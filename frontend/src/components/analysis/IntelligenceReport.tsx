import AgentFeed from "./AgentFeed";
import InsuranceRiskCard from "./InsuranceRiskCard";
import type { UseAnalysisReturn } from "../../hooks/useAnalysisState";
import type { InsuranceRiskReport } from "../../types";

interface Props {
  analysis: UseAnalysisReturn;
}

export default function IntelligenceReport({ analysis }: Props) {
  const { state, AGENT_ORDER } = analysis;
  const insurancePayload = state.agents.insurance_risk.payload as InsuranceRiskReport | null;
  const isComplete = state.analysisStatus === "complete" && insurancePayload;

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
