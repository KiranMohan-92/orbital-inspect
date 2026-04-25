import { Suspense, useCallback, useEffect, useState } from "react";
import AgentFeed from "./AgentFeed";
import InsuranceRiskCard from "./InsuranceRiskCard";
import { RiskMatrixDrilldown, DegradationTimeline } from "../viz";
import type { UseAnalysisReturn } from "../../hooks/useAnalysisState";
import type { InsuranceRiskReport, SatelliteFailureModeAnalysis, ClassificationResult } from "../../types";
import { apiFetch, apiUrl, readApiErrorMessage } from "../../utils/api";

interface Props {
  analysis: UseAnalysisReturn;
}

interface DecisionSummary {
  recommended_action?: string | null;
  policy_recommended_action?: string | null;
  decision_confidence?: string | null;
  decision_rationale?: string | null;
  required_human_review?: boolean;
  blocked?: boolean;
  blocked_reason?: string | null;
  evidence_completeness_bucket?: string | null;
  urgency?: string | null;
  policy_version?: string | null;
  override_active?: boolean;
  override_reason_code?: string | null;
  override_reason?: string | null;
}

interface PersistedAnalysisDetail {
  asset_id?: string | null;
  asset_name?: string | null;
  asset_external_id?: string | null;
  asset_identity_source?: string | null;
  subsystem_id?: string | null;
  subsystem_key?: string | null;
  assessment_mode?: string | null;
  decision_authority?: string | null;
  required_evidence_gaps?: Array<{ id?: string; label?: string; description?: string; status?: string }>;
  unsupported_claims_blocked?: string[];
  decision_summary?: DecisionSummary | null;
  decision_status?: string | null;
  decision_approved_by?: string | null;
  decision_approved_at?: string | null;
  decision_override_reason?: string | null;
  triage_score?: number | null;
  triage_band?: string | null;
  permissions?: {
    can_review_decision?: boolean;
    can_override_decision?: boolean;
  };
}

interface AnalysisEvidenceItem {
  evidence_id: string;
  used_for?: string | null;
  source_type: string;
  evidence_role: string;
  source_label: string;
  source_domain: string;
  confidence?: number | null;
  confidence_bucket: string;
  provider?: string | null;
  captured_at?: string | null;
  ingested_at?: string | null;
  source_url?: string | null;
  tags?: string[];
  highlights?: string[];
}

interface ReferenceProfileDetail {
  operator_name?: string | null;
  manufacturer?: string | null;
  mission_class?: string | null;
  orbit_regime?: string | null;
  reference_revision?: string | null;
  dimensions_json?: Record<string, unknown>;
  subsystem_baseline_json?: Record<string, unknown>;
  reference_sources_json?: string[];
  last_verified_at?: string | null;
}

interface AnalysisEvidenceDetail {
  summary?: {
    evidence_completeness_pct?: number | null;
    linked_evidence_count?: number;
    sources_available?: string[];
    evidence_gaps?: string[];
    evidence_quality?: {
      quality_score?: number;
      missing_required_sources?: string[];
      failed_source_count?: number;
      stale_source_count?: number;
      low_confidence_count?: number;
      gaps?: Array<{
        source: string;
        status: string;
        description: string;
      }>;
    };
    assessment_contract?: {
      assessment_mode?: string;
      decision_authority?: string;
      report_title?: string;
      required_evidence_gaps?: Array<{ id?: string; label?: string; description?: string; status?: string }>;
      unsupported_claims_blocked?: string[];
      authority_rationale?: string;
    };
    counts_by_role?: Record<string, number>;
    counts_by_domain?: Record<string, number>;
  };
  reference_profile?: ReferenceProfileDetail | null;
  items?: AnalysisEvidenceItem[];
}

const DOMAIN_LABELS: Record<string, string> = {
  public: "PUBLIC",
  operator_supplied: "OPERATOR",
  internal: "INTERNAL",
  partner: "PARTNER",
  offline_eval: "OFFLINE",
  unknown: "UNKNOWN",
};

const DOMAIN_STYLES: Record<string, { color: string; background: string; border: string }> = {
  public: {
    color: "#60a5fa",
    background: "rgba(96,165,250,0.12)",
    border: "rgba(96,165,250,0.22)",
  },
  operator_supplied: {
    color: "#34d399",
    background: "rgba(52,211,153,0.12)",
    border: "rgba(52,211,153,0.22)",
  },
  internal: {
    color: "#c084fc",
    background: "rgba(192,132,252,0.12)",
    border: "rgba(192,132,252,0.22)",
  },
  partner: {
    color: "#f59e0b",
    background: "rgba(245,158,11,0.12)",
    border: "rgba(245,158,11,0.22)",
  },
  offline_eval: {
    color: "#94a3b8",
    background: "rgba(148,163,184,0.12)",
    border: "rgba(148,163,184,0.22)",
  },
  unknown: {
    color: "#94a3b8",
    background: "rgba(148,163,184,0.12)",
    border: "rgba(148,163,184,0.22)",
  },
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "#22c55e",
  medium: "#f59e0b",
  low: "#ef4444",
  unknown: "#94a3b8",
};

function titleize(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return value.replace(/_/g, " ").replace(/-/g, " ").toUpperCase();
}

function safeDateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export default function IntelligenceReport({ analysis }: Props) {
  const { state, AGENT_ORDER } = analysis;
  const insurancePayload = state.agents.insurance_risk.payload as InsuranceRiskReport | null;
  const failureModePayload = state.agents.failure_mode.payload as SatelliteFailureModeAnalysis | null;
  const classificationPayload = state.agents.orbital_classification.payload as ClassificationResult | null;
  const isComplete = (state.analysisStatus === "completed" || state.analysisStatus === "completed_partial") && insurancePayload;
  const isPartial = state.analysisStatus === "completed_partial";
  const derivedAgentFailure = AGENT_ORDER
    .map((agentName) => state.agents[agentName])
    .find((agent) => agent.status === "error");
  const derivedFailureMessage =
    state.errorMessage ||
    (typeof derivedAgentFailure?.payload?.reason === "string" ? derivedAgentFailure.payload.reason : null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [persistedAnalysis, setPersistedAnalysis] = useState<PersistedAnalysisDetail | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [evidenceDetail, setEvidenceDetail] = useState<AnalysisEvidenceDetail | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [overrideAction, setOverrideAction] = useState("monitor");
  const [overrideReasonCode, setOverrideReasonCode] = useState("new_evidence");
  const [overrideComments, setOverrideComments] = useState("");
  const assessmentMode =
    (insurancePayload as { assessment_mode?: string } | null)?.assessment_mode ||
    persistedAnalysis?.assessment_mode ||
    evidenceDetail?.summary?.assessment_contract?.assessment_mode ||
    state.assessmentMode;
  const decisionAuthority =
    (insurancePayload as { decision_authority?: string } | null)?.decision_authority ||
    persistedAnalysis?.decision_authority ||
    evidenceDetail?.summary?.assessment_contract?.decision_authority ||
    "SCREENING_ONLY";
  const reportTitle =
    (insurancePayload as { report_title?: string } | null)?.report_title ||
    evidenceDetail?.summary?.assessment_contract?.report_title ||
    (decisionAuthority === "SCREENING_ONLY" ? "Public Risk Screen" : "Technical Risk Assessment");
  const requiredEvidenceGaps =
    (insurancePayload as { required_evidence_gaps?: Array<{ id?: string; label?: string; description?: string; status?: string }> } | null)?.required_evidence_gaps ||
    persistedAnalysis?.required_evidence_gaps ||
    evidenceDetail?.summary?.assessment_contract?.required_evidence_gaps ||
    [];
  const unsupportedClaims =
    (insurancePayload as { unsupported_claims_blocked?: string[] } | null)?.unsupported_claims_blocked ||
    persistedAnalysis?.unsupported_claims_blocked ||
    evidenceDetail?.summary?.assessment_contract?.unsupported_claims_blocked ||
    [];

  useEffect(() => {
    if (!state.analysisId || !["completed", "completed_partial", "failed", "rejected"].includes(state.analysisStatus)) {
      return;
    }

    let cancelled = false;
    async function fetchDetail() {
      setDecisionLoading(true);
      try {
        for (let attempt = 0; attempt < 6 && !cancelled; attempt += 1) {
          const response = await apiFetch(`/api/analyses/${state.analysisId}`);
          if (!response.ok) {
            return;
          }
          const payload = (await response.json()) as PersistedAnalysisDetail;
          if (cancelled) {
            return;
          }
          setPersistedAnalysis(payload);

          const ready =
            Boolean(payload.decision_summary) &&
            payload.decision_status !== "pending_policy";
          if (ready) {
            return;
          }

          await new Promise((resolve) => window.setTimeout(resolve, 600));
        }
      } finally {
        if (!cancelled) {
          setDecisionLoading(false);
        }
      }
    }
    void fetchDetail();
    return () => {
      cancelled = true;
    };
  }, [state.analysisId, state.analysisStatus]);

  useEffect(() => {
    if (!state.analysisId || !["completed", "completed_partial", "failed", "rejected"].includes(state.analysisStatus)) {
      setEvidenceDetail(null);
      return;
    }

    let cancelled = false;
    async function fetchEvidence() {
      setEvidenceLoading(true);
      setEvidenceError(null);
      try {
        const response = await apiFetch(`/api/analyses/${state.analysisId}/evidence`);
        if (!response.ok) {
          throw new Error(await readApiErrorMessage(response, "Evidence detail unavailable"));
        }
        const payload = await response.json() as AnalysisEvidenceDetail;
        if (!cancelled) {
          setEvidenceDetail(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setEvidenceError(error instanceof Error ? error.message : "Evidence detail unavailable");
        }
      } finally {
        if (!cancelled) {
          setEvidenceLoading(false);
        }
      }
    }

    void fetchEvidence();
    return () => {
      cancelled = true;
    };
  }, [state.analysisId, state.analysisStatus]);

  const handleDecisionReview = useCallback(async (
    action: "approve" | "block" | "request_reimage" | "override_action" | "reset_review",
    options?: { comments?: string; overrideAction?: string; reasonCode?: string }
  ) => {
    if (!state.analysisId) return;
    setDecisionBusy(true);
    setDecisionError(null);
    try {
      const response = await apiFetch(`/api/analyses/${state.analysisId}/decision/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          comments:
            options?.comments ??
            (action === "approve"
              ? "Approved for operational use"
              : action === "block"
                ? "Blocked pending analyst review"
                : action === "request_reimage"
                  ? "Re-image required before decision use"
                  : ""),
          override_action: options?.overrideAction,
          reason_code: options?.reasonCode,
        }),
      });
      if (!response.ok) {
        throw new Error(await readApiErrorMessage(response, "Decision review failed"));
      }
      const payload = await response.json() as PersistedAnalysisDetail;
      setPersistedAnalysis((current) => ({ ...(current ?? {}), ...payload }));
      setOverrideComments("");
    } catch (error) {
      setDecisionError(error instanceof Error ? error.message : "Decision review failed");
    } finally {
      setDecisionBusy(false);
    }
  }, [state.analysisId]);

  const canReviewDecision = persistedAnalysis?.permissions?.can_review_decision ?? false;
  const canOverrideDecision = persistedAnalysis?.permissions?.can_override_decision ?? false;

  const handleDownloadReport = useCallback(async () => {
    setPdfLoading(true);
    try {
      if (state.analysisId) {
        const response = await apiFetch(`/api/reports/${state.analysisId}/generate-pdf`, {
          method: "POST",
        });
        if (!response.ok) throw new Error(`Report generation failed: ${response.status}`);
        const artifact = await response.json() as { artifact_download_url?: string };
        if (!artifact.artifact_download_url) {
          throw new Error("Report artifact URL missing");
        }
        const url = apiUrl(artifact.artifact_download_url);
        window.open(url, "_blank");
      } else {
        const response = await apiFetch("/api/reports/inline/generate-pdf", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            classification: state.agents.orbital_classification.payload || {},
            vision: state.agents.satellite_vision.payload || {},
            environment: state.agents.orbital_environment.payload || {},
            failure_mode: state.agents.failure_mode.payload || {},
            insurance_risk: state.agents.insurance_risk.payload || {},
          }),
        });
        if (!response.ok) throw new Error(`Report generation failed: ${response.status}`);
        const html = await response.text();
        const blob = new Blob([html], { type: "text/html" });
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
        setTimeout(() => URL.revokeObjectURL(url), 30000);
      }
    } catch {
      window.print();
    } finally {
      setPdfLoading(false);
    }
  }, [state.agents, state.analysisId]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--bg-panel-border)" }}>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--agent-insurance)" }} />
          <p className="label-mono">{reportTitle.toUpperCase()}</p>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto dark-scrollbar px-4 py-3 space-y-4">
        {/* Agent Pipeline Feed */}
        {state.analysisStatus !== "idle" && (
          <AgentFeed agents={state.agents} agentOrder={AGENT_ORDER} />
        )}

        {state.analysisStatus !== "idle" && (
          <div className="data-card">
            <div className="flex items-center justify-between gap-3">
              <p className="label-mono">ANALYSIS TRACE</p>
              {state.analysisId && (
                <span className="font-mono-data text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                  {state.analysisId}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Mode</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {titleize(assessmentMode)}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Authority</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {titleize(decisionAuthority)}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Asset Label</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {persistedAnalysis?.asset_name || state.assetName || "n/a"}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Asset Type</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>{state.assetType}</p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>NORAD</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>{state.noradId || "n/a"}</p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Operator Asset ID</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {persistedAnalysis?.asset_external_id || state.externalAssetId || "n/a"}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Inspection Epoch</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>{state.inspectionEpoch || "n/a"}</p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Subsystem</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {persistedAnalysis?.subsystem_key || state.targetSubsystem || "n/a"}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Identity Source</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {(persistedAnalysis?.asset_identity_source || "unknown").replace(/_/g, " ")}
                </p>
              </div>
            </div>
            <div className="mt-3 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
              Governance: public/open data supports screening and evidence triage. Underwriting use requires private evidence and human review.
            </div>
          </div>
        )}

        {decisionAuthority === "SCREENING_ONLY" && state.analysisStatus !== "idle" && (
          <div data-testid="public-risk-screen-banner" className="data-card" style={{ borderColor: "rgba(96,165,250,0.25)", background: "rgba(96,165,250,0.06)" }}>
            <p className="label-mono mb-1" style={{ color: "#60a5fa" }}>SCREENING ONLY</p>
            <p className="text-xs" style={{ color: "var(--text-primary)" }}>
              This public-data assessment ranks risk and evidence gaps; it is not an insurability or loss-probability determination.
            </p>
          </div>
        )}

        {/* Divider */}
        {isComplete && <hr className="orbital-divider my-2" />}

        {isPartial && (
          <div data-testid="partial-assessment-banner" className="data-card" style={{ borderColor: "rgba(245,158,11,0.25)", background: "rgba(245,158,11,0.06)" }}>
            <p className="label-mono mb-1" style={{ color: "#f59e0b" }}>PARTIAL ASSESSMENT</p>
            <p className="text-xs" style={{ color: "var(--text-primary)" }}>
              One or more evidence sources or pipeline stages degraded. Treat the underwriting result as triage only.
            </p>
          </div>
        )}

        {(requiredEvidenceGaps.length > 0 || unsupportedClaims.length > 0) && (
          <div className="data-card" data-testid="required-evidence-gaps-panel">
            <div className="flex items-center justify-between gap-3">
              <p className="label-mono">NEXT DATA NEEDED</p>
              <span className="font-mono-data text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                {requiredEvidenceGaps.length} gaps
              </span>
            </div>
            {requiredEvidenceGaps.length > 0 && (
              <div className="mt-3 space-y-2">
                {requiredEvidenceGaps.slice(0, 5).map((gap) => (
                  <div key={gap.id || gap.label} className="text-xs">
                    <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                      {(gap.label || gap.id || "Evidence").replace(/_/g, " ")}
                    </p>
                    {gap.description && (
                      <p className="mt-1" style={{ color: "var(--text-tertiary)" }}>{gap.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
            {unsupportedClaims.length > 0 && (
              <div className="mt-3 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                Blocked claims: {unsupportedClaims.slice(0, 3).map((claim) => claim.replace(/_/g, " ")).join(", ")}
              </div>
            )}
          </div>
        )}

        {(evidenceLoading || evidenceDetail || evidenceError) && (
          <div className="data-card" data-testid="analysis-evidence-panel">
            <div className="flex items-center justify-between gap-3">
              <p className="label-mono">EVIDENCE LINEAGE</p>
              {typeof evidenceDetail?.summary?.evidence_completeness_pct === "number" && (
                <span className="font-mono-data text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                  {evidenceDetail.summary.evidence_completeness_pct.toFixed(1)}% complete
                </span>
              )}
            </div>

            {evidenceLoading && !evidenceDetail && (
              <div className="mt-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                Loading evidence provenance…
              </div>
            )}

            {evidenceError && (
              <div className="mt-3 text-xs" style={{ color: "var(--severity-critical)" }}>
                {evidenceError}
              </div>
            )}

            {evidenceDetail && (
              <>
                <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                  <div>
                    <p style={{ color: "var(--text-tertiary)" }}>Linked Evidence</p>
                    <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                      {evidenceDetail.summary?.linked_evidence_count ?? evidenceDetail.items?.length ?? 0}
                    </p>
                  </div>
                  <div>
                    <p style={{ color: "var(--text-tertiary)" }}>Evidence Gaps</p>
                    <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                      {evidenceDetail.summary?.evidence_gaps?.length
                        ? evidenceDetail.summary.evidence_gaps.join(", ")
                        : "none"}
                    </p>
                  </div>
                </div>

                {evidenceDetail.summary?.evidence_quality && (
                  <div className="mt-3 rounded-md p-3" style={{ border: "1px solid var(--bg-panel-border)" }}>
                    <div className="flex items-center justify-between gap-3">
                      <p className="label-mono">SOURCE QUALITY</p>
                      {typeof evidenceDetail.summary.evidence_quality.quality_score === "number" && (
                        <span className="font-mono-data text-[11px]" style={{ color: "var(--text-secondary)" }}>
                          {evidenceDetail.summary.evidence_quality.quality_score.toFixed(1)} quality
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-3 text-[11px]">
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Missing</p>
                        <p className="font-mono-data" style={{ color: "var(--severity-warning)" }}>
                          {evidenceDetail.summary.evidence_quality.missing_required_sources?.length ?? 0}
                        </p>
                      </div>
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Failed</p>
                        <p className="font-mono-data" style={{ color: "var(--severity-critical)" }}>
                          {evidenceDetail.summary.evidence_quality.failed_source_count ?? 0}
                        </p>
                      </div>
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Low Confidence</p>
                        <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                          {evidenceDetail.summary.evidence_quality.low_confidence_count ?? 0}
                        </p>
                      </div>
                    </div>
                    {evidenceDetail.summary.evidence_quality.gaps?.length ? (
                      <div className="mt-3 space-y-1">
                        {evidenceDetail.summary.evidence_quality.gaps.slice(0, 4).map((gap) => (
                          <div key={`${gap.source}-${gap.status}-${gap.description}`} className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                            <span className="font-mono-data" style={{ color: "var(--text-secondary)" }}>{gap.source}</span>
                            {" "}
                            {gap.status.replace(/_/g, " ")}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}

                {evidenceDetail.summary?.counts_by_domain && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {Object.entries(evidenceDetail.summary.counts_by_domain).map(([domain, count]) => {
                      const style = DOMAIN_STYLES[domain] || DOMAIN_STYLES.unknown;
                      return (
                        <span
                          key={domain}
                          className="px-2 py-1 rounded-md text-[11px] font-mono-data"
                          style={{
                            color: style.color,
                            background: style.background,
                            border: `1px solid ${style.border}`,
                          }}
                        >
                          {DOMAIN_LABELS[domain] || titleize(domain)} · {count}
                        </span>
                      );
                    })}
                  </div>
                )}

                {evidenceDetail.summary?.sources_available?.length ? (
                  <div className="mt-3 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                    Runtime bundle: {evidenceDetail.summary.sources_available.join(", ")}
                  </div>
                ) : null}

                <div className="space-y-2 mt-4">
                  {(evidenceDetail.items || []).slice(0, 8).map((item) => {
                    const style = DOMAIN_STYLES[item.source_domain] || DOMAIN_STYLES.unknown;
                    const confidenceColor = CONFIDENCE_COLORS[item.confidence_bucket] || CONFIDENCE_COLORS.unknown;
                    return (
                      <div key={item.evidence_id} className="rounded-md p-3" style={{ border: "1px solid var(--bg-panel-border)" }}>
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-mono-display text-xs" style={{ color: "var(--text-primary)" }}>
                              {item.source_label}
                            </div>
                            <div className="text-[11px] mt-1" style={{ color: "var(--text-tertiary)" }}>
                              {item.used_for ? `Used for ${item.used_for.replace(/_/g, " ")}` : titleize(item.evidence_role)}
                              {item.provider ? ` · ${item.provider}` : ""}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 flex-wrap justify-end">
                            <span
                              className="px-2 py-1 rounded-md text-[11px] font-mono-data"
                              style={{
                                color: style.color,
                                background: style.background,
                                border: `1px solid ${style.border}`,
                              }}
                            >
                              {DOMAIN_LABELS[item.source_domain] || titleize(item.source_domain)}
                            </span>
                            <span className="text-[11px] font-mono-data" style={{ color: confidenceColor }}>
                              {titleize(item.confidence_bucket)}
                              {typeof item.confidence === "number" ? ` ${(item.confidence * 100).toFixed(0)}%` : ""}
                            </span>
                          </div>
                        </div>

                        {item.highlights?.length ? (
                          <div className="mt-2 text-[11px]" style={{ color: "var(--text-secondary)" }}>
                            {item.highlights.join(" · ")}
                          </div>
                        ) : null}

                        <div className="mt-2 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                          Captured: {safeDateTime(item.captured_at)} · Ingested: {safeDateTime(item.ingested_at)}
                        </div>
                        {item.source_url && (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-block mt-2 text-[11px] underline"
                            style={{ color: "var(--accent-orbital)" }}
                          >
                            Source provenance
                          </a>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}

        {evidenceDetail?.reference_profile && (
          <div className="data-card" data-testid="analysis-reference-profile-panel">
            <div className="flex items-center justify-between gap-3">
              <p className="label-mono">REFERENCE PROFILE</p>
              {evidenceDetail.reference_profile.last_verified_at && (
                <span className="font-mono-data text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                  Verified {safeDateTime(evidenceDetail.reference_profile.last_verified_at)}
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Operator</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {evidenceDetail.reference_profile.operator_name || "n/a"}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Manufacturer</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {evidenceDetail.reference_profile.manufacturer || "n/a"}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Mission Class</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {evidenceDetail.reference_profile.mission_class || "n/a"}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Orbit Regime</p>
                <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                  {evidenceDetail.reference_profile.orbit_regime || "n/a"}
                </p>
              </div>
            </div>

            {evidenceDetail.reference_profile.reference_sources_json?.length ? (
              <div className="mt-3 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                Sources: {evidenceDetail.reference_profile.reference_sources_json.join(", ")}
              </div>
            ) : null}
          </div>
        )}

        {/* Insurance Risk Report */}
        {isComplete && insurancePayload && (
          <InsuranceRiskCard report={insurancePayload} />
        )}

        {persistedAnalysis?.decision_summary && (
          <div className="data-card" data-testid="decision-summary-panel">
            <div className="flex items-center justify-between gap-3">
              <p className="label-mono">RECOMMENDED ACTION</p>
              <span className="font-mono-data text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                {persistedAnalysis.decision_status || "pending_policy"}
              </span>
            </div>

            {persistedAnalysis.decision_status === "pending_policy" && (
              <div className="mt-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                Decision post-processing is still finalizing. Review controls will appear once the deterministic policy pass completes.
              </div>
            )}

            {decisionLoading && persistedAnalysis?.decision_status === "pending_policy" && (
              <div className="mt-2 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                Refreshing analysis detail…
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Action</p>
                <p className="font-mono-display text-sm" style={{ color: "var(--text-primary)" }}>
                  {(persistedAnalysis.decision_summary.recommended_action || "blocked").replace(/_/g, " ").toUpperCase()}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Urgency</p>
                <p className="font-mono-data text-sm" style={{ color: "var(--text-primary)" }}>
                  {(persistedAnalysis.decision_summary.urgency || "routine").toUpperCase()}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Confidence</p>
                <p className="font-mono-data text-sm" style={{ color: "var(--text-primary)" }}>
                  {(persistedAnalysis.decision_summary.decision_confidence || "low").toUpperCase()}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-tertiary)" }}>Triage</p>
                <p className="font-mono-data text-sm" style={{ color: "var(--text-primary)" }}>
                  {persistedAnalysis.triage_band?.toUpperCase() || "ROUTINE"}
                  {typeof persistedAnalysis.triage_score === "number" ? ` · ${persistedAnalysis.triage_score.toFixed(2)}` : ""}
                </p>
              </div>
            </div>

            {persistedAnalysis.decision_summary.policy_recommended_action && (
              <div className="mt-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                Policy baseline: {persistedAnalysis.decision_summary.policy_recommended_action.replace(/_/g, " ")}
              </div>
            )}

            <p className="text-xs leading-relaxed mt-3" style={{ color: "var(--text-primary)" }}>
              {persistedAnalysis.decision_summary.decision_rationale || "Decision policy pending."}
            </p>

            {persistedAnalysis.decision_summary.blocked_reason && (
              <div className="mt-3 text-xs" style={{ color: "var(--severity-critical)" }}>
                Blocked: {persistedAnalysis.decision_summary.blocked_reason}
              </div>
            )}

            {persistedAnalysis.decision_summary.override_active && (
              <div className="mt-3 text-xs" style={{ color: "#f59e0b" }}>
                Override active
                {persistedAnalysis.decision_summary.override_reason_code ? ` · ${persistedAnalysis.decision_summary.override_reason_code}` : ""}
                {persistedAnalysis.decision_summary.override_reason ? ` · ${persistedAnalysis.decision_summary.override_reason}` : ""}
              </div>
            )}

            {decisionError && (
              <div className="mt-3 text-xs" data-testid="decision-error-message" style={{ color: "var(--severity-critical)" }}>
                {decisionError}
              </div>
            )}

            {persistedAnalysis.decision_status === "pending_human_review" && canReviewDecision && (
              <div className="flex gap-2 mt-4">
                <button
                  data-testid="decision-approve-button"
                  disabled={decisionBusy}
                  onClick={() => void handleDecisionReview("approve")}
                  className="px-3 py-2 rounded-md text-xs font-mono-display"
                  style={{ background: "rgba(34,197,94,0.12)", color: "#22c55e", border: "1px solid rgba(34,197,94,0.24)" }}
                >
                  APPROVE
                </button>
                <button
                  data-testid="decision-block-button"
                  disabled={decisionBusy}
                  onClick={() => void handleDecisionReview("block")}
                  className="px-3 py-2 rounded-md text-xs font-mono-display"
                  style={{ background: "rgba(239,68,68,0.08)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.18)" }}
                >
                  BLOCK
                </button>
                <button
                  data-testid="decision-reimage-button"
                  disabled={decisionBusy}
                  onClick={() => void handleDecisionReview("request_reimage")}
                  className="px-3 py-2 rounded-md text-xs font-mono-display"
                  style={{ background: "rgba(245,158,11,0.08)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.18)" }}
                >
                  REQUEST REIMAGE
                </button>
              </div>
            )}

            {persistedAnalysis.decision_status === "blocked" && canReviewDecision && (
              <div className="flex gap-2 mt-4">
                <button
                  data-testid="decision-reset-button"
                  disabled={decisionBusy}
                  onClick={() => void handleDecisionReview("reset_review", { comments: "Decision reset for renewed analyst review" })}
                  className="px-3 py-2 rounded-md text-xs font-mono-display"
                  style={{ background: "rgba(148,163,184,0.08)", color: "#cbd5e1", border: "1px solid rgba(148,163,184,0.18)" }}
                >
                  RESET REVIEW
                </button>
              </div>
            )}

            {canOverrideDecision && persistedAnalysis.decision_status !== "blocked" && (
              <div className="mt-4 rounded-md p-3" style={{ border: "1px solid rgba(245,158,11,0.18)", background: "rgba(245,158,11,0.04)" }}>
                <p className="label-mono mb-2" style={{ color: "#f59e0b" }}>ADMIN OVERRIDE</p>
                <p className="text-[11px] mb-3" style={{ color: "var(--text-tertiary)" }}>
                  Exception workflow. Override requires a reason code, written rationale, and is auditable against the policy recommendation.
                </p>
                <div className="grid grid-cols-3 gap-2">
                  <select
                    data-testid="decision-override-action-select"
                    value={overrideAction}
                    onChange={(e) => setOverrideAction(e.target.value)}
                    className="orbital-input font-mono-data text-xs"
                  >
                    {["continue_operations", "monitor", "reimage", "maneuver_review", "servicing_candidate", "insurance_escalation", "disposal_review"].map((action) => (
                      <option key={action} value={action}>{action.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                  <select
                    data-testid="decision-override-reason-code-select"
                    value={overrideReasonCode}
                    onChange={(e) => setOverrideReasonCode(e.target.value)}
                    className="orbital-input font-mono-data text-xs"
                  >
                    {["new_evidence", "mission_priority", "customer_policy", "operator_context", "temporary_exception"].map((code) => (
                      <option key={code} value={code}>{code.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                  <button
                    data-testid="decision-override-button"
                    disabled={decisionBusy || !overrideComments.trim()}
                    onClick={() => void handleDecisionReview("override_action", {
                      comments: overrideComments,
                      overrideAction,
                      reasonCode: overrideReasonCode,
                    })}
                    className="px-3 py-2 rounded-md text-xs font-mono-display"
                    style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.24)" }}
                  >
                    APPLY OVERRIDE
                  </button>
                </div>
                <textarea
                  data-testid="decision-override-comments-input"
                  value={overrideComments}
                  onChange={(e) => setOverrideComments(e.target.value)}
                  placeholder="State the operational reason, evidence delta, and why the policy recommendation is being superseded."
                  className="orbital-input w-full font-mono-data min-h-[88px] resize-none mt-2"
                />
                {!overrideComments.trim() && (
                  <div className="mt-2 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                    Enter a written rationale to enable override.
                  </div>
                )}
              </div>
            )}

            {persistedAnalysis.decision_status === "approved_for_use" && persistedAnalysis.decision_approved_at && (
              <div className="mt-3 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                Approved for use by {persistedAnalysis.decision_approved_by || "reviewer"} at {new Date(persistedAnalysis.decision_approved_at).toLocaleString()}
              </div>
            )}
          </div>
        )}

        {/* Risk Matrix Drilldown */}
        {isComplete && insurancePayload?.risk_matrix && (
          <Suspense fallback={<div className="text-xs text-center py-4" style={{ color: "var(--text-tertiary)" }}>Loading visualization...</div>}>
            <RiskMatrixDrilldown
              riskMatrix={insurancePayload.risk_matrix}
              riskTier={insurancePayload.risk_tier ?? "UNKNOWN"}
            />
          </Suspense>
        )}

        {/* Degradation Timeline */}
        {isComplete && (classificationPayload || failureModePayload) && (
          <Suspense fallback={<div className="text-xs text-center py-4" style={{ color: "var(--text-tertiary)" }}>Loading timeline...</div>}>
            <DegradationTimeline
              designLifeYears={classificationPayload?.design_life_years ?? null}
              estimatedAgeYears={classificationPayload?.estimated_age_years ?? null}
              remainingLifeYears={insurancePayload?.estimated_remaining_life_years ?? null}
              powerMarginPct={insurancePayload?.power_margin_percentage ?? null}
              annualDegradationPct={insurancePayload?.annual_degradation_rate_pct ?? null}
              damages={((state.agents.satellite_vision.payload as Record<string, unknown>)?.damages as Array<{ type: string; severity: string }>) ?? []}
            />
          </Suspense>
        )}

        {/* Download Report Button */}
        {isComplete && (
          <button
            onClick={handleDownloadReport}
            data-testid="download-report-button"
            disabled={pdfLoading}
            className="w-full py-3 rounded-md font-mono-display text-xs tracking-[0.15em] transition-all flex items-center justify-center gap-2"
            style={{
              background: pdfLoading ? "rgba(255,255,255,0.03)" : "linear-gradient(135deg, #22c55e, #059669)",
              color: pdfLoading ? "var(--text-tertiary)" : "#ffffff",
              cursor: pdfLoading ? "wait" : "pointer",
              boxShadow: pdfLoading ? "none" : "0 0 20px rgba(34,197,94,0.15)",
              border: "1px solid rgba(34,197,94,0.2)",
            }}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            {pdfLoading ? "GENERATING..." : "DOWNLOAD CONDITION REPORT"}
          </button>
        )}

        {/* Idle state */}
        {state.analysisStatus === "idle" && (
          <div className="flex flex-col items-center justify-center h-full gap-4 py-16">
            <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"
              style={{ color: "var(--text-tertiary)", opacity: 0.4 }}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={0.8}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div className="text-center">
              <p className="font-mono-display text-xs tracking-wider" style={{ color: "var(--text-tertiary)" }}>
                NO ACTIVE ASSESSMENT
              </p>
              <p className="text-xs mt-1.5" style={{ color: "var(--text-tertiary)", opacity: 0.6 }}>
                Upload satellite imagery to generate a Condition Report
              </p>
            </div>
          </div>
        )}

        {/* Error state */}
        {state.analysisStatus === "failed" && (
          <div data-testid="analysis-failed-banner" className="data-card" style={{ borderColor: "rgba(239,68,68,0.2)", background: "rgba(239,68,68,0.05)" }}>
            <p className="label-mono mb-1" style={{ color: "var(--severity-critical)" }}>ASSESSMENT FAILED</p>
            <p className="text-xs" style={{ color: "var(--text-primary)" }}>
              {derivedFailureMessage || "An unexpected error occurred."}
            </p>
          </div>
        )}

        {state.analysisStatus === "rejected" && (
          <div data-testid="analysis-rejected-banner" className="data-card" style={{ borderColor: "rgba(245,158,11,0.2)", background: "rgba(245,158,11,0.05)" }}>
            <p className="label-mono mb-1" style={{ color: "#f59e0b" }}>TARGET REJECTED</p>
            <p className="text-xs" style={{ color: "var(--text-primary)" }}>
              {derivedFailureMessage || "The uploaded imagery was rejected as non-satellite or unsupported."}
            </p>
          </div>
        )}

        {/* Elapsed timer */}
        {state.analysisStatus === "analyzing" && (
          <div className="text-center pt-2">
            <span className="font-mono-display text-xs" style={{ color: "var(--accent-scan)" }}>
              T+{state.elapsedTime}s
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
