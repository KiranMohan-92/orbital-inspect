import {
  useRef,
  useEffect,
  useState,
  useCallback,
  useMemo,
} from "react";
import * as d3 from "d3";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DamageEvent {
  type: string;
  severity: string;
}

export interface DegradationTimelineProps {
  designLifeYears: number | null;
  estimatedAgeYears: number | null;
  remainingLifeYears: number | null;
  powerMarginPct: number | null;
  annualDegradationPct: number | null;
  damages: DamageEvent[];
  className?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  SEVERE: "#f97316",
  MODERATE: "#eab308",
  MINOR: "#84cc16",
};

const POWER_THRESHOLD = 15; // % — end of usable life
const MARGIN = { top: 28, right: 32, bottom: 48, left: 52 };

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getSeverityColor(severity: string): string {
  const key = severity.toUpperCase();
  return SEVERITY_COLORS[key] ?? SEVERITY_COLORS.MINOR;
}

/** Compute year at which power crosses the threshold given annual degradation */
function crossingYear(
  startPct: number,
  annualDeg: number,
  threshold: number
): number | null {
  if (annualDeg <= 0) return null;
  const year = (startPct - threshold) / annualDeg;
  return year > 0 ? year : null;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function DegradationTimeline({
  designLifeYears,
  estimatedAgeYears,
  remainingLifeYears,
  powerMarginPct,
  annualDegradationPct,
  damages,
  className = "",
}: DegradationTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 560, height: 220 });
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    label: string;
  } | null>(null);

  // ── Resize observer ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      if (width > 0) {
        setDims({ width, height: Math.max(180, Math.min(260, width * 0.38)) });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // ── Derived values ───────────────────────────────────────────────────────────
  const designLife = designLifeYears ?? 15;
  const currentAge = estimatedAgeYears ?? 0;
  const annualDeg = annualDegradationPct ?? 1.5;
  const initialPower = 100;
  // Use actual reported power margin if provided, else compute from model
  const reportedPower = powerMarginPct ?? null;

  const revisedEolYear = useMemo(
    () => crossingYear(initialPower, annualDeg, POWER_THRESHOLD),
    [annualDeg]
  );

  const innerW = dims.width - MARGIN.left - MARGIN.right;
  const innerH = dims.height - MARGIN.top - MARGIN.bottom;

  // ── D3 Scales ────────────────────────────────────────────────────────────────
  const xScale = useMemo(
    () => d3.scaleLinear().domain([0, designLife]).range([0, innerW]),
    [designLife, innerW]
  );

  const yScale = useMemo(
    () => d3.scaleLinear().domain([0, 100]).range([innerH, 0]),
    [innerH]
  );

  // ── Power curve points ───────────────────────────────────────────────────────
  const curvePoints = useMemo(() => {
    const steps = 200;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const year = (i / steps) * designLife;
      const power = Math.max(0, initialPower - annualDeg * year);
      return { year, power };
    });
  }, [designLife, annualDeg]);

  // Split into history (solid) and projected (dashed)
  const historyCurve = curvePoints.filter((p) => p.year <= currentAge);
  const projectedCurve = curvePoints.filter((p) => p.year >= currentAge);

  // ── Path generators ──────────────────────────────────────────────────────────
  const lineGen = d3
    .line<{ year: number; power: number }>()
    .x((d) => xScale(d.year))
    .y((d) => yScale(d.power))
    .curve(d3.curveMonotoneX);

  const areaGen = d3
    .area<{ year: number; power: number }>()
    .x((d) => xScale(d.year))
    .y0(innerH)
    .y1((d) => yScale(d.power))
    .curve(d3.curveMonotoneX);

  const historyPath = historyCurve.length > 1 ? lineGen(historyCurve) ?? "" : "";
  const projectedPath =
    projectedCurve.length > 1 ? lineGen(projectedCurve) ?? "" : "";
  const areaPath = curvePoints.length > 1 ? areaGen(curvePoints) ?? "" : "";

  // ── Axis ticks ───────────────────────────────────────────────────────────────
  const xTicks = xScale.ticks(Math.min(8, designLife));
  const yTicks = yScale.ticks(5);

  // ── Grid lines ───────────────────────────────────────────────────────────────
  const gridLines = yTicks.map((t) => ({
    y: yScale(t),
    label: `${t}`,
  }));

  // ── Gradient id (stable per component instance) ──────────────────────────────
  const gradId = useRef(
    `dg-grad-${Math.random().toString(36).slice(2)}`
  ).current;
  const maskId = useRef(
    `dg-mask-${Math.random().toString(36).slice(2)}`
  ).current;

  // ── Tooltip handler ──────────────────────────────────────────────────────────
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGRectElement>) => {
      const rect = (e.target as SVGRectElement).getBoundingClientRect();
      const svgX = e.clientX - rect.left;
      const year = xScale.invert(svgX);
      if (year < 0 || year > designLife) {
        setTooltip(null);
        return;
      }
      const power = Math.max(0, initialPower - annualDeg * year);
      setTooltip({
        x: xScale(year),
        y: yScale(power),
        label: `Year ${year.toFixed(1)}: ${power.toFixed(1)}% power`,
      });
    },
    [xScale, yScale, designLife, annualDeg]
  );

  const computedPower = Math.max(0, initialPower - annualDeg * currentAge);
  const currentPowerVal = reportedPower !== null ? reportedPower : computedPower;
  const currentPowerY = yScale(currentPowerVal);
  const currentPowerX = xScale(currentAge);

  // ── Damage dot severities at current age ─────────────────────────────────────
  const damageDots = useMemo(() => {
    const seen = new Map<string, number>();
    return damages.map((d, i) => {
      const key = d.severity.toUpperCase();
      const count = seen.get(key) ?? 0;
      seen.set(key, count + 1);
      return {
        id: i,
        color: getSeverityColor(d.severity),
        offsetX: currentPowerX + (count - damages.length / 2) * 10,
        y: currentPowerY - 18 - count * 2,
      };
    });
  }, [damages, currentPowerX, currentPowerY]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        width: "100%",
        background: "rgba(8,10,20,0.88)",
        borderRadius: 8,
        padding: "4px 0 0",
        position: "relative",
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      {/* Chart title */}
      <div
        style={{
          padding: "8px 16px 0",
          fontSize: 11,
          color: "rgba(77,124,255,0.9)",
          letterSpacing: "0.1em",
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >
        POWER DEGRADATION TIMELINE
      </div>

      <svg
        width={dims.width}
        height={dims.height}
        style={{ overflow: "visible", display: "block" }}
      >
        <defs>
          {/* Area gradient */}
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4d7cff" stopOpacity={0.28} />
            <stop offset="60%" stopColor="#4d7cff" stopOpacity={0.06} />
            <stop offset="100%" stopColor="#4d7cff" stopOpacity={0} />
          </linearGradient>
          {/* Clip mask so area doesn't overflow */}
          <clipPath id={maskId}>
            <rect x={0} y={0} width={innerW} height={innerH} />
          </clipPath>
        </defs>

        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {/* Background */}
          <rect
            x={0}
            y={0}
            width={innerW}
            height={innerH}
            fill="rgba(4,6,16,0.6)"
            rx={4}
          />

          {/* Grid lines */}
          {gridLines.map((gl) => (
            <g key={gl.label}>
              <line
                x1={0}
                y1={gl.y}
                x2={innerW}
                y2={gl.y}
                stroke="rgba(100,120,255,0.07)"
                strokeWidth={1}
              />
              <text
                x={-8}
                y={gl.y + 4}
                textAnchor="end"
                fontSize={9}
                fill="rgba(160,170,210,0.6)"
                fontFamily="'JetBrains Mono', monospace"
              >
                {gl.label}
              </text>
            </g>
          ))}

          {/* X-axis ticks */}
          {xTicks.map((t) => (
            <g key={t} transform={`translate(${xScale(t)},${innerH})`}>
              <line y1={0} y2={5} stroke="rgba(160,170,210,0.35)" strokeWidth={1} />
              <text
                y={16}
                textAnchor="middle"
                fontSize={9}
                fill="rgba(160,170,210,0.6)"
                fontFamily="'JetBrains Mono', monospace"
              >
                {t}yr
              </text>
            </g>
          ))}

          {/* Y-axis label */}
          <text
            transform={`translate(${-38},${innerH / 2}) rotate(-90)`}
            textAnchor="middle"
            fontSize={9}
            fill="rgba(160,170,210,0.55)"
            fontFamily="'JetBrains Mono', monospace"
          >
            POWER %
          </text>

          {/* X-axis label */}
          <text
            x={innerW / 2}
            y={innerH + 36}
            textAnchor="middle"
            fontSize={9}
            fill="rgba(160,170,210,0.55)"
            fontFamily="'JetBrains Mono', monospace"
          >
            MISSION YEAR
          </text>

          {/* Clipped chart content */}
          <g clipPath={`url(#${maskId})`}>
            {/* Area fill */}
            <path d={areaPath} fill={`url(#${gradId})`} />

            {/* History curve (solid) */}
            {historyPath && (
              <path
                d={historyPath}
                fill="none"
                stroke="#4d7cff"
                strokeWidth={2}
                strokeLinecap="round"
              />
            )}

            {/* Projected curve (dashed) */}
            {projectedPath && (
              <path
                d={projectedPath}
                fill="none"
                stroke="#4d7cff"
                strokeWidth={1.5}
                strokeDasharray="5,3"
                strokeLinecap="round"
                opacity={0.55}
              />
            )}
          </g>

          {/* Critical threshold line */}
          <line
            x1={0}
            y1={yScale(POWER_THRESHOLD)}
            x2={innerW}
            y2={yScale(POWER_THRESHOLD)}
            stroke="#ef4444"
            strokeWidth={1}
            strokeDasharray="4,4"
            opacity={0.7}
          />
          <text
            x={innerW - 4}
            y={yScale(POWER_THRESHOLD) - 4}
            textAnchor="end"
            fontSize={8}
            fill="#ef4444"
            opacity={0.85}
            fontFamily="'JetBrains Mono', monospace"
          >
            EOL THRESHOLD
          </text>

          {/* Current age vertical line */}
          {currentAge > 0 && (
            <g>
              <line
                x1={currentPowerX}
                y1={0}
                x2={currentPowerX}
                y2={innerH}
                stroke="#00d4ff"
                strokeWidth={1}
                strokeDasharray="3,3"
                opacity={0.7}
              />
              <circle
                cx={currentPowerX}
                cy={currentPowerY}
                r={4}
                fill="#00d4ff"
                stroke="#020208"
                strokeWidth={1.5}
              />
              <text
                x={currentPowerX + 4}
                y={12}
                fontSize={8}
                fill="#00d4ff"
                opacity={0.85}
                fontFamily="'JetBrains Mono', monospace"
              >
                NOW
              </text>
            </g>
          )}

          {/* Design life EOL vertical line */}
          <g>
            <line
              x1={xScale(designLife)}
              y1={0}
              x2={xScale(designLife)}
              y2={innerH}
              stroke="rgba(255,255,255,0.3)"
              strokeWidth={1}
              strokeDasharray="2,4"
            />
            <text
              x={xScale(designLife) - 4}
              y={12}
              textAnchor="end"
              fontSize={8}
              fill="rgba(255,255,255,0.5)"
              fontFamily="'JetBrains Mono', monospace"
            >
              DESIGN EOL
            </text>
          </g>

          {/* Revised EOL marker */}
          {revisedEolYear !== null &&
            revisedEolYear < designLife &&
            revisedEolYear !== designLife && (
              <g>
                <line
                  x1={xScale(revisedEolYear)}
                  y1={yScale(POWER_THRESHOLD) - 8}
                  x2={xScale(revisedEolYear)}
                  y2={innerH}
                  stroke="#f97316"
                  strokeWidth={1.5}
                  strokeDasharray="3,2"
                  opacity={0.75}
                />
                <text
                  x={xScale(revisedEolYear) + 4}
                  y={yScale(POWER_THRESHOLD) - 10}
                  fontSize={8}
                  fill="#f97316"
                  opacity={0.85}
                  fontFamily="'JetBrains Mono', monospace"
                >
                  PWR EOL
                </text>
              </g>
            )}

          {/* Damage event dots */}
          {damageDots.map((dot) => (
            <circle
              key={dot.id}
              cx={dot.offsetX}
              cy={currentPowerY}
              r={4}
              fill={dot.color}
              stroke="#020208"
              strokeWidth={1}
              opacity={0.9}
            />
          ))}

          {/* Remaining life annotation */}
          {remainingLifeYears !== null && currentAge > 0 && (
            <g>
              <rect
                x={currentPowerX + 6}
                y={currentPowerY - 14}
                width={80}
                height={16}
                rx={3}
                fill="rgba(8,10,20,0.85)"
                stroke="rgba(77,124,255,0.3)"
              />
              <text
                x={currentPowerX + 46}
                y={currentPowerY - 3}
                textAnchor="middle"
                fontSize={8}
                fill="#4d7cff"
                fontFamily="'JetBrains Mono', monospace"
              >
                {remainingLifeYears.toFixed(1)}yr remain
              </text>
            </g>
          )}

          {/* Hover interaction overlay */}
          <rect
            x={0}
            y={0}
            width={innerW}
            height={innerH}
            fill="transparent"
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setTooltip(null)}
            style={{ cursor: "crosshair" }}
          />

          {/* Tooltip */}
          {tooltip && (
            <g>
              <line
                x1={tooltip.x}
                y1={0}
                x2={tooltip.x}
                y2={innerH}
                stroke="rgba(255,255,255,0.2)"
                strokeWidth={1}
                pointerEvents="none"
              />
              <circle
                cx={tooltip.x}
                cy={tooltip.y}
                r={3}
                fill="white"
                opacity={0.8}
                pointerEvents="none"
              />
              <rect
                x={tooltip.x + 6}
                y={tooltip.y - 14}
                width={140}
                height={18}
                rx={3}
                fill="rgba(8,10,20,0.9)"
                stroke="rgba(255,255,255,0.15)"
                pointerEvents="none"
              />
              <text
                x={tooltip.x + 76}
                y={tooltip.y - 2}
                textAnchor="middle"
                fontSize={9}
                fill="rgba(255,255,255,0.85)"
                fontFamily="'JetBrains Mono', monospace"
                pointerEvents="none"
              >
                {tooltip.label}
              </text>
            </g>
          )}

          {/* Axes borders */}
          <line x1={0} y1={innerH} x2={innerW} y2={innerH} stroke="rgba(100,120,255,0.25)" strokeWidth={1} />
          <line x1={0} y1={0} x2={0} y2={innerH} stroke="rgba(100,120,255,0.25)" strokeWidth={1} />
        </g>
      </svg>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: 16,
          padding: "6px 16px 10px",
          flexWrap: "wrap",
        }}
      >
        {[
          { color: "#4d7cff", dash: false, label: "Power (historical)" },
          { color: "#4d7cff", dash: true, label: "Power (projected)" },
          { color: "#00d4ff", dash: true, label: "Current position" },
          { color: "#ef4444", dash: true, label: "EOL threshold (15%)" },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 9,
              color: "rgba(160,170,210,0.7)",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            <svg width={22} height={8}>
              <line
                x1={0}
                y1={4}
                x2={22}
                y2={4}
                stroke={item.color}
                strokeWidth={item.dash ? 1.5 : 2}
                strokeDasharray={item.dash ? "3,2" : undefined}
              />
            </svg>
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}
