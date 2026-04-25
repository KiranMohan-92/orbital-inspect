import { useAnalysisState } from "../../hooks/useAnalysisState";
import { useSSE } from "../../hooks/useSSE";
import SatelliteInput from "./SatelliteInput";
import VisualAnalysis from "./VisualAnalysis";
import IntelligenceReport from "./IntelligenceReport";
import ErrorBoundary from "../ErrorBoundary";

export default function AnalysisMode() {
  const analysis = useAnalysisState();
  const { state } = analysis;
  const { analyzeImage, analyzeDemo } = useSSE(analysis);

  const handleAnalyze = () => {
    if (!state.image) return;
    analyzeImage(state.image, {
      noradId: state.noradId || undefined,
      assetName: state.assetName || undefined,
      externalAssetId: state.externalAssetId || undefined,
      additionalContext: state.additionalContext || undefined,
      assetType: state.assetType,
      inspectionEpoch: state.inspectionEpoch || undefined,
      targetSubsystem: state.targetSubsystem || undefined,
    });
  };

  return (
    <div data-testid="analysis-mode" className="h-full flex flex-col orbital-bg overflow-hidden">
      {/* 3-Panel Layout */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        {/* Panel A: Target Acquisition (300px) */}
        <div data-testid="analysis-input-panel" className="w-[300px] flex-shrink-0 flex flex-col glass-panel overflow-hidden"
          style={{ borderRight: "1px solid var(--bg-panel-border)" }}>
          <ErrorBoundary panelName="Target Acquisition">
            <SatelliteInput analysis={analysis} onAnalyze={handleAnalyze} onDemo={analyzeDemo} />
          </ErrorBoundary>
        </div>

        {/* Panel B: Visual Analysis (flex-1) */}
        <ErrorBoundary panelName="Visual Analysis">
          <div data-testid="analysis-visual-panel" className="flex-1">
            <VisualAnalysis analysis={analysis} />
          </div>
        </ErrorBoundary>

        {/* Panel C: Intelligence Report (380px) */}
        <div data-testid="analysis-report-panel" className="w-[380px] flex-shrink-0 flex flex-col glass-panel overflow-hidden"
          style={{ borderLeft: "1px solid var(--bg-panel-border)" }}>
          <ErrorBoundary panelName="Intelligence Report">
            <IntelligenceReport analysis={analysis} />
          </ErrorBoundary>
        </div>
      </div>

      {/* Footer — Mission Status Bar */}
      <div className="h-9 flex-shrink-0 flex items-center justify-between px-4"
        style={{ background: "rgba(2,2,8,0.95)", borderTop: "1px solid var(--bg-panel-border)" }}>
        <div className="flex items-center gap-3">
          <span className="font-mono-display text-xs tracking-[0.15em]"
            style={{ color: "var(--accent-orbital)", opacity: 0.7 }}>
            ORBITAL INSPECT
          </span>
          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>v0.1</span>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            ADK · Gemini Vision · 5 Agents · CelesTrak
          </span>
          {state.analysisStatus === "analyzing" && (
            <span data-testid="analysis-status" className="font-mono-display text-xs" style={{ color: "var(--accent-scan)" }}>
              T+{state.elapsedTime}s
            </span>
          )}
          {state.analysisStatus === "completed" && (
            <span data-testid="analysis-status" className="font-mono-display text-xs" style={{ color: "var(--severity-healthy)" }}>
              ASSESSMENT COMPLETE
            </span>
          )}
          {state.analysisStatus === "completed_partial" && (
            <span data-testid="analysis-status" className="font-mono-display text-xs" style={{ color: "#f59e0b" }}>
              PARTIAL ASSESSMENT
            </span>
          )}
          {state.analysisStatus === "failed" && (
            <span data-testid="analysis-status" className="font-mono-display text-xs" style={{ color: "var(--severity-critical)" }}>
              ASSESSMENT FAILED
            </span>
          )}
          {state.analysisStatus === "rejected" && (
            <span data-testid="analysis-status" className="font-mono-display text-xs" style={{ color: "#f59e0b" }}>
              TARGET REJECTED
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
