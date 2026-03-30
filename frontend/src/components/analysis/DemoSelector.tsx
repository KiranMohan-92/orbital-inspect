/**
 * Demo case selector — allows users to run pre-configured analysis demos
 * without uploading an image or having a Gemini API key.
 */

interface DemoCase {
  id: string;
  name: string;
  norad_id: string;
  description: string;
  icon: string;
  regime: string;
}

const DEMO_CASES: DemoCase[] = [
  {
    id: "hubble_solar_array",
    name: "HUBBLE — Solar Array",
    norad_id: "20580",
    description: "Micrometeorite impacts after 8+ years in LEO",
    icon: "HST",
    regime: "LEO 547km",
  },
  {
    id: "iss_solar_panel",
    name: "ISS — Debris Strike",
    norad_id: "25544",
    description: "Orbital debris impact on solar array wing",
    icon: "ISS",
    regime: "LEO 408km",
  },
  {
    id: "sentinel_1a",
    name: "SENTINEL-1A — Impact",
    norad_id: "39634",
    description: "~40cm particle impact on solar array",
    icon: "S1A",
    regime: "SSO 693km",
  },
];

interface DemoSelectorProps {
  onSelectDemo: (demoId: string) => void;
  disabled: boolean;
}

export default function DemoSelector({ onSelectDemo, disabled }: DemoSelectorProps) {
  return (
    <div>
      <p className="label-mono mb-2">DEMO CASES</p>
      <p className="text-xs mb-3" style={{ color: "var(--text-tertiary)" }}>
        Run pre-configured analysis without an API key
      </p>
      <div className="space-y-2">
        {DEMO_CASES.map((demo) => (
          <button
            key={demo.id}
            onClick={() => onSelectDemo(demo.id)}
            disabled={disabled}
            className="w-full text-left px-3 py-2.5 rounded-md transition-all glass-panel-hover group"
            style={{
              border: "1px solid var(--bg-panel-border)",
              opacity: disabled ? 0.4 : 1,
              cursor: disabled ? "not-allowed" : "pointer",
            }}
          >
            <div className="flex items-center gap-3">
              <div
                className="w-9 h-9 rounded flex items-center justify-center flex-shrink-0 font-mono-display text-xs"
                style={{
                  background: "rgba(77, 124, 255, 0.08)",
                  border: "1px solid rgba(77, 124, 255, 0.15)",
                  color: "var(--accent-orbital)",
                  letterSpacing: "0.05em",
                }}
              >
                {demo.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="font-mono-display text-xs tracking-wider"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {demo.name}
                  </span>
                </div>
                <span className="text-xs block truncate" style={{ color: "var(--text-tertiary)" }}>
                  {demo.description}
                </span>
                <span
                  className="text-xs font-mono-data"
                  style={{ color: "var(--text-data)", fontSize: "0.6rem" }}
                >
                  #{demo.norad_id} · {demo.regime}
                </span>
              </div>
              <svg
                className="w-4 h-4 flex-shrink-0 transition-transform group-hover:translate-x-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                style={{ color: "var(--text-tertiary)" }}
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
