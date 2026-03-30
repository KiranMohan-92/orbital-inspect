import { useEffect, useRef } from "react";
import type { SatelliteDamageItem } from "../../types";

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  SEVERE: "#f97316",
  MODERATE: "#eab308",
  MINOR: "#84cc16",
};

export interface DamageDetailPopoverProps {
  damage: SatelliteDamageItem;
  position: { x: number; y: number };
  onClose: () => void;
}

function formatDamageType(raw: string): string {
  return raw
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DamageDetailPopover({
  damage,
  position,
  onClose,
}: DamageDetailPopoverProps) {
  const ref = useRef<HTMLDivElement>(null);

  // Adjust position so popover stays within viewport
  const POPOVER_W = 280;
  const POPOVER_H = 220;
  const OFFSET = 12;

  // Start from click position, nudge if near edges
  let left = position.x + OFFSET;
  let top = position.y + OFFSET;

  if (ref.current) {
    const parent = ref.current.parentElement?.getBoundingClientRect();
    if (parent) {
      if (left + POPOVER_W > parent.width - 8) left = position.x - POPOVER_W - OFFSET;
      if (top + POPOVER_H > parent.height - 8) top = position.y - POPOVER_H - OFFSET;
    }
  }

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const color = SEVERITY_COLORS[damage.severity?.toUpperCase()] || SEVERITY_COLORS.MODERATE;
  const confidencePct = Math.round(damage.confidence * 100);
  const powerImpact = damage.estimated_power_impact_pct ?? 0;

  const confidenceColor =
    confidencePct >= 80 ? "#22c55e" : confidencePct >= 60 ? "#eab308" : "#f97316";

  return (
    <div
      ref={ref}
      onClick={(e) => e.stopPropagation()}
      style={{
        position: "absolute",
        left,
        top,
        zIndex: 50,
        minWidth: 240,
        maxWidth: 320,
        background: "rgba(8,10,20,0.92)",
        backdropFilter: "blur(20px) saturate(130%)",
        border: "1px solid rgba(100,120,255,0.15)",
        borderRadius: 8,
        overflow: "hidden",
        boxShadow: "0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(77,124,255,0.06)",
        animation: "popoverSlideIn 0.16s ease forwards",
      }}
    >
      <style>{`
        @keyframes popoverSlideIn {
          from { opacity: 0; transform: translateY(8px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>

      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 12px 8px",
          borderBottom: "1px solid rgba(100,120,255,0.08)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          {/* Severity dot */}
          <div
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: color,
              boxShadow: `0 0 6px ${color}80`,
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              fontWeight: 700,
              color: "var(--text-primary)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {formatDamageType(damage.type)}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 7, flexShrink: 0 }}>
          {/* Severity badge */}
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 8,
              fontWeight: 700,
              color,
              background: `${color}18`,
              border: `1px solid ${color}40`,
              borderRadius: 3,
              padding: "2px 6px",
              letterSpacing: "0.1em",
            }}
          >
            {damage.severity}
          </span>

          {/* Close button */}
          <button
            onClick={onClose}
            style={{
              width: 20,
              height: 20,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(100,120,255,0.10)",
              borderRadius: 4,
              cursor: "pointer",
              color: "var(--text-tertiary)",
              transition: "all 0.12s ease",
              padding: 0,
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(100,120,255,0.25)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.color = "var(--text-tertiary)";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(100,120,255,0.10)";
            }}
          >
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
              <path d="M1 1l6 6M7 1L1 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Details grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 1,
          padding: "10px 12px",
          borderBottom: "1px solid rgba(100,120,255,0.08)",
        }}
      >
        {/* Confidence */}
        <div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 9,
              color: "var(--text-tertiary)",
              letterSpacing: "0.1em",
              marginBottom: 3,
            }}
          >
            CONFIDENCE
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div
              style={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: confidenceColor,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 13,
                fontWeight: 700,
                color: confidenceColor,
              }}
            >
              {confidencePct}%
            </span>
          </div>
        </div>

        {/* Power impact */}
        <div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 9,
              color: "var(--text-tertiary)",
              letterSpacing: "0.1em",
              marginBottom: 3,
            }}
          >
            PWR IMPACT
          </div>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              fontWeight: 700,
              color: powerImpact > 3 ? "var(--severity-severe)" : "var(--text-data)",
            }}
          >
            {powerImpact > 0 ? `-${powerImpact.toFixed(1)}%` : "—"}
          </span>
        </div>

        {/* Label */}
        <div style={{ marginTop: 8 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 9,
              color: "var(--text-tertiary)",
              letterSpacing: "0.1em",
              marginBottom: 3,
            }}
          >
            LABEL
          </div>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--text-secondary)",
            }}
          >
            {damage.label}
          </span>
        </div>

        {/* Uncertain flag */}
        <div style={{ marginTop: 8 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 9,
              color: "var(--text-tertiary)",
              letterSpacing: "0.1em",
              marginBottom: 3,
            }}
          >
            UNCERTAIN
          </div>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: damage.uncertain ? "#eab308" : "#22c55e",
            }}
          >
            {damage.uncertain ? "YES" : "NO"}
          </span>
        </div>
      </div>

      {/* Description */}
      {damage.description && (
        <div style={{ padding: "10px 12px" }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 9,
              color: "var(--text-tertiary)",
              letterSpacing: "0.1em",
              marginBottom: 5,
            }}
          >
            DESCRIPTION
          </div>
          <p
            style={{
              fontSize: 11,
              color: "var(--text-secondary)",
              lineHeight: 1.55,
              margin: 0,
            }}
          >
            {damage.description}
          </p>
        </div>
      )}
    </div>
  );
}
