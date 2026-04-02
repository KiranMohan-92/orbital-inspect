import { useReducer, useRef, useEffect, useCallback } from "react";
import type { AgentName, AgentState, AgentStatusType, AnalysisStatus, AssetType } from "../types";

export const AGENT_ORDER: AgentName[] = [
  "orbital_classification",
  "satellite_vision",
  "orbital_environment",
  "failure_mode",
  "insurance_risk",
];

export function makeAgentState(): Record<AgentName, AgentState> {
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
  assetType: AssetType;
  inspectionEpoch: string;
  targetSubsystem: string;
  additionalContext: string;
  analysisStatus: AnalysisStatus;
  errorMessage: string | null;
  analysisId: string | null;
  agents: Record<AgentName, AgentState>;
  showAnnotations: boolean;
  elapsedTime: number;
}

export function buildInitialAnalysisState(): AnalysisFullState {
  return {
    image: null,
    imagePreviewUrl: null,
    noradId: "",
    assetType: "satellite",
    inspectionEpoch: "",
    targetSubsystem: "",
    additionalContext: "",
    analysisStatus: "idle",
    errorMessage: null,
    analysisId: null,
    agents: makeAgentState(),
    showAnnotations: true,
    elapsedTime: 0,
  };
}

const INITIAL_STATE = buildInitialAnalysisState();

export type AnalysisAction =
  | { type: "SET_IMAGE"; image: File; previewUrl: string }
  | { type: "SET_NORAD_ID"; noradId: string }
  | { type: "SET_ASSET_TYPE"; assetType: AssetType }
  | { type: "SET_INSPECTION_EPOCH"; inspectionEpoch: string }
  | { type: "SET_TARGET_SUBSYSTEM"; targetSubsystem: string }
  | { type: "SET_ADDITIONAL_CONTEXT"; additionalContext: string }
  | { type: "START_ANALYSIS" }
  | { type: "SET_ANALYSIS_ID"; analysisId: string }
  | { type: "AGENT_UPDATE"; agent: AgentName; status: AgentStatusType; message?: string; payload?: Record<string, unknown> }
  | { type: "ANALYSIS_COMPLETE"; status: AnalysisStatus }
  | { type: "ANALYSIS_ERROR"; error: string }
  | { type: "TOGGLE_ANNOTATIONS" }
  | { type: "SET_ELAPSED"; time: number }
  | { type: "RESET" };

export function analysisStateReducer(state: AnalysisFullState, action: AnalysisAction): AnalysisFullState {
  switch (action.type) {
    case "SET_IMAGE":
      if (state.imagePreviewUrl) URL.revokeObjectURL(state.imagePreviewUrl);
      return {
        ...buildInitialAnalysisState(),
        image: action.image,
        imagePreviewUrl: action.previewUrl,
        noradId: state.noradId,
        assetType: state.assetType,
        inspectionEpoch: state.inspectionEpoch,
        targetSubsystem: state.targetSubsystem,
        additionalContext: state.additionalContext,
      };
    case "SET_NORAD_ID":
      return { ...state, noradId: action.noradId };
    case "SET_ASSET_TYPE":
      return { ...state, assetType: action.assetType };
    case "SET_INSPECTION_EPOCH":
      return { ...state, inspectionEpoch: action.inspectionEpoch };
    case "SET_TARGET_SUBSYSTEM":
      return { ...state, targetSubsystem: action.targetSubsystem };
    case "SET_ADDITIONAL_CONTEXT":
      return { ...state, additionalContext: action.additionalContext };
    case "START_ANALYSIS":
      return {
        ...state,
        analysisStatus: "analyzing",
        errorMessage: null,
        analysisId: null,
        agents: makeAgentState(),
        elapsedTime: 0,
      };
    case "SET_ANALYSIS_ID":
      return { ...state, analysisId: action.analysisId };
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
      return { ...state, analysisStatus: action.status };
    case "ANALYSIS_ERROR":
      return { ...state, analysisStatus: "failed", errorMessage: action.error };
    case "TOGGLE_ANNOTATIONS":
      return { ...state, showAnnotations: !state.showAnnotations };
    case "SET_ELAPSED":
      return { ...state, elapsedTime: action.time };
    case "RESET":
      if (state.imagePreviewUrl) URL.revokeObjectURL(state.imagePreviewUrl);
      return buildInitialAnalysisState();
    default:
      return state;
  }
}

export function useAnalysisState() {
  const [state, dispatch] = useReducer(analysisStateReducer, INITIAL_STATE);
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
    setAssetType: useCallback((assetType: AssetType) => dispatch({ type: "SET_ASSET_TYPE", assetType }), []),
    setInspectionEpoch: useCallback((inspectionEpoch: string) => dispatch({ type: "SET_INSPECTION_EPOCH", inspectionEpoch }), []),
    setTargetSubsystem: useCallback((targetSubsystem: string) => dispatch({ type: "SET_TARGET_SUBSYSTEM", targetSubsystem }), []),
    setAdditionalContext: useCallback((additionalContext: string) => dispatch({ type: "SET_ADDITIONAL_CONTEXT", additionalContext }), []),
    startAnalysis: useCallback(() => dispatch({ type: "START_ANALYSIS" }), []),
    setAnalysisId: useCallback((analysisId: string) => dispatch({ type: "SET_ANALYSIS_ID", analysisId }), []),
    updateAgent: useCallback((agent: AgentName, status: AgentStatusType, message?: string, payload?: Record<string, unknown>) => {
      dispatch({ type: "AGENT_UPDATE", agent, status, message, payload });
    }, []),
    completeAnalysis: useCallback((status: AnalysisStatus = "completed") => dispatch({ type: "ANALYSIS_COMPLETE", status }), []),
    errorAnalysis: useCallback((error: string) => dispatch({ type: "ANALYSIS_ERROR", error }), []),
    toggleAnnotations: useCallback(() => dispatch({ type: "TOGGLE_ANNOTATIONS" }), []),
    reset: useCallback(() => dispatch({ type: "RESET" }), []),
    AGENT_ORDER,
  };
}

export type UseAnalysisReturn = ReturnType<typeof useAnalysisState>;
