import { useReducer, useRef, useEffect, useCallback } from "react";
import type {
  AgentName,
  AgentState,
  AgentStatusType,
  AnalysisStatus,
} from "../types";

// ── State Shape ─────────────────────────────────────────────────────────────

const AGENT_ORDER: AgentName[] = [
  "orchestrator",
  "vision",
  "environment",
  "failure_mode",
  "priority",
];

function makeAgentState(): Record<AgentName, AgentState> {
  const state = {} as Record<AgentName, AgentState>;
  for (const name of AGENT_ORDER) {
    state[name] = {
      status: "queued",
      message: "",
      payload: null,
      timestamp: null,
    };
  }
  return state;
}

export interface AnalysisFullState {
  image: File | null;
  imagePreviewUrl: string | null;
  analysisStatus: AnalysisStatus;
  errorMessage: string | null;
  agents: Record<AgentName, AgentState>;
  showAnnotations: boolean;
  elapsedTime: number;
}

const INITIAL_STATE: AnalysisFullState = {
  image: null,
  imagePreviewUrl: null,
  analysisStatus: "idle",
  errorMessage: null,
  agents: makeAgentState(),
  showAnnotations: true,
  elapsedTime: 0,
};

// ── Actions ─────────────────────────────────────────────────────────────────

type Action =
  | { type: "SET_IMAGE"; image: File; previewUrl: string }
  | { type: "START_ANALYSIS" }
  | {
      type: "AGENT_UPDATE";
      agent: AgentName;
      status: AgentStatusType;
      message?: string;
      payload?: Record<string, unknown>;
    }
  | { type: "ANALYSIS_COMPLETE" }
  | { type: "ANALYSIS_ERROR"; error: string }
  | { type: "TOGGLE_ANNOTATIONS" }
  | { type: "SET_ELAPSED"; time: number }
  | { type: "RESET" };

function reducer(state: AnalysisFullState, action: Action): AnalysisFullState {
  switch (action.type) {
    case "SET_IMAGE":
      // Revoke previous object URL to prevent memory leaks
      if (state.imagePreviewUrl) {
        URL.revokeObjectURL(state.imagePreviewUrl);
      }
      return {
        ...INITIAL_STATE,
        image: action.image,
        imagePreviewUrl: action.previewUrl,
      };

    case "START_ANALYSIS":
      return {
        ...state,
        analysisStatus: "analyzing",
        agents: makeAgentState(),
        elapsedTime: 0,
      };

    case "AGENT_UPDATE":
      return {
        ...state,
        agents: {
          ...state.agents,
          [action.agent]: {
            status: action.status,
            message: action.message || state.agents[action.agent].message,
            payload: action.payload || state.agents[action.agent].payload,
            timestamp: Date.now(),
          },
        },
      };

    case "ANALYSIS_COMPLETE":
      return { ...state, analysisStatus: "complete" };

    case "ANALYSIS_ERROR":
      return { ...state, analysisStatus: "error", errorMessage: action.error };

    case "TOGGLE_ANNOTATIONS":
      return { ...state, showAnnotations: !state.showAnnotations };

    case "SET_ELAPSED":
      return { ...state, elapsedTime: action.time };

    case "RESET":
      if (state.imagePreviewUrl) {
        URL.revokeObjectURL(state.imagePreviewUrl);
      }
      return { ...INITIAL_STATE };

    default:
      return state;
  }
}

// ── Hook ────────────────────────────────────────────────────────────────────

export function useAnalysisState() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  // Elapsed time timer
  useEffect(() => {
    if (state.analysisStatus === "analyzing") {
      startTimeRef.current = Date.now();
      timerRef.current = setInterval(() => {
        dispatch({
          type: "SET_ELAPSED",
          time: Math.floor((Date.now() - startTimeRef.current) / 1000),
        });
      }, 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [state.analysisStatus]);

  const setImage = useCallback((file: File) => {
    const previewUrl = URL.createObjectURL(file);
    dispatch({ type: "SET_IMAGE", image: file, previewUrl });
  }, []);

  const startAnalysis = useCallback(() => {
    dispatch({ type: "START_ANALYSIS" });
  }, []);

  const updateAgent = useCallback(
    (
      agent: AgentName,
      status: AgentStatusType,
      message?: string,
      payload?: Record<string, unknown>
    ) => {
      dispatch({ type: "AGENT_UPDATE", agent, status, message, payload });
    },
    []
  );

  const completeAnalysis = useCallback(() => {
    dispatch({ type: "ANALYSIS_COMPLETE" });
  }, []);

  const errorAnalysis = useCallback((error: string) => {
    dispatch({ type: "ANALYSIS_ERROR", error });
  }, []);

  const toggleAnnotations = useCallback(() => {
    dispatch({ type: "TOGGLE_ANNOTATIONS" });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: "RESET" });
  }, []);

  return {
    state,
    setImage,
    startAnalysis,
    updateAgent,
    completeAnalysis,
    errorAnalysis,
    toggleAnnotations,
    reset,
    AGENT_ORDER,
  };
}

export type UseAnalysisReturn = ReturnType<typeof useAnalysisState>;
