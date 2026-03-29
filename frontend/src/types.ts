// ─── Satellite Domain Types ─────────────────────────────────────────────────

export type OrbitalRegime = "LEO" | "MEO" | "GEO" | "HEO" | "SSO" | "UNKNOWN";

export type SatelliteType =
  | "communications"
  | "earth_observation"
  | "navigation"
  | "scientific"
  | "weather"
  | "military"
  | "technology_demo"
  | "mega_constellation"
  | "space_station"
  | "other";

export interface SatelliteTarget {
  id: string;
  name: string | null;
  norad_id: string | null;
  cospar_id: string | null;
  operator: string | null;
  satellite_type: string;
  bus_platform: string | null;
  orbital_regime: string;
  altitude_km: number | null;
  inclination_deg: number | null;
  launch_date: string | null;
  design_life_years: number | null;
  age_years: number | null;
  mass_kg: number | null;
  power_watts: number | null;
  expected_components: string[];
  insured: boolean | null;
  insured_value_usd: number | null;
}

export interface ClassificationResult {
  valid: boolean;
  rejection_reason: string | null;
  satellite_type: string;
  bus_platform: string | null;
  orbital_regime: string;
  expected_components: string[];
  design_life_years: number | null;
  estimated_age_years: number | null;
  operator: string | null;
  notes: string;
}

// ─── Satellite Vision Types ─────────────────────────────────────────────────

export type DamageSeverity = "MINOR" | "MODERATE" | "SEVERE" | "CRITICAL";

export interface SatelliteDamageItem {
  id: number;
  type: string;
  description: string;
  bounding_box: [number, number, number, number]; // [y_min, x_min, y_max, x_max] 0-1000
  label: string;
  severity: DamageSeverity;
  confidence: number;
  uncertain: boolean;
  estimated_power_impact_pct: number;
}

export interface SatelliteDamagesAssessment {
  damages: SatelliteDamageItem[];
  overall_pattern: string;
  overall_severity: DamageSeverity;
  overall_confidence: number;
  total_power_impact_pct: number;
  healthy_areas_noted: string;
  component_assessed: string;
}

// ─── Orbital Environment Types ──────────────────────────────────────────────

export interface OrbitalStressor {
  name: string;
  severity: "LOW" | "MEDIUM" | "HIGH";
  measured_value: string;
  description: string;
  source: string;
}

export interface OrbitalEnvironmentAnalysis {
  orbital_regime: string;
  altitude_km: number | null;
  inclination_deg: number | null;
  debris_flux_density: string;
  collision_probability: string;
  radiation_dose_rate: string;
  thermal_cycling_range: string;
  atomic_oxygen_flux: string;
  stressors: OrbitalStressor[];
  accelerating_factors: string[];
  mitigating_factors: string[];
  data_sources: string[];
}

// ─── Failure Mode Types ─────────────────────────────────────────────────────

export interface SatellitePrecedent {
  event: string;
  satellite: string;
  operator: string;
  year: string;
  outcome: string;
  claim_amount_usd: string;
  relevance: string;
  source: string;
}

export interface SatelliteFailureModeAnalysis {
  failure_mode: string;
  mechanism: string;
  root_cause_chain: string[];
  progression_rate: "SLOW" | "MODERATE" | "RAPID";
  power_degradation_estimate_pct: number;
  remaining_life_revision_years: number | null;
  time_to_critical: string;
  historical_precedents: SatellitePrecedent[];
}

// ─── Insurance Risk Types ───────────────────────────────────────────────────

export type UnderwritingRecommendation =
  | "INSURABLE_STANDARD"
  | "INSURABLE_ELEVATED_PREMIUM"
  | "INSURABLE_WITH_EXCLUSIONS"
  | "FURTHER_INVESTIGATION"
  | "UNINSURABLE";

export interface RiskMatrixDimension {
  score: number; // 1-5
  reasoning: string;
}

export interface RiskMatrix {
  severity: RiskMatrixDimension;
  probability: RiskMatrixDimension;
  consequence: RiskMatrixDimension;
  composite: number; // 1-125
}

export interface ConsistencyCheck {
  passed: boolean;
  anomalies: string[];
  confidence_adjustment: string;
}

export interface InsuranceRiskReport {
  consistency_check: ConsistencyCheck;
  risk_matrix: RiskMatrix;
  risk_tier: string;
  estimated_remaining_life_years: number | null;
  power_margin_percentage: number | null;
  annual_degradation_rate_pct: number | null;
  replacement_cost_usd: number | null;
  depreciated_value_usd: number | null;
  revenue_at_risk_annual_usd: number | null;
  total_loss_probability: number | null;
  underwriting_recommendation: UnderwritingRecommendation;
  recommendation_rationale: string;
  recommended_actions: Array<{ action: string; timeline: string; priority: string }>;
  worst_case_scenario: string;
  summary: string;
}

// ─── Condition Report Types ─────────────────────────────────────────────────

export interface SatelliteConditionReport {
  target: SatelliteTarget;
  classification: ClassificationResult;
  vision: SatelliteDamagesAssessment | null;
  environment: OrbitalEnvironmentAnalysis | null;
  failure_mode: SatelliteFailureModeAnalysis | null;
  insurance_risk: InsuranceRiskReport | null;
  generated_at: string;
  report_version: string;
}

// ─── SSE Event Types ────────────────────────────────────────────────────────

export type AgentName =
  | "orbital_classification"
  | "satellite_vision"
  | "orbital_environment"
  | "failure_mode"
  | "insurance_risk";

export type AgentStatusType = "queued" | "thinking" | "complete" | "error";

export interface SSEEvent {
  agent: AgentName;
  status: AgentStatusType;
  payload: Record<string, unknown>;
  timestamp: number;
}

export interface AgentState {
  status: AgentStatusType;
  message: string;
  payload: Record<string, unknown> | null;
  timestamp: number | null;
}

export type AnalysisStatus = "idle" | "analyzing" | "complete" | "error";

export interface AnalysisContext {
  norad_id?: string;
  operator?: string;
  satellite_name?: string;
  insured_value?: string;
}
