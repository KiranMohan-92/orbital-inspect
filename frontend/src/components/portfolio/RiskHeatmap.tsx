/**
 * Visual heatmap showing risk distribution across the fleet.
 * Each cell represents a satellite, colored by risk tier.
 */

interface RiskHeatmapProps {
  satellites: Array<{
    norad_id: string | null;
    risk_tier: string;
    composite_score: number | null;
  }>;
}

const TIER_COLORS: Record<string, string> = {
  LOW: "#22c55e",
  MEDIUM: "#eab308",
  "MEDIUM-HIGH": "#f97316",
  HIGH: "#ef4444",
  CRITICAL: "#ef4444",
  UNKNOWN: "#333",
};

export default function RiskHeatmap({ satellites }: RiskHeatmapProps) {
  // Sort by composite score descending (highest risk first)
  const sorted = [...satellites].sort((a, b) =>
    (b.composite_score ?? 0) - (a.composite_score ?? 0)
  );

  return (
    <div className="glass-panel rounded-lg p-4">
      <div className="label-mono mb-3">FLEET RISK HEATMAP</div>
      <div className="flex flex-wrap gap-1">
        {sorted.map((sat, i) => (
          <div
            key={sat.norad_id || i}
            className="w-8 h-8 rounded-sm flex items-center justify-center text-xs font-mono-data transition-all hover:scale-110 cursor-pointer"
            style={{
              background: `${TIER_COLORS[sat.risk_tier] || "#333"}20`,
              border: `1px solid ${TIER_COLORS[sat.risk_tier] || "#333"}40`,
              color: TIER_COLORS[sat.risk_tier] || "#666",
            }}
            title={`${sat.norad_id || "?"} — ${sat.risk_tier} (${sat.composite_score ?? "?"})`}
          >
            {sat.composite_score ?? "?"}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-3 mt-3 pt-2" style={{ borderTop: "1px solid var(--bg-panel-border)" }}>
        {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map(tier => (
          <div key={tier} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-sm" style={{ background: TIER_COLORS[tier] }} />
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>{tier}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
