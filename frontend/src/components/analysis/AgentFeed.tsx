import type { AgentName, AgentState } from "../../types";

const AGENT_META: Record<AgentName, { color: string; label: string; icon: string }> = {
  orbital_classification: { color: "var(--agent-classification)", label: "ORBITAL CLASS", icon: "OC" },
  satellite_vision:       { color: "var(--agent-vision)",         label: "SAT VISION",   icon: "SV" },
  orbital_environment:    { color: "var(--agent-environment)",    label: "ENVIRONMENT",  icon: "OE" },
  failure_mode:           { color: "var(--agent-failure)",        label: "FAILURE MODE", icon: "FM" },
  insurance_risk:         { color: "var(--agent-insurance)",      label: "INSURANCE",    icon: "IR" },
};

interface AgentFeedProps {
  agents: Record<AgentName, AgentState>;
  agentOrder: AgentName[];
}

export default function AgentFeed({ agents, agentOrder }: AgentFeedProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="label-mono mb-2">AGENT PIPELINE</p>

      {agentOrder.map((name, idx) => {
        const agent = agents[name];
        const meta = AGENT_META[name];
        const isThinking = agent.status === "thinking";
        const isComplete = agent.status === "complete";
        const isError = agent.status === "error";
        const isQueued = agent.status === "queued";

        return (
          <div
            key={name}
            className={`flex items-center gap-3 px-3 py-2 rounded-md transition-all ${
              isQueued ? "opacity-30" : "agent-entry"
            }`}
            style={{
              background: isThinking ? `${meta.color}08` : "transparent",
              borderLeft: isComplete ? `2px solid ${meta.color}` : isThinking ? `2px solid ${meta.color}40` : "2px solid transparent",
            }}
          >
            {/* Step number + dot */}
            <div className="flex items-center gap-2 flex-shrink-0" style={{ minWidth: 28 }}>
              <span
                className="font-mono-display text-xs"
                style={{ color: isQueued ? "var(--text-tertiary)" : meta.color, opacity: isQueued ? 0.4 : 0.6 }}
              >
                {String(idx + 1).padStart(2, "0")}
              </span>
              <div
                className={`w-2 h-2 rounded-full ${isThinking ? "agent-dot-thinking" : ""}`}
                style={{
                  backgroundColor: isError ? "var(--severity-critical)" : isQueued ? "transparent" : meta.color,
                  border: isQueued ? `1px solid var(--text-tertiary)` : "none",
                  boxShadow: isThinking ? `0 0 8px ${meta.color}` : "none",
                }}
              />
            </div>

            {/* Agent label */}
            <span
              className="font-mono-display text-xs tracking-wider flex-shrink-0"
              style={{
                color: isQueued ? "var(--text-tertiary)" : "var(--text-primary)",
                minWidth: 90,
              }}
            >
              {meta.label}
            </span>

            {/* Status */}
            <span
              className="text-xs truncate"
              style={{
                fontFamily: "var(--font-sans)",
                color: isError ? "var(--severity-critical)"
                  : isThinking ? "var(--accent-scan)"
                  : isComplete ? meta.color
                  : "var(--text-tertiary)",
              }}
            >
              {isComplete && <span className="mr-1 opacity-60">&#10003;</span>}
              {isThinking
                ? agent.message || "Processing..."
                : isError
                ? (typeof agent.payload?.reason === "string" ? agent.payload.reason : "Failed")
                : isComplete
                ? agent.message || "Complete"
                : "STANDBY"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
