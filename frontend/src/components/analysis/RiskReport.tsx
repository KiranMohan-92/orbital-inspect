import type { PriorityReport } from "../../types";

const TIER_COLORS: Record<string, string> = {
  CRITICAL: "var(--severity-critical)",
  HIGH: "var(--severity-severe)",
  "MEDIUM-HIGH": "var(--severity-moderate)",
  MEDIUM: "var(--severity-moderate)",
  LOW: "var(--severity-healthy)",
};

const PRIORITY_COLORS: Record<string, string> = {
  IMMEDIATE: "var(--priority-immediate)",
  URGENT: "var(--priority-urgent)",
  SCHEDULED: "var(--priority-scheduled)",
  MONITOR: "var(--priority-monitor)",
};

function scoreColor(score: number): string {
  if (score >= 4) return "var(--severity-critical)";
  if (score >= 3) return "var(--severity-moderate)";
  return "var(--severity-healthy)";
}

interface RiskReportProps {
  report: PriorityReport;
}

export default function RiskReport({ report }: RiskReportProps) {
  const tierColor = TIER_COLORS[report.risk_tier] || "var(--text-secondary)";
  const isHighRisk = report.risk_tier === "CRITICAL" || report.risk_tier === "HIGH";

  return (
    <div className="flex flex-col gap-4 font-body">
      {/* Risk Tier Badge */}
      <div
        className={`rounded-xl p-4 text-center ${isHighRisk ? (report.risk_tier === "CRITICAL" ? "risk-glow-critical" : "risk-glow-high") : ""}`}
        style={{
          background: `color-mix(in srgb, ${tierColor} 12%, transparent)`,
          border: `1px solid color-mix(in srgb, ${tierColor} 30%, transparent)`,
        }}
      >
        <p
          className="font-mono-display text-2xl tracking-wider"
          style={{ color: tierColor }}
        >
          {report.risk_tier}
        </p>
        <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
          COMPOSITE SCORE: {report.risk_matrix.composite} / 125
        </p>
      </div>

      {/* Risk Matrix */}
      <div>
        <p className="label-mono mb-2" style={{ color: "var(--text-secondary)" }}>
          RISK MATRIX
        </p>
        <div className="grid grid-cols-3 gap-2">
          {(["severity", "probability", "consequence"] as const).map((dim) => {
            const d = report.risk_matrix[dim];
            return (
              <div
                key={dim}
                className="rounded-lg p-3 text-center"
                style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--bg-panel-border)",
                }}
              >
                <p
                  className="font-mono-display text-xl"
                  style={{ color: scoreColor(d.score) }}
                >
                  {d.score}
                </p>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                  /5
                </p>
                <p
                  className="label-mono mt-1.5"
                  style={{ color: "var(--text-secondary)", fontSize: "0.55rem" }}
                >
                  {dim.toUpperCase()}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Consistency Check */}
      <div
        className="rounded-lg px-3 py-2.5 flex items-center gap-2"
        style={{
          background: report.consistency_check.passed
            ? "rgba(0, 230, 118, 0.06)"
            : "rgba(255, 23, 68, 0.06)",
          border: `1px solid ${
            report.consistency_check.passed
              ? "rgba(0, 230, 118, 0.2)"
              : "rgba(255, 23, 68, 0.2)"
          }`,
        }}
      >
        <span
          className="font-mono-display text-xs"
          style={{
            color: report.consistency_check.passed
              ? "var(--severity-healthy)"
              : "var(--severity-critical)",
          }}
        >
          {report.consistency_check.passed ? "CONSISTENCY: PASSED" : "ANOMALIES DETECTED"}
        </span>
      </div>

      {report.consistency_check.anomalies.length > 0 && (
        <div className="space-y-1 px-1">
          {report.consistency_check.anomalies.map((a, i) => (
            <p key={i} className="text-xs" style={{ color: "var(--severity-moderate)" }}>
              {a}
            </p>
          ))}
        </div>
      )}

      {/* Summary */}
      {report.summary && (
        <div>
          <p className="label-mono mb-1.5" style={{ color: "var(--text-secondary)" }}>
            ASSESSMENT
          </p>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-primary)" }}>
            {report.summary}
          </p>
        </div>
      )}

      {/* Recommended Actions */}
      {report.recommended_actions.length > 0 && (
        <div>
          <p className="label-mono mb-2" style={{ color: "var(--text-secondary)" }}>
            RECOMMENDED ACTIONS
          </p>
          <div className="space-y-2">
            {report.recommended_actions.map((action, i) => {
              const pColor = PRIORITY_COLORS[action.priority] || "var(--text-secondary)";
              return (
                <div
                  key={i}
                  className="rounded-lg px-3 py-2.5"
                  style={{
                    borderLeft: `3px solid ${pColor}`,
                    background: "rgba(255,255,255,0.02)",
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="font-mono-display text-xs"
                      style={{ color: pColor, fontSize: "0.6rem" }}
                    >
                      {action.priority}
                    </span>
                    <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {action.timeline}
                    </span>
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-primary)" }}>
                    {action.action}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Worst Case Scenario */}
      {report.worst_case_scenario && (
        <div
          className="rounded-lg p-3"
          style={{
            background: "rgba(255, 23, 68, 0.05)",
            border: "1px solid rgba(255, 23, 68, 0.15)",
          }}
        >
          <p className="label-mono mb-1.5" style={{ color: "var(--severity-critical)" }}>
            WORST CASE SCENARIO
          </p>
          <p
            className="text-xs leading-relaxed italic"
            style={{ color: "var(--text-primary)" }}
          >
            {report.worst_case_scenario}
          </p>
        </div>
      )}
    </div>
  );
}
