import { useState } from "react";
import AnalysisMode from "./components/analysis/AnalysisMode";
import PortfolioView from "./components/portfolio/PortfolioView";

type AppView = "analyze" | "portfolio";

export default function App() {
  const [view, setView] = useState<AppView>("analyze");

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header
        className="flex items-center justify-between px-5 py-2 flex-shrink-0 z-10"
        style={{ background: "rgba(2,2,8,0.95)", borderBottom: "1px solid var(--bg-panel-border)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center"
            style={{ border: "1.5px solid var(--accent-orbital)", background: "var(--accent-orbital-dim)" }}
          >
            <div className="w-2 h-2 rounded-full" style={{ background: "var(--accent-orbital)" }} />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono-display text-sm tracking-[0.15em]" style={{ color: "var(--text-primary)" }}>
              ORBITAL INSPECT
            </span>
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              Orbital Infrastructure Health Intelligence
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <nav className="flex items-center gap-2">
            {([
              ["analyze", "ANALYZE"],
              ["portfolio", "PORTFOLIO"],
            ] as const).map(([id, label]) => (
              <button
                key={id}
                onClick={() => setView(id)}
                data-testid={`nav-${id}`}
                className="px-3 py-1.5 rounded-md text-xs font-mono-display tracking-[0.14em] transition-all"
                style={{
                  color: view === id ? "#ffffff" : "var(--text-tertiary)",
                  background: view === id ? "rgba(77,124,255,0.18)" : "transparent",
                  border: `1px solid ${view === id ? "rgba(77,124,255,0.35)" : "var(--bg-panel-border)"}`,
                }}
              >
                {label}
              </button>
            ))}
          </nav>
          <span className="label-mono" style={{ color: "var(--text-tertiary)" }}>
            UNCLASSIFIED
          </span>
        </div>
      </header>

      <div className="flex-1 overflow-hidden">
        {view === "analyze" ? <AnalysisMode /> : <PortfolioView />}
      </div>
    </div>
  );
}
