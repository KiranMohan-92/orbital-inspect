/**
 * useSSE — Connects the Analysis Mode frontend to the backend SSE streaming endpoint.
 *
 * Uses fetch + ReadableStream (not native EventSource, which only supports GET).
 * Parses SSE events and dispatches them to useAnalysisState.
 */

import { useRef, useCallback } from "react";
import type { AgentName, AgentStatusType, AnalysisContext } from "../types";
import type { UseAnalysisReturn } from "./useAnalysisState";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface SSEEventData {
  agent: AgentName;
  status: AgentStatusType;
  payload: Record<string, unknown>;
  timestamp: number;
}

// ── Shared SSE Stream Parser ────────────────────────────────────────────────

interface SSEHandlers {
  onAgentEvent: (data: SSEEventData) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

/**
 * Read an SSE stream from a fetch Response, parse events, and dispatch to handlers.
 * Properly releases the reader lock on completion, error, or abort.
 */
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
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are delimited by double newlines
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const eventBlock of events) {
        if (!eventBlock.trim()) continue;

        const lines = eventBlock.split("\n");
        let eventType = "";
        let eventData = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            // Accumulate multi-line data fields per SSE spec
            eventData += (eventData ? "\n" : "") + line.slice(5).trim();
          }
        }

        if (!eventData) continue;

        if (eventType === "done") {
          handlers.onDone();
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
            const data: SSEEventData = JSON.parse(eventData);
            handlers.onAgentEvent(data);
          } catch {
            // Skip malformed events silently
          }
        }
      }
    }

    // Stream ended without a done event
    handlers.onDone();
  } finally {
    reader.releaseLock();
  }
}

// ── Hook ────────────────────────────────────────────────────────────────────

export function useSSE(analysis: UseAnalysisReturn) {
  const { updateAgent, startAnalysis, completeAnalysis, errorAnalysis } = analysis;
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  /** Dispatch an SSE agent event to the analysis state. */
  const handleAgentEvent = useCallback(
    (data: SSEEventData) => {
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
    [updateAgent]
  );

  const analyzeImage = useCallback(
    async (image: File, context?: AnalysisContext) => {
      cancel();

      const controller = new AbortController();
      abortRef.current = controller;

      const formData = new FormData();
      formData.append("file", image);

      if (context) {
        const filtered: Record<string, string> = {};
        for (const [k, v] of Object.entries(context)) {
          if (v && v.trim()) filtered[k] = v.trim();
        }
        if (Object.keys(filtered).length > 0) {
          formData.append("context", JSON.stringify(filtered));
        }
      }

      startAnalysis();

      try {
        const response = await fetch(`${API_BASE}/api/analyze`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Server error" }));
          throw new Error(errorData.detail || `Server error ${response.status}`);
        }

        await consumeSSEStream(response, {
          onAgentEvent: handleAgentEvent,
          onDone: completeAnalysis,
          onError: errorAnalysis,
        });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        const message =
          err instanceof TypeError
            ? "Cannot reach backend — is it running on http://localhost:8000?"
            : err instanceof Error
            ? err.message
            : String(err);
        errorAnalysis(message);
      }
    },
    [startAnalysis, handleAgentEvent, completeAnalysis, errorAnalysis, cancel]
  );

  const analyzeDemo = useCallback(
    async (scenario: string) => {
      cancel();

      const controller = new AbortController();
      abortRef.current = controller;

      startAnalysis();

      try {
        const response = await fetch(
          `${API_BASE}/api/analyze-demo?scenario=${encodeURIComponent(scenario)}`,
          { method: "POST", signal: controller.signal }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: "Demo not available" }));
          throw new Error(errorData.detail || `Server error ${response.status}`);
        }

        await consumeSSEStream(response, {
          onAgentEvent: handleAgentEvent,
          onDone: completeAnalysis,
          onError: errorAnalysis,
        });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        errorAnalysis(err instanceof Error ? err.message : "Demo analysis failed");
      }
    },
    [startAnalysis, handleAgentEvent, completeAnalysis, errorAnalysis, cancel]
  );

  return { analyzeImage, analyzeDemo, cancel };
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Generate a brief summary message for the agent feed when an agent completes. */
function summarizePayload(agent: AgentName, payload: Record<string, unknown>): string {
  switch (agent) {
    case "orchestrator": {
      const structType = payload.structure_type as string;
      const env = payload.environment_category as string;
      return structType ? `${structType} in ${env}` : "Validated";
    }
    case "vision": {
      const damages = payload.damages as unknown[];
      const severity = payload.overall_severity as string;
      if (damages?.length) return `${damages.length} damage(s) — ${severity}`;
      return severity ? `Overall: ${severity}` : "Analysis complete";
    }
    case "environment": {
      const stressors = payload.stressors as unknown[];
      return stressors?.length ? `${stressors.length} stressor(s) identified` : "Analysis complete";
    }
    case "failure_mode": {
      const mode = payload.failure_mode as string;
      return mode || "Classification complete";
    }
    case "priority": {
      const tier = payload.risk_tier as string;
      const composite = payload.risk_matrix as Record<string, unknown>;
      return tier
        ? `${tier} (${composite?.composite || "?"}/125)`
        : "Assessment complete";
    }
    default:
      return "Complete";
  }
}
