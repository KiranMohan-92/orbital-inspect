import { useRef } from "react";
import BoundingBoxOverlay from "./BoundingBoxOverlay";
import type { UseAnalysisReturn } from "../../hooks/useAnalysisState";
import type { SatelliteDamageItem, SatelliteDamagesAssessment } from "../../types";

interface VisualAnalysisProps {
  analysis: UseAnalysisReturn;
}

export default function VisualAnalysis({ analysis }: VisualAnalysisProps) {
  const { state, toggleAnnotations } = analysis;
  const imgRef = useRef<HTMLImageElement>(null);

  const isIdle = state.analysisStatus === "idle";
  const isAnalyzing = state.analysisStatus === "analyzing";
  const hasImage = !!state.imagePreviewUrl;

  const visionPayload = state.agents.satellite_vision.payload as SatelliteDamagesAssessment | null;
  const damages: SatelliteDamageItem[] = visionPayload?.damages || [];

  return (
    <div className="flex-1 relative flex items-center justify-center overflow-hidden"
      style={{ background: "var(--bg-void)" }}>

      {/* Subtle orbital ring background element */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="orbit-ring" style={{
          width: "140%", height: "140%",
          border: "1px solid rgba(77,124,255,0.04)",
          borderRadius: "50%",
        }} />
      </div>

      {/* Vignette */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: "radial-gradient(ellipse at center, transparent 30%, rgba(2,2,8,0.8) 100%)",
        zIndex: 2,
      }} />

      {/* Awaiting target */}
      {!hasImage && (
        <div className="flex flex-col items-center gap-5 z-10">
          <svg className="w-20 h-20 breathe" fill="none" viewBox="0 0 24 24" stroke="currentColor"
            style={{ color: "var(--text-tertiary)" }}>
            <circle cx="12" cy="12" r="10" strokeWidth={0.5} strokeDasharray="2 4" />
            <circle cx="12" cy="12" r="5" strokeWidth={0.5} />
            <circle cx="12" cy="12" r="1" strokeWidth={1} fill="currentColor" />
            <path strokeLinecap="round" strokeWidth={0.5} d="M12 1v3M12 20v3M1 12h3M20 12h3" />
          </svg>
          <div className="text-center">
            <p className="font-mono-display text-base tracking-[0.25em] breathe"
              style={{ color: "var(--text-tertiary)" }}>
              AWAITING TARGET
            </p>
            <p className="text-xs mt-2" style={{ color: "var(--text-tertiary)", opacity: 0.5 }}>
              Upload satellite imagery to begin condition assessment
            </p>
          </div>
        </div>
      )}

      {/* Image display */}
      {hasImage && (
        <div className="relative max-w-full max-h-full flex items-center justify-center">
          <img ref={imgRef} src={state.imagePreviewUrl!} alt="Satellite target"
            className="max-w-full max-h-full object-contain relative" style={{ zIndex: 1 }} />
          {damages.length > 0 && (
            <BoundingBoxOverlay damages={damages} imageRef={imgRef} visible={state.showAnnotations} />
          )}
        </div>
      )}

      {/* Scan line */}
      {isAnalyzing && hasImage && <div className="scan-line" />}

      {/* Toolbar */}
      {hasImage && !isIdle && (
        <div className="absolute top-3 right-3 flex gap-1.5 z-20">
          {damages.length > 0 && (
            <button onClick={toggleAnnotations}
              className="px-3 py-1.5 rounded-md text-xs font-mono-display tracking-wider transition-all"
              style={{
                background: state.showAnnotations ? "var(--accent-orbital-dim)" : "rgba(255,255,255,0.04)",
                border: `1px solid ${state.showAnnotations ? "rgba(77,124,255,0.3)" : "var(--bg-panel-border)"}`,
                color: state.showAnnotations ? "var(--accent-orbital)" : "var(--text-tertiary)",
              }}>
              {state.showAnnotations ? "ANNOTATIONS ON" : "ANNOTATIONS OFF"}
            </button>
          )}
        </div>
      )}

      {/* Vision summary badge */}
      {visionPayload && (
        <div className="absolute top-3 left-3 flex items-center gap-3 z-20">
          <div className="px-3 py-1.5 rounded-md font-mono-display text-xs"
            style={{ background: "rgba(2,2,8,0.8)", backdropFilter: "blur(8px)", color: "var(--text-data)" }}>
            {visionPayload.component_assessed?.toUpperCase() || "COMPONENT"} — {visionPayload.overall_severity}
          </div>
          {visionPayload.total_power_impact_pct > 0 && (
            <div className="px-3 py-1.5 rounded-md font-mono-display text-xs"
              style={{
                background: "rgba(2,2,8,0.8)", backdropFilter: "blur(8px)",
                color: visionPayload.total_power_impact_pct > 10 ? "var(--severity-critical)"
                  : visionPayload.total_power_impact_pct > 5 ? "var(--severity-severe)"
                  : "var(--severity-moderate)",
              }}>
              PWR IMPACT: -{visionPayload.total_power_impact_pct.toFixed(1)}%
            </div>
          )}
        </div>
      )}

      {/* Damage count */}
      {damages.length > 0 && (
        <div className="absolute bottom-3 left-3 px-3 py-1.5 rounded-md z-20"
          style={{ background: "rgba(2,2,8,0.8)", backdropFilter: "blur(8px)" }}>
          <p className="font-mono-display text-xs" style={{ color: "var(--accent-scan)" }}>
            {damages.length} ANOMAL{damages.length !== 1 ? "IES" : "Y"} DETECTED
          </p>
        </div>
      )}
    </div>
  );
}
