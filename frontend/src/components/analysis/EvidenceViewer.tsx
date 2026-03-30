import { useState, useRef, useCallback } from "react";
import { TransformWrapper, TransformComponent, useControls } from "react-zoom-pan-pinch";
import type { SatelliteDamageItem } from "../../types";
import DamageDetailPopover from "./DamageDetailPopover";

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  SEVERE: "#f97316",
  MODERATE: "#eab308",
  MINOR: "#84cc16",
};

const SEVERITY_GLOW: Record<string, string> = {
  CRITICAL: "rgba(239,68,68,0.4)",
  SEVERE: "rgba(249,115,22,0.4)",
  MODERATE: "rgba(234,179,8,0.4)",
  MINOR: "rgba(132,204,22,0.4)",
};

export interface EvidenceViewerProps {
  imageUrl: string;
  damages: SatelliteDamageItem[];
  overallSeverity: string;
  totalPowerImpact: number;
  componentAssessed: string;
  showAnnotations: boolean;
  onToggleAnnotations: () => void;
  onDamageSelect?: (damage: SatelliteDamageItem) => void;
}

interface PopoverState {
  damage: SatelliteDamageItem;
  position: { x: number; y: number };
}

// ─── Zoom Controls Toolbar ────────────────────────────────────────────────────
function ZoomControls({ scale }: { scale: number }) {
  const { zoomIn, zoomOut, resetTransform, centerView } = useControls();

  const btnStyle: React.CSSProperties = {
    width: 28,
    height: 28,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg-panel)",
    border: "1px solid rgba(100,120,255,0.12)",
    borderRadius: 5,
    color: "var(--text-secondary)",
    cursor: "pointer",
    fontSize: 14,
    transition: "all 0.15s ease",
    backdropFilter: "blur(12px)",
    flexShrink: 0,
  };

  return (
    <div
      style={{
        position: "absolute",
        top: 10,
        right: 10,
        zIndex: 30,
        display: "flex",
        flexDirection: "column",
        gap: 4,
        alignItems: "center",
        background: "rgba(8,10,20,0.82)",
        backdropFilter: "blur(16px) saturate(120%)",
        border: "1px solid rgba(100,120,255,0.10)",
        borderRadius: 8,
        padding: "6px 5px",
      }}
    >
      {/* Zoom level display */}
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 9,
          color: "var(--accent-scan)",
          letterSpacing: "0.08em",
          marginBottom: 2,
          userSelect: "none",
        }}
      >
        {scale.toFixed(1)}x
      </div>

      <button
        style={btnStyle}
        title="Zoom in"
        onClick={() => zoomIn(0.5)}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--accent-orbital)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(77,124,255,0.35)";
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(77,124,255,0.08)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(100,120,255,0.12)";
          (e.currentTarget as HTMLButtonElement).style.background = "var(--bg-panel)";
        }}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M6 2v8M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>

      <button
        style={btnStyle}
        title="Zoom out"
        onClick={() => zoomOut(0.5)}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--accent-orbital)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(77,124,255,0.35)";
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(77,124,255,0.08)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(100,120,255,0.12)";
          (e.currentTarget as HTMLButtonElement).style.background = "var(--bg-panel)";
        }}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>

      {/* Divider */}
      <div style={{ width: 16, height: 1, background: "rgba(100,120,255,0.12)", margin: "1px 0" }} />

      <button
        style={btnStyle}
        title="Fit to view"
        onClick={() => centerView(1)}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--accent-orbital)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(77,124,255,0.35)";
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(77,124,255,0.08)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(100,120,255,0.12)";
          (e.currentTarget as HTMLButtonElement).style.background = "var(--bg-panel)";
        }}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <rect x="1" y="1" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2" />
          <rect x="7" y="1" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2" />
          <rect x="1" y="7" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2" />
          <rect x="7" y="7" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.2" />
        </svg>
      </button>

      <button
        style={btnStyle}
        title="Reset view"
        onClick={() => resetTransform()}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--accent-scan)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(0,212,255,0.35)";
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(0,212,255,0.06)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(100,120,255,0.12)";
          (e.currentTarget as HTMLButtonElement).style.background = "var(--bg-panel)";
        }}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path
            d="M2 6a4 4 0 1 1 1.2 2.8"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
            fill="none"
          />
          <path d="M1 9V6.5h2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
      </button>
    </div>
  );
}

// ─── Damage Bounding Boxes (inside TransformComponent) ───────────────────────
interface DamageBoxesProps {
  damages: SatelliteDamageItem[];
  visible: boolean;
  selectedId: number | null;
  onBoxClick: (damage: SatelliteDamageItem, e: React.MouseEvent) => void;
}

function DamageBoxes({ damages, visible, selectedId, onBoxClick }: DamageBoxesProps) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  if (!visible) return null;

  return (
    <>
      {damages.map((damage) => {
        const [yMin, xMin, yMax, xMax] = damage.bounding_box;
        const left = xMin / 10; // convert 0-1000 → 0-100%
        const top = yMin / 10;
        const width = (xMax - xMin) / 10;
        const height = (yMax - yMin) / 10;

        if (width <= 0 || height <= 0) return null;

        const color = SEVERITY_COLORS[damage.severity] || SEVERITY_COLORS.MODERATE;
        const glow = SEVERITY_GLOW[damage.severity] || SEVERITY_GLOW.MODERATE;
        const isHovered = hoveredId === damage.id;
        const isSelected = selectedId === damage.id;
        const isUncertain = damage.uncertain;

        return (
          <div
            key={damage.id}
            onClick={(e) => { e.stopPropagation(); onBoxClick(damage, e); }}
            onMouseEnter={() => setHoveredId(damage.id)}
            onMouseLeave={() => setHoveredId(null)}
            style={{
              position: "absolute",
              left: `${left}%`,
              top: `${top}%`,
              width: `${width}%`,
              height: `${height}%`,
              border: `${isSelected ? 2.5 : isHovered ? 2 : 1.5}px ${isUncertain ? "dashed" : "solid"} ${color}`,
              background: isHovered || isSelected ? `${color}22` : `${color}0d`,
              cursor: "pointer",
              transition: "all 0.15s ease",
              boxShadow: isSelected
                ? `0 0 0 1px ${color}60, 0 0 12px ${glow}`
                : isHovered
                ? `0 0 8px ${glow}`
                : "none",
              borderRadius: 2,
            }}
          >
            {/* Label tag */}
            <div
              style={{
                position: "absolute",
                top: "calc(-100% - 2px)",
                left: 0,
                whiteSpace: "nowrap",
                fontFamily: "var(--font-mono)",
                fontSize: "clamp(8px, 0.8vw, 11px)",
                fontWeight: 700,
                color: "#000",
                background: color,
                padding: "1px 5px",
                borderRadius: "3px 3px 3px 0",
                pointerEvents: "none",
                opacity: isHovered || isSelected ? 1 : 0.85,
                transition: "opacity 0.15s ease",
                lineHeight: 1.6,
              }}
            >
              {isUncertain ? "? " : ""}{damage.label} — {Math.round(damage.confidence * 100)}%
            </div>
          </div>
        );
      })}
    </>
  );
}

// ─── Main EvidenceViewer ──────────────────────────────────────────────────────
export default function EvidenceViewer({
  imageUrl,
  damages,
  overallSeverity,
  totalPowerImpact,
  componentAssessed,
  showAnnotations,
  onToggleAnnotations,
  onDamageSelect,
}: EvidenceViewerProps) {
  const [scale, setScale] = useState(1);
  const [popover, setPopover] = useState<PopoverState | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleBoxClick = useCallback(
    (damage: SatelliteDamageItem, e: React.MouseEvent) => {
      const containerRect = containerRef.current?.getBoundingClientRect();
      if (!containerRect) return;

      const x = e.clientX - containerRect.left;
      const y = e.clientY - containerRect.top;

      setSelectedId(damage.id);
      setPopover({ damage, position: { x, y } });
      onDamageSelect?.(damage);
    },
    [onDamageSelect]
  );

  const handleClosePopover = useCallback(() => {
    setPopover(null);
    setSelectedId(null);
  }, []);

  const severityColor =
    SEVERITY_COLORS[overallSeverity?.toUpperCase()] || "var(--text-secondary)";

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        position: "relative",
        overflow: "hidden",
        background: "var(--bg-void)",
        display: "flex",
        flexDirection: "column",
      }}
      onClick={handleClosePopover}
    >
      {/* Pan/Zoom wrapper */}
      <TransformWrapper
        initialScale={1}
        minScale={0.5}
        maxScale={8}
        doubleClick={{ mode: "toggle", step: 2 }}
        wheel={{ step: 0.12 }}
        pinch={{ step: 8 }}
        onTransformed={(_ref, state) => setScale(state.scale)}
        centerOnInit
      >
        {({ instance }) => (
          <>
            {/* Zoom controls — reads scale from outer state */}
            <ZoomControls scale={scale} />

            <TransformComponent
              wrapperStyle={{
                width: "100%",
                height: "100%",
                cursor: "crosshair",
              }}
              contentStyle={{
                position: "relative",
                display: "inline-block",
              }}
            >
              <img
                src={imageUrl}
                alt="Satellite target"
                draggable={false}
                style={{
                  display: "block",
                  maxWidth: "100%",
                  maxHeight: "100%",
                  userSelect: "none",
                }}
              />

              {/* Bounding boxes scale with the image inside TransformComponent */}
              {damages.length > 0 && (
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    pointerEvents: showAnnotations ? "auto" : "none",
                  }}
                >
                  <DamageBoxes
                    damages={damages}
                    visible={showAnnotations}
                    selectedId={selectedId}
                    onBoxClick={handleBoxClick}
                  />
                </div>
              )}
            </TransformComponent>

            {/* Suppress unused variable warning for instance */}
            {instance && null}
          </>
        )}
      </TransformWrapper>

      {/* Bottom info bar */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 20,
          display: "flex",
          alignItems: "center",
          gap: 0,
          background: "rgba(8,10,20,0.85)",
          backdropFilter: "blur(16px) saturate(120%)",
          borderTop: "1px solid rgba(100,120,255,0.08)",
          padding: "7px 12px",
        }}
      >
        {/* Component assessed */}
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--accent-scan)",
            letterSpacing: "0.14em",
            marginRight: 16,
          }}
        >
          {componentAssessed?.toUpperCase() || "COMPONENT"}
        </div>

        {/* Separator */}
        <div style={{ width: 1, height: 14, background: "rgba(100,120,255,0.15)", marginRight: 16 }} />

        {/* Damage count */}
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            color: "var(--text-secondary)",
            letterSpacing: "0.1em",
            marginRight: 16,
          }}
        >
          {damages.length} ANOMAL{damages.length !== 1 ? "IES" : "Y"}
        </div>

        {/* Severity badge */}
        {overallSeverity && (
          <>
            <div style={{ width: 1, height: 14, background: "rgba(100,120,255,0.15)", marginRight: 16 }} />
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 9,
                fontWeight: 700,
                color: severityColor,
                background: `${severityColor}18`,
                border: `1px solid ${severityColor}40`,
                borderRadius: 4,
                padding: "2px 7px",
                letterSpacing: "0.12em",
                marginRight: 16,
              }}
            >
              {overallSeverity.toUpperCase()}
            </div>
          </>
        )}

        {/* Power impact */}
        {totalPowerImpact > 0 && (
          <>
            <div style={{ width: 1, height: 14, background: "rgba(100,120,255,0.15)", marginRight: 16 }} />
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                color:
                  totalPowerImpact > 10
                    ? "var(--severity-critical)"
                    : totalPowerImpact > 5
                    ? "var(--severity-severe)"
                    : "var(--severity-moderate)",
                letterSpacing: "0.1em",
                marginRight: 16,
              }}
            >
              PWR -{totalPowerImpact.toFixed(1)}%
            </div>
          </>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Annotations toggle */}
        {damages.length > 0 && (
          <button
            onClick={(e) => { e.stopPropagation(); onToggleAnnotations(); }}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 9,
              letterSpacing: "0.12em",
              padding: "4px 10px",
              borderRadius: 5,
              cursor: "pointer",
              transition: "all 0.15s ease",
              background: showAnnotations ? "rgba(77,124,255,0.1)" : "rgba(255,255,255,0.04)",
              border: `1px solid ${showAnnotations ? "rgba(77,124,255,0.3)" : "rgba(100,120,255,0.10)"}`,
              color: showAnnotations ? "var(--accent-orbital)" : "var(--text-tertiary)",
            }}
          >
            {showAnnotations ? "ANNOTATIONS ON" : "ANNOTATIONS OFF"}
          </button>
        )}
      </div>

      {/* Damage detail popover */}
      {popover && (
        <DamageDetailPopover
          damage={popover.damage}
          position={popover.position}
          onClose={handleClosePopover}
        />
      )}
    </div>
  );
}
