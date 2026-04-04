/**
 * useSSE — Connects the Analysis Mode frontend to the backend SSE streaming endpoint.
 *
 * Uses fetch + ReadableStream (not native EventSource, which only supports GET).
 * Parses SSE events and dispatches them to useAnalysisState.
 */

import { useRef, useCallback } from "react";
import type {
  AgentName,
  AgentStatusType,
  AnalysisContext,
  AnalysisSubmissionResponse,
  AnalysisStatus,
} from "../types";
import type { UseAnalysisReturn } from "./useAnalysisState";
import { apiFetch, apiUrl } from "../utils/api";

const VALID_AGENTS = new Set<string>([
  "orbital_classification",
  "satellite_vision",
  "orbital_environment",
  "failure_mode",
  "insurance_risk",
]);

interface SSEEventData {
  agent: AgentName;
  status: AgentStatusType;
  payload: Record<string, unknown>;
  timestamp: number;
  analysis_id: string;
  event_id: string;
  sequence: number;
  schema_version: string;
  degraded: boolean;
}

interface SSEHandlers {
  onAgentEvent: (data: SSEEventData) => void;
  onDone: (status: string) => void;
  onError: (message: string) => void;
}

async function consumeSSEStream(response: Response, handlers: SSEHandlers): Promise<void> {
  if (!response.body) {
    throw new Error("No response body — SSE streaming not supported");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");

      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const eventBlock of events) {
        if (!eventBlock.trim()) {
          continue;
        }

        const lines = eventBlock.split("\n");
        let eventType = "";
        let eventData = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            eventData += (eventData ? "\n" : "") + line.slice(5).trim();
          }
        }

        if (!eventData) {
          continue;
        }

        if (eventType === "done") {
          try {
            const done = JSON.parse(eventData) as { status?: string };
            handlers.onDone(done.status || "completed");
          } catch {
            handlers.onDone("completed");
          }
          return;
        }

        if (eventType === "error") {
          try {
            const err = JSON.parse(eventData);
            handlers.onError(err.error || "Unknown error");
          } catch {
            handlers.onError("Stream error");
          }
          return;
        }

        if (eventType === "agent_event") {
          try {
            const data = JSON.parse(eventData) as SSEEventData;
            if (data.agent && data.status && VALID_AGENTS.has(data.agent)) {
              handlers.onAgentEvent(data);
            }
          } catch {
            // Ignore malformed events
          }
        }
      }
    }

    handlers.onDone("completed");
  } finally {
    reader.releaseLock();
  }
}

export function useSSE(analysis: UseAnalysisReturn) {
  const {
    updateAgent,
    startAnalysis,
    completeAnalysis,
    errorAnalysis,
    setAnalysisId,
  } = analysis;
  const abortRef = useRef<AbortController | null>(null);
  const analysisIdRef = useRef<string>("");
  const lastSequenceRef = useRef<number>(-1);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    analysisIdRef.current = "";
    lastSequenceRef.current = -1;
  }, []);

  const handleAgentEvent = useCallback(
    (data: SSEEventData) => {
      if (data.analysis_id && !analysisIdRef.current) {
        analysisIdRef.current = data.analysis_id;
        setAnalysisId(data.analysis_id);
      }
      if (data.sequence > 0 && data.sequence !== lastSequenceRef.current + 1) {
        console.warn(`SSE sequence gap: expected ${lastSequenceRef.current + 1}, got ${data.sequence}`);
      }
      lastSequenceRef.current = data.sequence;

      const message =
        data.status === "thinking"
          ? (typeof data.payload?.message === "string" ? data.payload.message : "Processing...")
          : data.status === "complete"
            ? summarizePayload(data.agent, data.payload)
            : data.status === "error"
              ? (typeof data.payload?.reason === "string" ? data.payload.reason : "Failed")
              : "";

      updateAgent(data.agent, data.status, message, data.payload);
    },
    [setAnalysisId, updateAgent]
  );

  const analyzeImage = useCallback(
    async (image: File, context?: AnalysisContext) => {
      cancel();

      const controller = new AbortController();
      abortRef.current = controller;

      const formData = new FormData();
      formData.append("image", image);

      if (context) {
        if (context.noradId) formData.append("norad_id", context.noradId);
        if (context.additionalContext) formData.append("context", context.additionalContext);
        if (context.assetType) formData.append("asset_type", context.assetType);
        if (context.inspectionEpoch) formData.append("inspection_epoch", context.inspectionEpoch);
        if (context.targetSubsystem) formData.append("target_subsystem", context.targetSubsystem);
        if (context.captureMetadata) formData.append("capture_metadata", JSON.stringify(context.captureMetadata));
        if (context.telemetrySummary) formData.append("telemetry_summary", JSON.stringify(context.telemetrySummary));
        if (context.baselineReference) formData.append("baseline_reference", JSON.stringify(context.baselineReference));
      }

      analysisIdRef.current = "";
      lastSequenceRef.current = -1;
      startAnalysis();

      try {
        const createResponse = await apiFetch("/api/analyses", {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });

        if (!createResponse.ok) {
          const errorData = await createResponse.json().catch(() => ({ detail: "Server error" }));
          throw new Error(errorData.detail || `Server error ${createResponse.status}`);
        }

        const created = (await createResponse.json()) as AnalysisSubmissionResponse;
        analysisIdRef.current = created.analysis_id;
        setAnalysisId(created.analysis_id);

        const response = await apiFetch(apiUrl(created.events_url), {
          method: "GET",
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Stream unavailable" }));
          throw new Error(errorData.detail || `Server error ${response.status}`);
        }

        await consumeSSEStream(response, {
          onAgentEvent: handleAgentEvent,
          onDone: (status) => completeAnalysis(mapTerminalStatus(status)),
          onError: errorAnalysis,
        });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          completeAnalysis("idle");
          return;
        }
        const message =
          err instanceof TypeError
            ? `Cannot reach backend — is it running on ${apiUrl("")}?`
            : err instanceof Error
              ? err.message
              : String(err);
        errorAnalysis(message);
      }
    },
    [cancel, completeAnalysis, errorAnalysis, handleAgentEvent, setAnalysisId, startAnalysis]
  );

  const analyzeDemo = useCallback(
    async (scenario: string) => {
      cancel();

      const controller = new AbortController();
      abortRef.current = controller;

      startAnalysis();

      try {
        const response = await apiFetch(
          `/api/demo/${encodeURIComponent(scenario)}`,
          { method: "POST", signal: controller.signal }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Demo not available" }));
          throw new Error(errorData.detail || `Server error ${response.status}`);
        }

        await consumeSSEStream(response, {
          onAgentEvent: handleAgentEvent,
          onDone: (status) => completeAnalysis(mapTerminalStatus(status)),
          onError: errorAnalysis,
        });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          completeAnalysis("idle");
          return;
        }
        errorAnalysis(err instanceof Error ? err.message : "Demo analysis failed");
      }
    },
    [cancel, completeAnalysis, errorAnalysis, handleAgentEvent, startAnalysis]
  );

  return { analyzeImage, analyzeDemo, cancel };
}

function summarizePayload(agent: AgentName, payload: Record<string, unknown>): string {
  switch (agent) {
    case "orbital_classification": {
      const satType = payload.satellite_type as string;
      const regime = payload.orbital_regime as string;
      return satType ? `${satType} — ${regime || "unknown regime"}` : "Classified";
    }
    case "satellite_vision": {
      const damages = payload.damages as unknown[];
      const severity = payload.overall_severity as string;
      if (damages?.length) return `${damages.length} anomal${damages.length !== 1 ? "ies" : "y"} — ${severity}`;
      return severity ? `Overall: ${severity}` : "Analysis complete";
    }
    case "orbital_environment": {
      const stressors = payload.stressors as unknown[];
      return stressors?.length ? `${stressors.length} stressor(s) identified` : "Environment assessed";
    }
    case "failure_mode": {
      const mode = payload.failure_mode as string;
      const rate = payload.progression_rate as string;
      return mode ? `${mode} — ${rate || ""}` : "Mechanisms analyzed";
    }
    case "insurance_risk": {
      const tier = payload.risk_tier as string;
      const composite = payload.risk_matrix as Record<string, unknown>;
      const rec = payload.underwriting_recommendation as string;
      if (tier && rec) return `${tier} (${composite?.composite || "?"}/125) — ${rec.replace(/_/g, " ")}`;
      return tier ? `${tier}` : "Assessment complete";
    }
    default:
      return "Complete";
  }
}

function mapTerminalStatus(status: string): AnalysisStatus {
  switch (status) {
    case "completed_partial":
      return "completed_partial";
    case "failed":
      return "failed";
    case "rejected":
      return "rejected";
    case "complete":
    case "completed":
    default:
      return "completed";
  }
}
