/**
 * Fleet health overview panel showing degradation trends across the portfolio.
 * Summary stats, average velocity, and top 5 worst-trending assets.
 */

export interface FleetHealthMapProps {
  fleetTrends: {
    total_assets_analyzed: number;
    worst_trending: Array<{
      asset_id: string;
      asset_name: string | null;
      norad_id: string | null;
      current_score: number;
      predicted_score_30d: number;
      slope_per_day: number;
      trend_direction: string;
      degradation_velocity: string;
      days_to_threshold: number | null;
    }>;
    fleet_avg_slope: number;
    assets_degrading: number;
    assets_stable: number;
    assets_improving: number;
  } | null;
  loading: boolean;
}

const VELOCITY_STYLES: Record<string, { color: string; background: string; border: string }> = {
  stable: {
    color: "#22c55e",
    background: "rgba(34,197,94,0.12)",
    border: "rgba(34,197,94,0.22)",
  },
  slow: {
    color: "#eab308",
    background: "rgba(234,179,8,0.12)",
    border: "rgba(234,179,8,0.22)",
  },
  moderate: {
    color: "#f97316",
    background: "rgba(249,115,22,0.12)",
    border: "rgba(249,115,22,0.22)",
  },
  rapid: {
    color: "#ef4444",
    background: "rgba(239,68,68,0.12)",
    border: "rgba(239,68,68,0.22)",
  },
  critical: {
    color: "#ef4444",
    background: "rgba(239,68,68,0.18)",
    border: "rgba(239,68,68,0.35)",
  },
};

function trendArrow(direction: string): string {
  switch (direction) {
    case "degrading":
      return "\u2191"; // up arrow (score increasing = worse)
    case "improving":
      return "\u2193"; // down arrow (score decreasing = better)
    default:
      return "\u2192"; // right arrow (stable)
  }
}

function trendArrowColor(direction: string): string {
  switch (direction) {
    case "degrading":
      return "#ef4444";
    case "improving":
      return "#22c55e";
    default:
      return "#eab308";
  }
}

export default function FleetHealthMap({ fleetTrends, loading }: FleetHealthMapProps) {
  if (loading && !fleetTrends) {
    return (
      <div className="data-card">
        <p className="label-mono breathe" style={{ color: "var(--accent-orbital)" }}>
          LOADING FLEET TRENDS
        </p>
      </div>
    );
  }

  if (!fleetTrends) {
    return (
      <div className="data-card">
        <p className="label-mono">FLEET DEGRADATION TRENDS</p>
        <p className="text-xs mt-2" style={{ color: "var(--text-tertiary)" }}>
          No trend data available. Run multiple analyses over time to generate trends.
        </p>
      </div>
    );
  }

  const avgSlopeDisplay = fleetTrends.fleet_avg_slope >= 0
    ? `+${fleetTrends.fleet_avg_slope.toFixed(3)}`
    : fleetTrends.fleet_avg_slope.toFixed(3);

  return (
    <div className="data-card">
      <p className="label-mono mb-3">FLEET DEGRADATION TRENDS</p>

      {/* Summary stats */}
      <div className="grid grid-cols-5 gap-3 mb-4">
        {[
          { label: "ANALYZED", value: fleetTrends.total_assets_analyzed, color: "var(--text-primary)" },
          { label: "DEGRADING", value: fleetTrends.assets_degrading, color: "#ef4444" },
          { label: "STABLE", value: fleetTrends.assets_stable, color: "#eab308" },
          { label: "IMPROVING", value: fleetTrends.assets_improving, color: "#22c55e" },
          { label: "AVG VELOCITY", value: avgSlopeDisplay, color: fleetTrends.fleet_avg_slope > 0 ? "#ef4444" : "#22c55e" },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-md p-2 text-center"
            style={{ border: "1px solid var(--bg-panel-border)" }}
          >
            <p className="text-[10px] font-mono-display" style={{ color: "var(--text-tertiary)", letterSpacing: "0.1em" }}>
              {item.label}
            </p>
            <p className="font-mono-data text-sm mt-1" style={{ color: item.color }}>
              {item.value}
            </p>
          </div>
        ))}
      </div>

      {/* Worst trending assets */}
      {fleetTrends.worst_trending.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-2">
            <p className="label-mono">WORST TRENDING ASSETS</p>
            <span className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
              top {Math.min(5, fleetTrends.worst_trending.length)} by degradation rate
            </span>
          </div>
          <div className="space-y-2">
            {fleetTrends.worst_trending.slice(0, 5).map((asset, idx) => {
              const velStyle = VELOCITY_STYLES[asset.degradation_velocity] || VELOCITY_STYLES.stable;
              return (
                <div
                  key={asset.asset_id}
                  className="flex items-center justify-between gap-3 rounded-md px-3 py-2"
                  style={{ border: "1px solid var(--bg-panel-border)" }}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-5 h-5 rounded-sm flex items-center justify-center text-[10px] font-mono-display"
                      style={{ color: "var(--text-tertiary)", background: "rgba(255,255,255,0.03)" }}
                    >
                      {idx + 1}
                    </div>
                    <div>
                      <div className="font-mono-display text-xs" style={{ color: "var(--text-primary)" }}>
                        {asset.asset_name || (asset.norad_id ? `#${asset.norad_id}` : asset.asset_id.slice(0, 8))}
                      </div>
                      {asset.norad_id && (
                        <div className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                          NORAD {asset.norad_id}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {/* Score trajectory */}
                    <div className="text-right">
                      <div className="font-mono-data text-xs">
                        <span style={{ color: "var(--text-primary)" }}>{asset.current_score.toFixed(1)}</span>
                        <span style={{ color: trendArrowColor(asset.trend_direction), margin: "0 4px" }}>
                          {trendArrow(asset.trend_direction)}
                        </span>
                        <span style={{ color: "var(--text-secondary)" }}>{asset.predicted_score_30d.toFixed(1)}</span>
                      </div>
                      {asset.days_to_threshold !== null && (
                        <div className="text-[10px]" style={{ color: "#ef4444" }}>
                          {asset.days_to_threshold}d to threshold
                        </div>
                      )}
                    </div>

                    {/* Velocity badge */}
                    <span
                      className="px-2 py-1 rounded-md text-[10px] font-mono-data whitespace-nowrap"
                      style={{
                        color: velStyle.color,
                        background: velStyle.background,
                        border: `1px solid ${velStyle.border}`,
                      }}
                    >
                      {asset.degradation_velocity.toUpperCase()}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
