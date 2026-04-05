/**
 * Individual satellite health card for the portfolio grid.
 */

interface SatelliteData {
  asset_name?: string | null;
  asset_external_id?: string | null;
  asset_identity_source?: string | null;
  operator_name?: string | null;
  norad_id: string | null;
  subsystem_key?: string | null;
  analysis_id: string;
  status: string;
  risk_tier: string;
  underwriting: string;
  composite_score: number | null;
  classification: Record<string, unknown>;
  completed_at: string | null;
  recommended_action?: string | null;
  decision_status?: string;
  urgency?: string | null;
  decision_blocked_reason?: string | null;
  decision_approved_by?: string | null;
  decision_approved_at?: string | null;
  decision_override_reason?: string | null;
  decision_summary?: {
    override_active?: boolean;
    override_reason_code?: string | null;
    override_reason?: string | null;
    blocked_reason?: string | null;
  };
  triage_score?: number | null;
  recurrence_count?: number;
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
  const operator = satellite.operator_name || (satellite.classification?.operator as string) || "";

  return (
    <div
      data-testid="portfolio-satellite-card"
      className="glass-panel rounded-lg p-4 transition-all hover:scale-[1.01] cursor-pointer"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="font-mono-display text-sm" style={{ color: "var(--text-primary)" }}>
            {satellite.asset_name || (satellite.norad_id ? `#${satellite.norad_id}` : satellite.analysis_id.slice(0, 8))}
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

      {(satellite.asset_external_id || satellite.subsystem_key || satellite.asset_identity_source) && (
        <div className="text-[11px] mb-2" style={{ color: "var(--text-tertiary)" }}>
          {[satellite.asset_external_id, satellite.subsystem_key, satellite.asset_identity_source].filter(Boolean).join(" · ")}
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

      <div className="flex items-center justify-between mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
        <span>{(satellite.recommended_action || "blocked").replace(/_/g, " ")}</span>
        <span>{(satellite.urgency || "routine").toUpperCase()}</span>
      </div>
      <div className="flex items-center justify-between mt-1 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
        <span>{satellite.decision_status || satellite.status}</span>
        <span>
          {typeof satellite.triage_score === "number" ? `Triage ${satellite.triage_score.toFixed(2)}` : "Triage —"}
          {satellite.recurrence_count ? ` · x${satellite.recurrence_count}` : ""}
        </span>
      </div>
      {(satellite.decision_summary?.override_active || satellite.decision_approved_by || satellite.decision_blocked_reason) && (
        <div className="mt-2 text-[11px]" style={{ color: "var(--text-tertiary)" }}>
          {satellite.decision_summary?.override_active
            ? `Override active${satellite.decision_summary.override_reason_code ? ` · ${satellite.decision_summary.override_reason_code}` : ""}`
            : satellite.decision_approved_by
              ? `Approved by ${satellite.decision_approved_by}${satellite.decision_approved_at ? ` · ${new Date(satellite.decision_approved_at).toLocaleString()}` : ""}`
              : satellite.decision_blocked_reason
                ? `Blocked · ${satellite.decision_blocked_reason}`
                : ""}
        </div>
      )}
    </div>
  );
}
