import type { InsuranceRiskReport, UnderwritingRecommendation } from "../../types";

const UW_STYLES: Record<UnderwritingRecommendation, { cls: string; label: string }> = {
  INSURABLE_STANDARD:        { cls: "uw-standard",    label: "INSURABLE — STANDARD TERMS" },
  INSURABLE_ELEVATED_PREMIUM:{ cls: "uw-elevated",    label: "INSURABLE — ELEVATED PREMIUM" },
  INSURABLE_WITH_EXCLUSIONS: { cls: "uw-exclusions",  label: "INSURABLE — WITH EXCLUSIONS" },
  FURTHER_INVESTIGATION:     { cls: "uw-investigate",  label: "FURTHER INVESTIGATION REQUIRED" },
  UNINSURABLE:               { cls: "uw-uninsurable",  label: "UNINSURABLE" },
};

const TIER_COLORS: Record<string, string> = {
  CRITICAL: "var(--severity-critical)",
  HIGH: "var(--severity-severe)",
  "MEDIUM-HIGH": "var(--severity-moderate)",
  MEDIUM: "var(--severity-moderate)",
  LOW: "var(--severity-healthy)",
};

function formatUSD(value: number | null): string {
  if (value === null) return "—";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function scoreColor(score: number): string {
  if (score >= 4) return "var(--severity-critical)";
  if (score >= 3) return "var(--severity-moderate)";
  return "var(--severity-healthy)";
}

interface Props {
  report: InsuranceRiskReport;
}

export default function InsuranceRiskCard({ report }: Props) {
  const tierColor = TIER_COLORS[report.risk_tier] || "var(--text-secondary)";
  const isHighRisk = report.risk_tier === "CRITICAL" || report.risk_tier === "HIGH";
  const uwStyle = UW_STYLES[report.underwriting_recommendation] || UW_STYLES.FURTHER_INVESTIGATION;

  return (
    <div className="flex flex-col gap-4 font-body">

      {/* Underwriting Recommendation — THE MONEY SHOT */}
      <div className={`uw-badge text-center ${uwStyle.cls}`}>
        {uwStyle.label}
      </div>

      {/* Risk Tier */}
      <div className={`rounded-lg p-4 text-center ${isHighRisk ? (report.risk_tier === "CRITICAL" ? "risk-glow-critical" : "risk-glow-high") : ""}`}
        style={{
          background: `${tierColor}0C`,
          border: `1px solid ${tierColor}30`,
        }}>
        <p className="font-mono-display text-xl tracking-wider" style={{ color: tierColor }}>
          {report.risk_tier}
        </p>
        <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
          COMPOSITE: {report.risk_matrix.composite} / 125
        </p>
      </div>

      {/* Risk Matrix */}
      <div>
        <p className="label-mono mb-2">RISK MATRIX</p>
        <div className="grid grid-cols-3 gap-2">
          {(["severity", "probability", "consequence"] as const).map((dim) => {
            const d = report.risk_matrix[dim];
            return (
              <div key={dim} className="data-card text-center">
                <p className="font-mono-display text-lg" style={{ color: scoreColor(d.score) }}>{d.score}</p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>/5</p>
                <p className="label-mono mt-1" style={{ fontSize: "0.5rem" }}>{dim.slice(0, 4).toUpperCase()}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Insurance Metrics — the data underwriters need */}
      <div>
        <p className="label-mono mb-2">INSURANCE METRICS</p>
        <div className="grid grid-cols-2 gap-2">
          {[
            { label: "REMAINING LIFE", value: report.estimated_remaining_life_years != null ? `${report.estimated_remaining_life_years.toFixed(1)} yr` : "—" },
            { label: "POWER MARGIN", value: report.power_margin_percentage != null ? `${report.power_margin_percentage.toFixed(1)}%` : "—" },
            { label: "ANNUAL DEGRAD", value: report.annual_degradation_rate_pct != null ? `${report.annual_degradation_rate_pct.toFixed(2)}%/yr` : "—" },
            { label: "LOSS PROB", value: report.total_loss_probability != null ? `${(report.total_loss_probability * 100).toFixed(1)}%` : "—" },
          ].map((m) => (
            <div key={m.label} className="data-card">
              <p className="label-mono" style={{ fontSize: "0.5rem" }}>{m.label}</p>
              <p className="font-mono-data text-sm mt-1">{m.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Financial Exposure */}
      {(report.replacement_cost_usd || report.revenue_at_risk_annual_usd) && (
        <div>
          <p className="label-mono mb-2">FINANCIAL EXPOSURE</p>
          <div className="space-y-2">
            {report.replacement_cost_usd && (
              <div className="data-card flex items-center justify-between">
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>Replacement Cost</span>
                <span className="money-large money-negative">{formatUSD(report.replacement_cost_usd)}</span>
              </div>
            )}
            {report.depreciated_value_usd && (
              <div className="data-card flex items-center justify-between">
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>Depreciated Value</span>
                <span className="text-money text-sm">{formatUSD(report.depreciated_value_usd)}</span>
              </div>
            )}
            {report.revenue_at_risk_annual_usd && (
              <div className="data-card flex items-center justify-between">
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>Revenue at Risk /yr</span>
                <span className="money-large" style={{ color: "var(--text-warning)" }}>{formatUSD(report.revenue_at_risk_annual_usd)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Consistency Check */}
      <div className="data-card flex items-center gap-2"
        style={{
          borderColor: report.consistency_check.passed ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)",
        }}>
        <span className="font-mono-display text-xs"
          style={{ color: report.consistency_check.passed ? "var(--severity-healthy)" : "var(--severity-critical)" }}>
          {report.consistency_check.passed ? "CONSISTENCY PASSED" : "ANOMALIES DETECTED"}
        </span>
      </div>

      {/* Summary */}
      {report.summary && (
        <div>
          <p className="label-mono mb-1.5">ASSESSMENT SUMMARY</p>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-primary)" }}>{report.summary}</p>
        </div>
      )}

      {/* Worst Case */}
      {report.worst_case_scenario && (
        <div className="data-card" style={{ borderColor: "rgba(239,68,68,0.15)", background: "rgba(239,68,68,0.03)" }}>
          <p className="label-mono mb-1" style={{ color: "var(--severity-critical)" }}>WORST CASE</p>
          <p className="text-xs leading-relaxed italic" style={{ color: "var(--text-primary)" }}>{report.worst_case_scenario}</p>
        </div>
      )}
    </div>
  );
}
