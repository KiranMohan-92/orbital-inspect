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

  useEffect(() => {
    void fetchPortfolio();
  }, [fetchPortfolio]);

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

  const satellites = portfolio?.satellites ?? [];

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
                <SatelliteCard key={sat.analysis_id} satellite={sat} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
