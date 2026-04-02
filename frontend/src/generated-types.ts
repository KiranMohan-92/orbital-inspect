/**
 * Auto-generated TypeScript types from Pydantic models.
 * DO NOT EDIT MANUALLY — run: python backend/scripts/generate_types.py
 * Generated from backend/models/satellite.py and backend/models/events.py
 */

export type OrbitalRegime = "LEO" | "MEO" | "GEO" | "HEO" | "SSO" | "UNKNOWN";

export type SatelliteType = "communications" | "earth_observation" | "navigation" | "scientific" | "weather" | "military" | "technology_demo" | "mega_constellation" | "space_station" | "other";

export type UnderwritingRecommendation = "INSURABLE_STANDARD" | "INSURABLE_ELEVATED_PREMIUM" | "INSURABLE_WITH_EXCLUSIONS" | "FURTHER_INVESTIGATION" | "UNINSURABLE";

export type DamageSeverity = "MINOR" | "MODERATE" | "SEVERE" | "CRITICAL";
export type ProgressionRate = "SLOW" | "MODERATE" | "RAPID" | "SUDDEN";
export type StressorSeverity = "LOW" | "MEDIUM" | "HIGH";
export type AssetType = "satellite" | "servicer" | "station_module" | "solar_array" | "radiator" | "power_node" | "compute_platform" | "other";
export type AgentName = "orbital_classification" | "satellite_vision" | "orbital_environment" | "failure_mode" | "insurance_risk";
export type AgentStatusType = "queued" | "thinking" | "complete" | "error";
export type AnalysisStatus = "idle" | "analyzing" | "completed" | "completed_partial" | "failed" | "rejected" | "error";

export interface SatelliteTarget {
  id: string;
  name?: string | null;
  norad_id?: string | null;
  cospar_id?: string | null;
  operator?: string | null;
  satellite_type?: string;
  bus_platform?: string | null;
  orbital_regime?: string;
  altitude_km?: number | null;
  inclination_deg?: number | null;
  launch_date?: string | null;
  design_life_years?: number | null;
  age_years?: number | null;
  mass_kg?: number | null;
  power_watts?: number | null;
  expected_components?: string[];
  insured?: boolean | null;
  insured_value_usd?: number | null;
}

export interface ClassificationResult {
  valid?: boolean;
  rejection_reason?: string | null;
  satellite_type?: string;
  bus_platform?: string | null;
  orbital_regime?: string;
  expected_components?: string[];
  design_life_years?: number | null;
  estimated_age_years?: number | null;
  operator?: string | null;
  notes?: string;
  degraded?: boolean;
}

export interface SatelliteDamageItem {
  id: number;
  type: string;
  description: string;
  bounding_box: number[];
  label: string;
  severity: string;
  confidence: number;
  uncertain?: boolean;
  estimated_power_impact_pct?: number;
}

export interface SatelliteDamagesAssessment {
  damages?: SatelliteDamageItem[];
  overall_pattern?: string;
  overall_severity?: string;
  overall_confidence?: number;
  total_power_impact_pct?: number;
  healthy_areas_noted?: string;
  component_assessed?: string;
  degraded?: boolean;
}

export interface OrbitalStressor {
  name: string;
  severity: string;
  measured_value?: string;
  description?: string;
  source?: string;
}

export interface OrbitalEnvironmentAnalysis {
  orbital_regime?: string;
  altitude_km?: number | null;
  inclination_deg?: number | null;
  debris_flux_density?: string;
  collision_probability?: string;
  radiation_dose_rate?: string;
  thermal_cycling_range?: string;
  atomic_oxygen_flux?: string;
  stressors?: OrbitalStressor[];
  accelerating_factors?: string[];
  mitigating_factors?: string[];
  data_sources?: string[];
  degraded?: boolean;
}

export interface SatellitePrecedent {
  event: string;
  satellite?: string;
  operator?: string;
  year?: string;
  outcome?: string;
  claim_amount_usd?: string;
  relevance?: string;
  source?: string;
}

export interface SatelliteFailureModeAnalysis {
  failure_mode?: string;
  mechanism?: string;
  root_cause_chain?: string[];
  progression_rate?: string;
  power_degradation_estimate_pct?: number;
  remaining_life_revision_years?: number | null;
  time_to_critical?: string;
  historical_precedents?: SatellitePrecedent[];
  degraded?: boolean;
}

export interface RiskMatrixDimension {
  score: number;
  reasoning?: string;
}

export interface RiskMatrix {
  severity: RiskMatrixDimension;
  probability: RiskMatrixDimension;
  consequence: RiskMatrixDimension;
  composite: number;
}

export interface ConsistencyCheck {
  passed?: boolean;
  anomalies?: string[];
  confidence_adjustment?: string;
}

export interface InsuranceRiskReport {
  consistency_check: ConsistencyCheck;
  risk_matrix: RiskMatrix;
  risk_tier: string;
  estimated_remaining_life_years?: number | null;
  power_margin_percentage?: number | null;
  annual_degradation_rate_pct?: number | null;
  replacement_cost_usd?: number | null;
  depreciated_value_usd?: number | null;
  revenue_at_risk_annual_usd?: number | null;
  total_loss_probability?: number | null;
  underwriting_recommendation?: string;
  recommendation_rationale?: string;
  recommended_actions?: Record<string, unknown>[];
  worst_case_scenario?: string;
  summary?: string;
  degraded?: boolean;
  evidence_gaps?: string[];
  report_completeness?: string;
}

export interface SatelliteConditionReport {
  target: SatelliteTarget;
  classification: ClassificationResult;
  vision?: SatelliteDamagesAssessment | null;
  environment?: OrbitalEnvironmentAnalysis | null;
  failure_mode?: SatelliteFailureModeAnalysis | null;
  insurance_risk?: InsuranceRiskReport | null;
  generated_at?: string;
  report_version?: string;
}

export interface AgentEvent {
  agent: string;
  status: string;
  payload?: Record<string, unknown>;
  timestamp?: number;
  analysis_id?: string;
  event_id?: string;
  sequence?: number;
  schema_version?: string;
  degraded?: boolean;
}
