/**
 * Fleet health summary — key metrics at a glance.
 * Top row of the portfolio dashboard.
 */

interface FleetSummaryProps {
  totalSatellites: number;
  riskDistribution: Record<string, number>;
  underwritingDistribution: Record<string, number>;
}

const TIER_COLORS: Record<string, string> = {
  LOW: "#22c55e",
  MEDIUM: "#eab308",
  "MEDIUM-HIGH": "#f97316",
  HIGH: "#ef4444",
  CRITICAL: "#ef4444",
};

export default function FleetSummary({ totalSatellites, riskDistribution, underwritingDistribution }: FleetSummaryProps) {
  const insurable = (underwritingDistribution["INSURABLE_STANDARD"] || 0) +
                    (underwritingDistribution["INSURABLE_ELEVATED_PREMIUM"] || 0);
  const atRisk = (underwritingDistribution["INSURABLE_WITH_EXCLUSIONS"] || 0) +
                 (underwritingDistribution["FURTHER_INVESTIGATION"] || 0) +
                 (underwritingDistribution["UNINSURABLE"] || 0);

  return (
    <div className="grid grid-cols-4 gap-3">
      {/* Total */}
      <div className="glass-panel rounded-lg p-4 text-center">
        <div className="font-mono-display text-2xl" style={{ color: "var(--accent-orbital)" }}>
          {totalSatellites}
        </div>
        <div className="label-mono mt-1">SATELLITES</div>
      </div>

      {/* Insurable */}
      <div className="glass-panel rounded-lg p-4 text-center">
        <div className="font-mono-display text-2xl" style={{ color: "#22c55e" }}>
          {insurable}
        </div>
        <div className="label-mono mt-1">INSURABLE</div>
      </div>

      {/* At Risk */}
      <div className="glass-panel rounded-lg p-4 text-center">
        <div className="font-mono-display text-2xl" style={{ color: "#ef4444" }}>
          {atRisk}
        </div>
        <div className="label-mono mt-1">AT RISK</div>
      </div>

      {/* Risk Tiers */}
      <div className="glass-panel rounded-lg p-4">
        <div className="label-mono mb-2">RISK DISTRIBUTION</div>
        <div className="flex gap-1 h-4 rounded overflow-hidden">
          {Object.entries(riskDistribution).map(([tier, count]) => (
            <div
              key={tier}
              style={{
                flex: count,
                background: TIER_COLORS[tier] || "#666",
                minWidth: count > 0 ? 4 : 0,
              }}
              title={`${tier}: ${count}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
