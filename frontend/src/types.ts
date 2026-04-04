/**
 * Orbital Inspect Type System
 *
 * Domain types are auto-generated from Pydantic models.
 * Frontend-only types are defined below.
 */

// Re-export all generated types from Pydantic models
export * from "./generated-types";

import type {
  AssetType,
  AgentStatusType,
  AgentName,
  SatelliteTarget,
  ClassificationResult,
  SatelliteDamagesAssessment,
  OrbitalEnvironmentAnalysis,
  SatelliteFailureModeAnalysis,
  InsuranceRiskReport,
} from "./generated-types";

// ─── Frontend-only types ─────────────────────────────────────────────────────

export interface AgentState {
  status: AgentStatusType;
  message: string;
  payload: Record<string, unknown> | null;
  timestamp: number | null;
}

export interface AnalysisContext {
  noradId?: string;
  additionalContext?: string;
  assetType?: AssetType;
  inspectionEpoch?: string;
  targetSubsystem?: string;
  captureMetadata?: Record<string, unknown>;
  telemetrySummary?: Record<string, unknown>;
  baselineReference?: Record<string, unknown>;
}

export interface SSEEvent {
  agent: AgentName;
  status: AgentStatusType;
  payload: Record<string, unknown>;
  timestamp: number;
  // v2 fields
  analysis_id: string;
  event_id: string;
  sequence: number;
  schema_version: string;
  degraded: boolean;
}

export interface AnalysisSubmissionResponse {
  analysis_id: string;
  status: string;
  analysis_url: string;
  events_url: string;
  request_id?: string | null;
  dispatch_mode?: string;
  queue_job_id?: string | null;
}

export interface SatelliteConditionReportFull {
  target: SatelliteTarget;
  classification: ClassificationResult;
  vision: SatelliteDamagesAssessment | null;
  environment: OrbitalEnvironmentAnalysis | null;
  failure_mode: SatelliteFailureModeAnalysis | null;
  insurance_risk: InsuranceRiskReport | null;
  generated_at: string;
  report_version: string;
}
