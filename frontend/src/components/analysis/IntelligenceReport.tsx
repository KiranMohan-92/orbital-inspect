import { Suspense, useCallback, useState } from "react";
import AgentFeed from "./AgentFeed";
import InsuranceRiskCard from "./InsuranceRiskCard";
import { RiskMatrixDrilldown, DegradationTimeline } from "../viz";
import type { UseAnalysisReturn } from "../../hooks/useAnalysisState";
import type { InsuranceRiskReport, SatelliteFailureModeAnalysis, ClassificationResult } from "../../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface Props {
  analysis: UseAnalysisReturn;
}

export default function IntelligenceReport({ analysis }: Props) {
  const { state, AGENT_ORDER } = analysis;
  const insurancePayload = state.agents.insurance_risk.payload as InsuranceRiskReport | null;
  const failureModePayload = state.agents.failure_mode.payload as SatelliteFailureModeAnalysis | null;
  const classificationPayload = state.agents.orbital_classification.payload as ClassificationResult | null;
  const isComplete = state.analysisStatus === "complete" && insurancePayload;
  const [pdfLoading, setPdfLoading] = useState(false);

  const handleDownloadReport = useCallback(async () => {
    setPdfLoading(true);
    try {
      // Call backend NASA-format report generator
      const response = await fetch(`${API_BASE}/api/reports/inline/generate-pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          classification: state.agents.orbital_classification.payload || {},
          vision: state.agents.satellite_vision.payload || {},
          environment: state.agents.orbital_environment.payload || {},
          failure_mode: state.agents.failure_mode.payload || {},
          insurance_risk: state.agents.insurance_risk.payload || {},
        }),
      });
      if (!response.ok) throw new Error(`Report generation failed: ${response.status}`);
      const html = await response.text();
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch {
      window.print();
    } finally {
      setPdfLoading(false);
    }
  }, [state.agents]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--bg-panel-border)" }}>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--agent-insurance)" }} />
          <p className="label-mono">INTELLIGENCE REPORT</p>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto dark-scrollbar px-4 py-3 space-y-4">
        {/* Agent Pipeline Feed */}
        {state.analysisStatus !== "idle" && (
          <AgentFeed agents={state.agents} agentOrder={AGENT_ORDER} />
        )}

        {/* Divider */}
        {isComplete && <hr className="orbital-divider my-2" />}

        {/* Insurance Risk Report */}
        {isComplete && insurancePayload && (
          <InsuranceRiskCard report={insurancePayload} />
        )}

        {/* Risk Matrix Drilldown */}
        {isComplete && insurancePayload?.risk_matrix && (
          <Suspense fallback={<div className="text-xs text-center py-4" style={{ color: "var(--text-tertiary)" }}>Loading visualization...</div>}>
            <RiskMatrixDrilldown
              riskMatrix={insurancePayload.risk_matrix}
              riskTier={insurancePayload.risk_tier ?? "UNKNOWN"}
            />
          </Suspense>
        )}

        {/* Degradation Timeline */}
        {isComplete && (classificationPayload || failureModePayload) && (
          <Suspense fallback={<div className="text-xs text-center py-4" style={{ color: "var(--text-tertiary)" }}>Loading timeline...</div>}>
            <DegradationTimeline
              designLifeYears={classificationPayload?.design_life_years ?? null}
              estimatedAgeYears={classificationPayload?.estimated_age_years ?? null}
              remainingLifeYears={insurancePayload?.estimated_remaining_life_years ?? null}
              powerMarginPct={insurancePayload?.power_margin_percentage ?? null}
              annualDegradationPct={insurancePayload?.annual_degradation_rate_pct ?? null}
              damages={((state.agents.satellite_vision.payload as Record<string, unknown>)?.damages as Array<{ type: string; severity: string }>) ?? []}
            />
          </Suspense>
        )}

        {/* Download Report Button */}
        {isComplete && (
          <button
            onClick={handleDownloadReport}
            disabled={pdfLoading}
            className="w-full py-3 rounded-md font-mono-display text-xs tracking-[0.15em] transition-all flex items-center justify-center gap-2"
            style={{
              background: pdfLoading ? "rgba(255,255,255,0.03)" : "linear-gradient(135deg, #22c55e, #059669)",
              color: pdfLoading ? "var(--text-tertiary)" : "#ffffff",
              cursor: pdfLoading ? "wait" : "pointer",
              boxShadow: pdfLoading ? "none" : "0 0 20px rgba(34,197,94,0.15)",
              border: "1px solid rgba(34,197,94,0.2)",
            }}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            {pdfLoading ? "GENERATING..." : "DOWNLOAD CONDITION REPORT"}
          </button>
        )}

        {/* Idle state */}
        {state.analysisStatus === "idle" && (
          <div className="flex flex-col items-center justify-center h-full gap-4 py-16">
            <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"
              style={{ color: "var(--text-tertiary)", opacity: 0.4 }}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={0.8}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div className="text-center">
              <p className="font-mono-display text-xs tracking-wider" style={{ color: "var(--text-tertiary)" }}>
                NO ACTIVE ASSESSMENT
              </p>
              <p className="text-xs mt-1.5" style={{ color: "var(--text-tertiary)", opacity: 0.6 }}>
                Upload satellite imagery to generate a Condition Report
              </p>
            </div>
          </div>
        )}

        {/* Error state */}
        {state.analysisStatus === "error" && (
          <div className="data-card" style={{ borderColor: "rgba(239,68,68,0.2)", background: "rgba(239,68,68,0.05)" }}>
            <p className="label-mono mb-1" style={{ color: "var(--severity-critical)" }}>ASSESSMENT FAILED</p>
            <p className="text-xs" style={{ color: "var(--text-primary)" }}>
              {state.errorMessage || "An unexpected error occurred."}
            </p>
          </div>
        )}

        {/* Elapsed timer */}
        {state.analysisStatus === "analyzing" && (
          <div className="text-center pt-2">
            <span className="font-mono-display text-xs" style={{ color: "var(--accent-scan)" }}>
              T+{state.elapsedTime}s
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
