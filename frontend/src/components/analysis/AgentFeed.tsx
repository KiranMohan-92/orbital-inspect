import type { AgentName, AgentState } from "../../types";

const AGENT_META: Record<AgentName, { color: string; label: string }> = {
  orchestrator: { color: "var(--agent-orchestrator)", label: "ORCHESTRATOR" },
  vision:       { color: "var(--agent-vision)",       label: "VISION" },
  environment:  { color: "var(--agent-environment)",  label: "ENVIRONMENT" },
  failure_mode: { color: "var(--agent-failure)",      label: "FAILURE MODE" },
  priority:     { color: "var(--agent-priority)",     label: "PRIORITY" },
  discovery:    { color: "var(--text-secondary)",     label: "DISCOVERY" },
};

const STATUS_LABELS: Record<string, string> = {
  queued: "STANDBY",
  thinking: "",
  complete: "COMPLETE",
  error: "ERROR",
};

interface AgentFeedProps {
  agents: Record<AgentName, AgentState>;
  agentOrder: AgentName[];
}

export default function AgentFeed({ agents, agentOrder }: AgentFeedProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="label-mono mb-2" style={{ color: "var(--text-secondary)" }}>
        AGENT ACTIVITY
      </p>

      {agentOrder.map((name) => {
        const agent = agents[name];
        const meta = AGENT_META[name] || AGENT_META.discovery;
        const isThinking = agent.status === "thinking";
        const isComplete = agent.status === "complete";
        const isError = agent.status === "error";
        const isQueued = agent.status === "queued";

        return (
          <div
            key={name}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
              isQueued ? "opacity-40" : "agent-entry"
            }`}
            style={{
              background: isThinking ? "var(--accent-scan-dim)" : "transparent",
            }}
          >
            {/* Status dot */}
            <div className="relative flex-shrink-0">
              <div
                className={`w-2.5 h-2.5 rounded-full ${isThinking ? "agent-dot-thinking" : ""}`}
                style={{
                  backgroundColor: isError
                    ? "var(--severity-critical)"
                    : isQueued
                    ? "transparent"
                    : meta.color,
                  border: isQueued ? `1.5px solid var(--text-tertiary)` : "none",
                  boxShadow: isThinking ? `0 0 8px ${meta.color}` : "none",
                }}
              />
            </div>

            {/* Agent name */}
            <span
              className="font-mono-display text-xs tracking-wider flex-shrink-0"
              style={{
                color: isQueued ? "var(--text-tertiary)" : "var(--text-primary)",
                minWidth: 100,
              }}
            >
              {meta.label}
            </span>

            {/* Status text */}
            <span
              className="text-xs font-body truncate"
              style={{
                color: isError
                  ? "var(--severity-critical)"
                  : isThinking
                  ? "var(--accent-scan)"
                  : isComplete
                  ? "var(--severity-healthy)"
                  : "var(--text-tertiary)",
              }}
            >
              {isComplete && (
                <span className="mr-1">&#10003;</span>
              )}
              {isThinking
                ? agent.message || "Processing..."
                : isError
                ? (typeof agent.payload?.reason === "string" ? agent.payload.reason : "Failed")
                : STATUS_LABELS[agent.status] || ""}
              {isComplete && agent.message && (
                <span className="ml-1 opacity-70">{agent.message}</span>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}
