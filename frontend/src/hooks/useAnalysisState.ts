import { useReducer, useRef, useEffect, useCallback } from "react";
import type { AgentName, AgentState, AgentStatusType, AnalysisStatus } from "../types";

const AGENT_ORDER: AgentName[] = [
  "orbital_classification",
  "satellite_vision",
  "orbital_environment",
  "failure_mode",
  "insurance_risk",
];

function makeAgentState(): Record<AgentName, AgentState> {
  const state = {} as Record<AgentName, AgentState>;
  for (const name of AGENT_ORDER) {
    state[name] = { status: "queued", message: "", payload: null, timestamp: null };
  }
  return state;
}

export interface AnalysisFullState {
  image: File | null;
  imagePreviewUrl: string | null;
  noradId: string;
  analysisStatus: AnalysisStatus;
  errorMessage: string | null;
  agents: Record<AgentName, AgentState>;
  showAnnotations: boolean;
  elapsedTime: number;
}

const INITIAL_STATE: AnalysisFullState = {
  image: null,
  imagePreviewUrl: null,
  noradId: "",
  analysisStatus: "idle",
  errorMessage: null,
  agents: makeAgentState(),
  showAnnotations: true,
  elapsedTime: 0,
};

type Action =
  | { type: "SET_IMAGE"; image: File; previewUrl: string }
  | { type: "SET_NORAD_ID"; noradId: string }
  | { type: "START_ANALYSIS" }
  | { type: "AGENT_UPDATE"; agent: AgentName; status: AgentStatusType; message?: string; payload?: Record<string, unknown> }
  | { type: "ANALYSIS_COMPLETE" }
  | { type: "ANALYSIS_ERROR"; error: string }
  | { type: "TOGGLE_ANNOTATIONS" }
  | { type: "SET_ELAPSED"; time: number }
  | { type: "RESET" };

function reducer(state: AnalysisFullState, action: Action): AnalysisFullState {
  switch (action.type) {
    case "SET_IMAGE":
      if (state.imagePreviewUrl) URL.revokeObjectURL(state.imagePreviewUrl);
      return { ...INITIAL_STATE, image: action.image, imagePreviewUrl: action.previewUrl, noradId: state.noradId };
    case "SET_NORAD_ID":
      return { ...state, noradId: action.noradId };
    case "START_ANALYSIS":
      return { ...state, analysisStatus: "analyzing", errorMessage: null, agents: makeAgentState(), elapsedTime: 0 };
    case "AGENT_UPDATE":
      return {
        ...state,
        agents: {
          ...state.agents,
          [action.agent]: {
            status: action.status,
            message: action.message ?? state.agents[action.agent].message,
            payload: action.payload ?? state.agents[action.agent].payload,
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
      if (state.imagePreviewUrl) URL.revokeObjectURL(state.imagePreviewUrl);
      return { ...INITIAL_STATE };
    default:
      return state;
  }
}

export function useAnalysisState() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  useEffect(() => {
    if (state.analysisStatus === "analyzing") {
      startTimeRef.current = Date.now();
      timerRef.current = setInterval(() => {
        dispatch({ type: "SET_ELAPSED", time: Math.floor((Date.now() - startTimeRef.current) / 1000) });
      }, 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [state.analysisStatus]);

  return {
    state,
    setImage: useCallback((file: File) => {
      dispatch({ type: "SET_IMAGE", image: file, previewUrl: URL.createObjectURL(file) });
    }, []),
    setNoradId: useCallback((id: string) => dispatch({ type: "SET_NORAD_ID", noradId: id }), []),
    startAnalysis: useCallback(() => dispatch({ type: "START_ANALYSIS" }), []),
    updateAgent: useCallback((agent: AgentName, status: AgentStatusType, message?: string, payload?: Record<string, unknown>) => {
      dispatch({ type: "AGENT_UPDATE", agent, status, message, payload });
    }, []),
    completeAnalysis: useCallback(() => dispatch({ type: "ANALYSIS_COMPLETE" }), []),
    errorAnalysis: useCallback((error: string) => dispatch({ type: "ANALYSIS_ERROR", error }), []),
    toggleAnnotations: useCallback(() => dispatch({ type: "TOGGLE_ANNOTATIONS" }), []),
    reset: useCallback(() => dispatch({ type: "RESET" }), []),
    AGENT_ORDER,
  };
}

export type UseAnalysisReturn = ReturnType<typeof useAnalysisState>;
