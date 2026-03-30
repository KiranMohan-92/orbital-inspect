/**
 * Individual satellite health card for the portfolio grid.
 */

interface SatelliteData {
  norad_id: string | null;
  analysis_id: string;
  risk_tier: string;
  underwriting: string;
  composite_score: number | null;
  classification: Record<string, unknown>;
  completed_at: string | null;
}

interface SatelliteCardProps {
  satellite: SatelliteData;
}

const TIER_COLORS: Record<string, string> = {
  LOW: "#22c55e",
  MEDIUM: "#eab308",
  "MEDIUM-HIGH": "#f97316",
  HIGH: "#ef4444",
  CRITICAL: "#ef4444",
  UNKNOWN: "#666",
};

export default function SatelliteCard({ satellite }: SatelliteCardProps) {
  const color = TIER_COLORS[satellite.risk_tier] || "#666";
  const satType = (satellite.classification?.satellite_type as string) || "unknown";
  const regime = (satellite.classification?.orbital_regime as string) || "";
  const operator = (satellite.classification?.operator as string) || "";

  return (
    <div
      className="glass-panel rounded-lg p-4 transition-all hover:scale-[1.01] cursor-pointer"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="font-mono-display text-sm" style={{ color: "var(--text-primary)" }}>
            {satellite.norad_id ? `#${satellite.norad_id}` : satellite.analysis_id.slice(0, 8)}
          </div>
          <div className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {satType.replace("_", " ")} · {regime}
          </div>
        </div>
        <span
          className="text-xs font-mono-display px-2 py-0.5 rounded"
          style={{
            color,
            background: `${color}15`,
            border: `1px solid ${color}30`,
          }}
        >
          {satellite.risk_tier}
        </span>
      </div>

      {operator && (
        <div className="text-xs mb-2" style={{ color: "var(--text-secondary)" }}>
          {operator}
        </div>
      )}

      <div className="flex items-center justify-between">
        <span className="font-mono-data text-xs">
          {satellite.composite_score != null ? `${satellite.composite_score}/125` : "—"}
        </span>
        <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          {satellite.completed_at
            ? new Date(satellite.completed_at).toLocaleDateString()
            : "pending"}
        </span>
      </div>
    </div>
  );
}
