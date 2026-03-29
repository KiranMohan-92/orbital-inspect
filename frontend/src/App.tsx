import AnalysisMode from "./components/analysis/AnalysisMode";

export default function App() {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header — Minimal, authoritative */}
      <header className="flex items-center justify-between px-5 py-2 flex-shrink-0 z-10"
        style={{ background: "rgba(2,2,8,0.95)", borderBottom: "1px solid var(--bg-panel-border)" }}>
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div className="w-6 h-6 rounded-full flex items-center justify-center"
            style={{ border: "1.5px solid var(--accent-orbital)", background: "var(--accent-orbital-dim)" }}>
            <div className="w-2 h-2 rounded-full" style={{ background: "var(--accent-orbital)" }} />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono-display text-sm tracking-[0.15em]"
              style={{ color: "var(--text-primary)" }}>
              ORBITAL INSPECT
            </span>
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              Satellite Condition Intelligence
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className="label-mono" style={{ color: "var(--text-tertiary)" }}>
            UNCLASSIFIED
          </span>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        <AnalysisMode />
      </div>
    </div>
  );
}
