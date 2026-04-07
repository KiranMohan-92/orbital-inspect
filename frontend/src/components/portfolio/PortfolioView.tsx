/**
 * Portfolio monitoring dashboard — fleet-level satellite health overview.
 * Bloomberg Terminal-tier visualization of satellite insurance portfolio.
 */

import { useState, useEffect, useCallback } from "react";
import FleetSummary from "./FleetSummary";
import SatelliteCard from "./SatelliteCard";
import RiskHeatmap from "./RiskHeatmap";
import { apiFetch } from "../../utils/api";

interface PortfolioData {
  satellites: Array<{
    asset_id?: string | null;
    asset_name?: string | null;
    asset_external_id?: string | null;
    asset_identity_source?: string | null;
    operator_name?: string | null;
    norad_id: string | null;
    subsystem_key?: string | null;
    analysis_id: string;
    status: string;
    asset_type?: string;
    degraded?: boolean;
    risk_tier: string;
    underwriting: string;
    composite_score: number | null;
    classification: Record<string, unknown>;
    completed_at: string | null;
    report_completeness: string;
    evidence_completeness_pct?: number | null;
    decision_status?: string;
    recommended_action?: string | null;
    urgency?: string | null;
    decision_blocked_reason?: string | null;
    decision_approved_by?: string | null;
    decision_approved_at?: string | null;
    decision_override_reason?: string | null;
    decision_last_evaluated_at?: string | null;
    decision_summary?: {
      override_active?: boolean;
      override_reason_code?: string | null;
      override_reason?: string | null;
      blocked_reason?: string | null;
    };
    triage_score?: number | null;
    triage_band?: string | null;
    recurrence_count?: number;
  }>;
  total: number;
}

interface SummaryData {
  total_assets?: number;
  total_analyses: number;
  completed: number;
  risk_distribution: Record<string, number>;
  underwriting_distribution: Record<string, number>;
  decision_distribution?: Record<string, number>;
  recommended_action_distribution?: Record<string, number>;
  urgency_distribution?: Record<string, number>;
  open_attention_queue?: number;
  urgent_assets?: number;
  approved_assets?: number;
}

interface AssetDetailData {
  asset: {
    asset_id: string;
    asset_type?: string;
    name?: string | null;
    norad_id?: string | null;
    external_asset_id?: string | null;
    identity_source?: string | null;
    operator_name?: string | null;
    status?: string | null;
    current_analysis_id?: string | null;
    updated_at?: string | null;
  };
  aliases?: Array<{
    alias_type: string;
    alias_value: string;
    is_primary?: boolean;
  }>;
  reference_profile?: {
    operator_name?: string | null;
    manufacturer?: string | null;
    mission_class?: string | null;
    orbit_regime?: string | null;
    reference_revision?: string | null;
    reference_sources_json?: string[];
    last_verified_at?: string | null;
  } | null;
  evidence_summary?: {
    total_records?: number;
    counts_by_role?: Record<string, number>;
    counts_by_domain?: Record<string, number>;
    providers?: string[];
    latest_captured_at?: string | null;
  };
  recent_evidence?: Array<{
    evidence_id: string;
    source_label: string;
    source_domain: string;
    evidence_role: string;
    confidence_bucket: string;
    confidence?: number | null;
    captured_at?: string | null;
    highlights?: string[];
  }>;
  current_analysis?: {
    analysis_id: string;
    status?: string;
    recommended_action?: string | null;
    decision_status?: string | null;
    triage_score?: number | null;
    triage_band?: string | null;
    evidence_completeness_pct?: number | null;
    completed_at?: string | null;
  } | null;
}

interface AssetTimelineData {
  analyses: Array<{
    analysis_id: string;
    status: string;
    inspection_epoch?: string | null;
    target_subsystem?: string | null;
    subsystem_key?: string | null;
    risk_tier?: string | null;
    recommended_action?: string | null;
    decision_status?: string | null;
    triage_score?: number | null;
    triage_band?: string | null;
    evidence_completeness_pct?: number | null;
    report_completeness?: string | null;
    degraded?: boolean;
    completed_at?: string | null;
    created_at?: string | null;
  }>;
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

function titleize(value: string | null | undefined): string {
  if (!value) return "n/a";
  return value.replace(/_/g, " ").replace(/-/g, " ");
}

function safeDateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export default function PortfolioView() {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [decisionFilter, setDecisionFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [urgencyFilter, setUrgencyFilter] = useState("all");
  const [degradedOnly, setDegradedOnly] = useState(false);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [assetDetail, setAssetDetail] = useState<AssetDetailData | null>(null);
  const [assetTimeline, setAssetTimeline] = useState<AssetTimelineData | null>(null);
  const [assetDetailLoading, setAssetDetailLoading] = useState(false);

  const fetchSummary = useCallback(async () => {
    const summaryRes = await apiFetch("/api/portfolio/summary");
    if (summaryRes.ok) {
      setSummary(await summaryRes.json());
    }
  }, []);

  const fetchPortfolio = useCallback(async () => {
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (riskFilter !== "all") params.set("risk_tier", riskFilter);
    if (decisionFilter !== "all") params.set("decision_status", decisionFilter);
    if (actionFilter !== "all") params.set("recommended_action", actionFilter);
    if (urgencyFilter !== "all") params.set("urgency", urgencyFilter);
    if (degradedOnly) params.set("degraded_only", "true");
    const path = params.size > 0 ? `/api/portfolio?${params.toString()}` : "/api/portfolio";
    const portfolioRes = await apiFetch(path);
    if (portfolioRes.ok) {
      setPortfolio(await portfolioRes.json());
    }
  }, [actionFilter, decisionFilter, degradedOnly, riskFilter, statusFilter, urgencyFilter]);

  const refreshPortfolioSurface = useCallback(async (withLoading: boolean) => {
    if (withLoading) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    try {
      await Promise.all([fetchPortfolio(), fetchSummary()]);
    } catch (e) {
      console.error("Failed to fetch portfolio data", e);
    } finally {
      if (withLoading) {
        setLoading(false);
      } else {
        setRefreshing(false);
      }
    }
  }, [fetchPortfolio, fetchSummary]);

  useEffect(() => {
    void refreshPortfolioSurface(true);
  }, [refreshPortfolioSurface]);

  const satellites = portfolio?.satellites ?? [];

  useEffect(() => {
    const availableIds = satellites
      .map((sat) => sat.asset_id)
      .filter((value): value is string => Boolean(value));

    if (!availableIds.length) {
      setSelectedAssetId(null);
      setAssetDetail(null);
      setAssetTimeline(null);
      return;
    }

    if (!selectedAssetId || !availableIds.includes(selectedAssetId)) {
      setSelectedAssetId(availableIds[0]);
    }
  }, [satellites, selectedAssetId]);

  useEffect(() => {
    if (!selectedAssetId) {
      setAssetDetail(null);
      setAssetTimeline(null);
      return;
    }

    let cancelled = false;
    async function fetchAssetContext() {
      setAssetDetailLoading(true);
      try {
        const [detailRes, timelineRes] = await Promise.all([
          apiFetch(`/api/assets/${selectedAssetId}`),
          apiFetch(`/api/assets/${selectedAssetId}/timeline?limit=8`),
        ]);
        if (!detailRes.ok || !timelineRes.ok) {
          return;
        }
        const [detailPayload, timelinePayload] = await Promise.all([
          detailRes.json() as Promise<AssetDetailData>,
          timelineRes.json() as Promise<AssetTimelineData>,
        ]);
        if (!cancelled) {
          setAssetDetail(detailPayload);
          setAssetTimeline(timelinePayload);
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to fetch asset context", error);
        }
      } finally {
        if (!cancelled) {
          setAssetDetailLoading(false);
        }
      }
    }

    void fetchAssetContext();
    return () => {
      cancelled = true;
    };
  }, [selectedAssetId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="label-mono breathe" style={{ color: "var(--accent-orbital)" }}>
            LOADING PORTFOLIO
          </div>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="portfolio-view" className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 flex-shrink-0" style={{ borderBottom: "1px solid var(--bg-panel-border)" }}>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--accent-orbital)" }} />
          <h2 className="font-mono-display text-sm tracking-[0.15em]" style={{ color: "var(--text-primary)" }}>
            PORTFOLIO MONITOR
          </h2>
          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {satellites.length} satellite{satellites.length !== 1 ? "s" : ""}
          </span>
          <button
            data-testid="portfolio-refresh-button"
            onClick={() => void refreshPortfolioSurface(false)}
            className="ml-auto px-3 py-1.5 rounded-md text-xs font-mono-display"
            style={{ border: "1px solid var(--bg-panel-border)", color: "var(--text-primary)" }}
          >
            {refreshing ? "REFRESHING" : "REFRESH"}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto dark-scrollbar p-6 space-y-4">
        {/* Fleet Summary */}
        {summary && (
          <FleetSummary
            totalSatellites={summary.total_assets ?? satellites.length}
            riskDistribution={summary.risk_distribution}
            underwritingDistribution={summary.underwriting_distribution}
          />
        )}

        {summary && (
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "OPEN ATTENTION", value: summary.open_attention_queue ?? 0 },
              { label: "URGENT ASSETS", value: summary.urgent_assets ?? 0 },
              { label: "APPROVED", value: summary.approved_assets ?? 0 },
              { label: "PENDING REVIEW", value: summary.decision_distribution?.pending_human_review ?? 0 },
            ].map((item) => (
              <div key={item.label} className="data-card">
                <p className="label-mono">{item.label}</p>
                <p className="font-mono-display text-lg mt-2" style={{ color: "var(--text-primary)" }}>
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3 flex-wrap">
          <select
            data-testid="portfolio-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="orbital-input font-mono-data text-xs"
          >
            <option value="all">All statuses</option>
            <option value="completed">Completed</option>
            <option value="completed_partial">Partial</option>
            <option value="failed">Failed</option>
            <option value="rejected">Rejected</option>
            <option value="running">Running</option>
          </select>
          <select
            data-testid="portfolio-risk-filter"
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="orbital-input font-mono-data text-xs"
          >
            <option value="all">All risk tiers</option>
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="MEDIUM-HIGH">MEDIUM-HIGH</option>
            <option value="HIGH">HIGH</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="UNKNOWN">UNKNOWN</option>
          </select>
          <select
            data-testid="portfolio-decision-filter"
            value={decisionFilter}
            onChange={(e) => setDecisionFilter(e.target.value)}
            className="orbital-input font-mono-data text-xs"
          >
            <option value="all">All decisions</option>
            <option value="pending_human_review">Pending Review</option>
            <option value="approved_for_use">Approved</option>
            <option value="blocked">Blocked</option>
            <option value="pending_policy">Pending Policy</option>
          </select>
          <select
            data-testid="portfolio-action-filter"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="orbital-input font-mono-data text-xs"
          >
            <option value="all">All actions</option>
            <option value="continue_operations">Continue operations</option>
            <option value="monitor">Monitor</option>
            <option value="reimage">Reimage</option>
            <option value="maneuver_review">Maneuver review</option>
            <option value="servicing_candidate">Servicing candidate</option>
            <option value="insurance_escalation">Insurance escalation</option>
            <option value="disposal_review">Disposal review</option>
          </select>
          <select
            data-testid="portfolio-urgency-filter"
            value={urgencyFilter}
            onChange={(e) => setUrgencyFilter(e.target.value)}
            className="orbital-input font-mono-data text-xs"
          >
            <option value="all">All urgency</option>
            <option value="urgent">Urgent</option>
            <option value="priority">Priority</option>
            <option value="routine">Routine</option>
          </select>
          <label className="flex items-center gap-2 text-xs" style={{ color: "var(--text-tertiary)" }}>
            <input
              data-testid="portfolio-degraded-only-toggle"
              type="checkbox"
              checked={degradedOnly}
              onChange={(e) => setDegradedOnly(e.target.checked)}
            />
            Degraded only
          </label>
        </div>

        {satellites.length > 0 && (
          <div className="data-card">
            <div className="flex items-center justify-between mb-3">
              <p className="label-mono">OPERATOR TRIAGE QUEUE</p>
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                ranked by persisted triage score
              </span>
            </div>
            <div className="space-y-2">
              {satellites.slice(0, 5).map((sat) => (
                <div key={`triage-${sat.analysis_id}`} className="flex items-center justify-between gap-3 rounded-md px-3 py-2" style={{ border: "1px solid var(--bg-panel-border)" }}>
                  <div>
                    <div className="font-mono-display text-xs" style={{ color: "var(--text-primary)" }}>
                      {sat.asset_name || (sat.norad_id ? `#${sat.norad_id}` : sat.analysis_id.slice(0, 8))}
                    </div>
                    <div className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {(sat.recommended_action || "blocked").replace(/_/g, " ")} · {sat.decision_status || "pending_policy"}
                    </div>
                    {(sat.decision_summary?.override_active || sat.decision_approved_by || sat.decision_blocked_reason) && (
                      <div className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                        {sat.decision_summary?.override_active
                          ? `override${sat.decision_summary.override_reason_code ? ` · ${sat.decision_summary.override_reason_code}` : ""}`
                          : sat.decision_approved_by
                            ? `approved by ${sat.decision_approved_by}`
                            : sat.decision_blocked_reason
                              ? `blocked · ${sat.decision_blocked_reason}`
                              : ""}
                      </div>
                    )}
                    {(sat.asset_external_id || sat.subsystem_key) && (
                      <div className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                        {[sat.asset_external_id, sat.subsystem_key].filter(Boolean).join(" · ")}
                      </div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="font-mono-data text-xs" style={{ color: "var(--text-primary)" }}>
                      {(sat.urgency || "routine").toUpperCase()}
                    </div>
                    <div className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {typeof sat.triage_score === "number" ? sat.triage_score.toFixed(2) : "—"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Risk Heatmap */}
        {satellites.length > 0 && <RiskHeatmap satellites={satellites} />}

        {selectedAssetId && (
          <div className="data-card" data-testid="portfolio-asset-detail-panel">
            <div className="flex items-center justify-between gap-3">
              <p className="label-mono">ASSET CONTEXT</p>
              {assetDetail?.asset?.updated_at && (
                <span className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                  Updated {safeDateTime(assetDetail.asset.updated_at)}
                </span>
              )}
            </div>

            {assetDetailLoading && !assetDetail && (
              <div className="mt-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                Loading asset context…
              </div>
            )}

            {assetDetail && (
              <>
                <div className="grid grid-cols-4 gap-3 mt-3 text-xs">
                  <div>
                    <p style={{ color: "var(--text-tertiary)" }}>Asset</p>
                    <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                      {assetDetail.asset.name || "n/a"}
                    </p>
                  </div>
                  <div>
                    <p style={{ color: "var(--text-tertiary)" }}>NORAD</p>
                    <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                      {assetDetail.asset.norad_id || "n/a"}
                    </p>
                  </div>
                  <div>
                    <p style={{ color: "var(--text-tertiary)" }}>Identity</p>
                    <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                      {titleize(assetDetail.asset.identity_source)}
                    </p>
                  </div>
                  <div>
                    <p style={{ color: "var(--text-tertiary)" }}>Current Analysis</p>
                    <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                      {assetDetail.current_analysis?.analysis_id || assetDetail.asset.current_analysis_id || "n/a"}
                    </p>
                  </div>
                </div>

                {assetDetail.aliases?.length ? (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {assetDetail.aliases.slice(0, 6).map((alias) => (
                      <span
                        key={`${alias.alias_type}-${alias.alias_value}`}
                        className="px-2 py-1 rounded-md text-[11px] font-mono-data"
                        style={{
                          color: alias.is_primary ? "#ffffff" : "var(--text-secondary)",
                          background: alias.is_primary ? "rgba(77,124,255,0.18)" : "rgba(255,255,255,0.04)",
                          border: `1px solid ${alias.is_primary ? "rgba(77,124,255,0.28)" : "var(--bg-panel-border)"}`,
                        }}
                      >
                        {titleize(alias.alias_type)} · {alias.alias_value}
                      </span>
                    ))}
                  </div>
                ) : null}

                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="rounded-md p-3" style={{ border: "1px solid var(--bg-panel-border)" }}>
                    <p className="label-mono">REFERENCE PROFILE</p>
                    <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Operator</p>
                        <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                          {assetDetail.reference_profile?.operator_name || assetDetail.asset.operator_name || "n/a"}
                        </p>
                      </div>
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Manufacturer</p>
                        <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                          {assetDetail.reference_profile?.manufacturer || "n/a"}
                        </p>
                      </div>
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Mission</p>
                        <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                          {assetDetail.reference_profile?.mission_class || "n/a"}
                        </p>
                      </div>
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Orbit</p>
                        <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                          {assetDetail.reference_profile?.orbit_regime || "n/a"}
                        </p>
                      </div>
                    </div>
                    {assetDetail.reference_profile?.reference_sources_json?.length ? (
                      <div className="mt-3 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                        Sources: {assetDetail.reference_profile.reference_sources_json.join(", ")}
                      </div>
                    ) : (
                      <div className="mt-3 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                        No reference profile persisted yet.
                      </div>
                    )}
                  </div>

                  <div className="rounded-md p-3" style={{ border: "1px solid var(--bg-panel-border)" }}>
                    <p className="label-mono">EVIDENCE SUMMARY</p>
                    <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Records</p>
                        <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                          {assetDetail.evidence_summary?.total_records ?? 0}
                        </p>
                      </div>
                      <div>
                        <p style={{ color: "var(--text-tertiary)" }}>Latest Capture</p>
                        <p className="font-mono-data" style={{ color: "var(--text-primary)" }}>
                          {safeDateTime(assetDetail.evidence_summary?.latest_captured_at)}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 mt-3">
                      {Object.entries(assetDetail.evidence_summary?.counts_by_domain || {}).map(([domain, count]) => {
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
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="rounded-md p-3" style={{ border: "1px solid var(--bg-panel-border)" }}>
                    <p className="label-mono">RECENT EVIDENCE</p>
                    <div className="space-y-2 mt-3">
                      {(assetDetail.recent_evidence || []).slice(0, 6).map((item) => {
                        const style = DOMAIN_STYLES[item.source_domain] || DOMAIN_STYLES.unknown;
                        return (
                          <div key={item.evidence_id} className="rounded-md px-3 py-2" style={{ border: "1px solid var(--bg-panel-border)" }}>
                            <div className="flex items-center justify-between gap-3">
                              <div className="font-mono-display text-xs" style={{ color: "var(--text-primary)" }}>
                                {item.source_label}
                              </div>
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
                            </div>
                            {item.highlights?.length ? (
                              <div className="mt-1 text-[11px]" style={{ color: "var(--text-secondary)" }}>
                                {item.highlights.join(" · ")}
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="rounded-md p-3" style={{ border: "1px solid var(--bg-panel-border)" }}>
                    <p className="label-mono">ANALYSIS TIMELINE</p>
                    <div className="space-y-2 mt-3">
                      {(assetTimeline?.analyses || []).map((entry) => (
                        <div key={entry.analysis_id} className="rounded-md px-3 py-2" style={{ border: "1px solid var(--bg-panel-border)" }}>
                          <div className="flex items-center justify-between gap-3">
                            <div className="font-mono-display text-xs" style={{ color: "var(--text-primary)" }}>
                              {entry.analysis_id}
                            </div>
                            <div className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                              {entry.risk_tier || "UNKNOWN"}
                            </div>
                          </div>
                          <div className="mt-1 text-[11px]" style={{ color: "var(--text-secondary)" }}>
                            {(entry.recommended_action || "blocked").replace(/_/g, " ")} · {entry.decision_status || entry.status}
                          </div>
                          <div className="mt-1 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                            {entry.subsystem_key || entry.target_subsystem || "asset-wide"} · {safeDateTime(entry.completed_at || entry.created_at)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* Satellite Grid */}
        <div>
          <div className="label-mono mb-3">ASSESSED SATELLITES</div>
          {satellites.length === 0 ? (
            <div className="glass-panel rounded-lg p-8 text-center">
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                No satellites assessed yet. Run an analysis to populate the portfolio.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {satellites.map((sat) => (
                <SatelliteCard
                  key={sat.analysis_id}
                  satellite={sat}
                  selected={Boolean(sat.asset_id && sat.asset_id === selectedAssetId)}
                  onSelect={sat.asset_id ? () => setSelectedAssetId(sat.asset_id as string) : undefined}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
