/**
 * Portfolio monitoring dashboard — fleet-level satellite health overview.
 * Bloomberg Terminal-tier visualization of satellite insurance portfolio.
 */

import { useState, useEffect } from "react";
import FleetSummary from "./FleetSummary";
import SatelliteCard from "./SatelliteCard";
import RiskHeatmap from "./RiskHeatmap";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface PortfolioData {
  satellites: Array<{
    norad_id: string | null;
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
  }>;
  total: number;
}

interface SummaryData {
  total_analyses: number;
  completed: number;
  risk_distribution: Record<string, number>;
  underwriting_distribution: Record<string, number>;
}

export default function PortfolioView() {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");

  useEffect(() => {
    async function fetchData() {
      try {
        const [portfolioRes, summaryRes] = await Promise.all([
          fetch(`${API_BASE}/api/portfolio`),
          fetch(`${API_BASE}/api/portfolio/summary`),
        ]);

        if (portfolioRes.ok) setPortfolio(await portfolioRes.json());
        if (summaryRes.ok) setSummary(await summaryRes.json());
      } catch (e) {
        console.error("Failed to fetch portfolio data", e);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

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

  const satellites = (portfolio?.satellites ?? []).filter((sat) => {
    const statusMatch = statusFilter === "all" || sat.status === statusFilter;
    const riskMatch = riskFilter === "all" || sat.risk_tier === riskFilter;
    return statusMatch && riskMatch;
  });

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
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto dark-scrollbar p-6 space-y-4">
        {/* Fleet Summary */}
        {summary && (
          <FleetSummary
            totalSatellites={satellites.length}
            riskDistribution={summary.risk_distribution}
            underwritingDistribution={summary.underwriting_distribution}
          />
        )}

        <div className="flex items-center gap-3">
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
        </div>

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
