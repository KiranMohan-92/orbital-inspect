import type { UseAnalysisReturn } from "../../hooks/useAnalysisState";
import type { SatelliteDamagesAssessment } from "../../types";
import EvidenceViewer from "./EvidenceViewer";

interface VisualAnalysisProps {
  analysis: UseAnalysisReturn;
}

export default function VisualAnalysis({ analysis }: VisualAnalysisProps) {
  const { state, toggleAnnotations } = analysis;

  const isIdle = state.analysisStatus === "idle";
  const isAnalyzing = state.analysisStatus === "analyzing";
  const hasImage = !!state.imagePreviewUrl;

  const visionPayload = state.agents.satellite_vision.payload as SatelliteDamagesAssessment | null;

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

      {/* Vignette — only shown in idle/no-image state */}
      {!hasImage && (
        <div className="absolute inset-0 pointer-events-none" style={{
          background: "radial-gradient(ellipse at center, transparent 30%, rgba(2,2,8,0.8) 100%)",
          zIndex: 2,
        }} />
      )}

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

      {/* Zoomable evidence viewer — shown when image is available */}
      {hasImage && (
        <EvidenceViewer
          imageUrl={state.imagePreviewUrl!}
          damages={visionPayload?.damages ?? []}
          overallSeverity={visionPayload?.overall_severity ?? ""}
          totalPowerImpact={visionPayload?.total_power_impact_pct ?? 0}
          componentAssessed={visionPayload?.component_assessed ?? ""}
          showAnnotations={state.showAnnotations}
          onToggleAnnotations={toggleAnnotations}
        />
      )}

      {/* Scan line during analysis */}
      {isAnalyzing && hasImage && <div className="scan-line" />}

      {/* Suppress unused variable warning */}
      {isIdle && null}
    </div>
  );
}
