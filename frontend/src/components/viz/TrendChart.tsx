/**
 * D3.js line chart showing risk composite trajectory with trend predictions.
 * Historical data points colored by risk tier, linear regression trend line,
 * 30d/90d prediction zones, and UNINSURABLE threshold.
 */

import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import * as d3 from "d3";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DataPoint {
  analysis_id: string;
  composite_score: number;
  timestamp: string;
  risk_tier: string | null;
}

export interface TrendChartProps {
  dataPoints: DataPoint[];
  slopePerDay: number;
  predictedScore30d: number;
  predictedScore90d: number;
  daysToThreshold: number | null;
  currentScore: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TIER_COLORS: Record<string, string> = {
  LOW: "#22c55e",
  MEDIUM: "#eab308",
  "MEDIUM-HIGH": "#f97316",
  HIGH: "#ef4444",
  CRITICAL: "#ef4444",
  UNKNOWN: "#666",
};

const UNINSURABLE_THRESHOLD = 85;
const MARGIN = { top: 28, right: 32, bottom: 48, left: 52 };

// ─── Component ────────────────────────────────────────────────────────────────

export default function TrendChart({
  dataPoints,
  slopePerDay,
  predictedScore30d,
  predictedScore90d,
  daysToThreshold,
  currentScore,
}: TrendChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 560, height: 240 });
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
        setDims({ width, height: Math.max(200, Math.min(280, width * 0.4)) });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // ── Parse timestamps and sort ───────────────────────────────────────────────
  const parsed = useMemo(() => {
    return dataPoints
      .map((dp) => ({ ...dp, date: new Date(dp.timestamp) }))
      .filter((dp) => !Number.isNaN(dp.date.getTime()))
      .sort((a, b) => a.date.getTime() - b.date.getTime());
  }, [dataPoints]);

  const innerW = dims.width - MARGIN.left - MARGIN.right;
  const innerH = dims.height - MARGIN.top - MARGIN.bottom;

  // ── X domain: from earliest point to 90 days after latest ───────────────────
  const xDomain = useMemo<[Date, Date]>(() => {
    if (parsed.length === 0) {
      const now = new Date();
      return [now, new Date(now.getTime() + 90 * 86400000)];
    }
    const minDate = parsed[0].date;
    const maxDate = parsed[parsed.length - 1].date;
    const predict90 = new Date(maxDate.getTime() + 90 * 86400000);
    return [minDate, predict90];
  }, [parsed]);

  const xScale = useMemo(
    () => d3.scaleTime().domain(xDomain).range([0, innerW]),
    [xDomain, innerW],
  );

  const yScale = useMemo(
    () => d3.scaleLinear().domain([0, 100]).range([innerH, 0]),
    [innerH],
  );

  // ── Trend line points ───────────────────────────────────────────────────────
  const trendLine = useMemo(() => {
    if (parsed.length === 0) return null;
    const lastPoint = parsed[parsed.length - 1];
    const lastDate = lastPoint.date;
    const predict30Date = new Date(lastDate.getTime() + 30 * 86400000);
    const predict90Date = new Date(lastDate.getTime() + 90 * 86400000);
    // Derive the regression intercept from the backend's predicted values
    // so the dashed line matches the actual fitted trend, not the last sample.
    const fittedAtLast = predictedScore30d - slopePerDay * 30;
    const startDayOffset = (parsed[0].date.getTime() - lastDate.getTime()) / 86400000;
    const startScore = Math.max(0, Math.min(100, fittedAtLast + slopePerDay * startDayOffset));
    return {
      x1: xScale(parsed[0].date),
      y1: yScale(startScore),
      x2: xScale(predict90Date),
      y2: yScale(Math.max(0, Math.min(100, predictedScore90d))),
    };
  }, [parsed, slopePerDay, predictedScore30d, predictedScore90d, xScale, yScale]);

  // ── Prediction zones ────────────────────────────────────────────────────────
  const predictionZones = useMemo(() => {
    if (parsed.length === 0) return null;
    const lastDate = parsed[parsed.length - 1].date;
    const predict30Date = new Date(lastDate.getTime() + 30 * 86400000);
    const predict90Date = new Date(lastDate.getTime() + 90 * 86400000);
    const lastScore = parsed[parsed.length - 1].composite_score;
    return {
      zone30: {
        x: xScale(lastDate),
        width: xScale(predict30Date) - xScale(lastDate),
        yTop: yScale(Math.min(100, Math.max(0, predictedScore30d + 5))),
        yBottom: yScale(Math.max(0, Math.min(100, predictedScore30d - 5))),
      },
      zone90: {
        x: xScale(predict30Date),
        width: xScale(predict90Date) - xScale(predict30Date),
        yTop: yScale(Math.min(100, Math.max(0, predictedScore90d + 10))),
        yBottom: yScale(Math.max(0, Math.min(100, predictedScore90d - 10))),
      },
      lastX: xScale(lastDate),
      lastY: yScale(lastScore),
    };
  }, [parsed, predictedScore30d, predictedScore90d, xScale, yScale]);

  // ── Axis ticks ───────────────────────────────────────────────────────────────
  const xTicks = xScale.ticks(6);
  const yTicks = yScale.ticks(5);
  const gridLines = yTicks.map((t) => ({ y: yScale(t), label: `${t}` }));

  // ── Gradient ids ─────────────────────────────────────────────────────────────
  const gradId = useRef(`trend-grad-${Math.random().toString(36).slice(2)}`).current;
  const maskId = useRef(`trend-mask-${Math.random().toString(36).slice(2)}`).current;

  // ── Tooltip handler ──────────────────────────────────────────────────────────
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGRectElement>) => {
      if (parsed.length === 0) return;
      const rect = (e.target as SVGRectElement).getBoundingClientRect();
      const svgX = e.clientX - rect.left;
      const hoverDate = xScale.invert(svgX);

      // Find closest data point
      let closest = parsed[0];
      let closestDist = Math.abs(hoverDate.getTime() - parsed[0].date.getTime());
      for (const p of parsed) {
        const dist = Math.abs(hoverDate.getTime() - p.date.getTime());
        if (dist < closestDist) {
          closest = p;
          closestDist = dist;
        }
      }

      const cx = xScale(closest.date);
      const cy = yScale(closest.composite_score);
      const dateStr = closest.date.toLocaleDateString();
      const tier = closest.risk_tier || "UNKNOWN";
      setTooltip({
        x: cx,
        y: cy,
        label: `${dateStr} · ${closest.composite_score.toFixed(1)} · ${tier}`,
      });
    },
    [parsed, xScale, yScale],
  );

  const formatDate = (d: Date) => {
    const m = d.getMonth() + 1;
    const day = d.getDate();
    return `${m}/${day}`;
  };

  return (
    <div
      ref={containerRef}
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
        RISK COMPOSITE TRAJECTORY
      </div>

      <svg
        width={dims.width}
        height={dims.height}
        style={{ overflow: "visible", display: "block" }}
      >
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4d7cff" stopOpacity={0.18} />
            <stop offset="100%" stopColor="#4d7cff" stopOpacity={0} />
          </linearGradient>
          <clipPath id={maskId}>
            <rect x={0} y={0} width={innerW} height={innerH} />
          </clipPath>
        </defs>

        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {/* Background */}
          <rect x={0} y={0} width={innerW} height={innerH} fill="rgba(4,6,16,0.6)" rx={4} />

          {/* Grid lines */}
          {gridLines.map((gl) => (
            <g key={gl.label}>
              <line x1={0} y1={gl.y} x2={innerW} y2={gl.y} stroke="rgba(100,120,255,0.07)" strokeWidth={1} />
              <text x={-8} y={gl.y + 4} textAnchor="end" fontSize={9} fill="rgba(160,170,210,0.6)" fontFamily="'JetBrains Mono', monospace">
                {gl.label}
              </text>
            </g>
          ))}

          {/* X-axis ticks */}
          {xTicks.map((t, i) => (
            <g key={i} transform={`translate(${xScale(t)},${innerH})`}>
              <line y1={0} y2={5} stroke="rgba(160,170,210,0.35)" strokeWidth={1} />
              <text y={16} textAnchor="middle" fontSize={9} fill="rgba(160,170,210,0.6)" fontFamily="'JetBrains Mono', monospace">
                {formatDate(t)}
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
            COMPOSITE SCORE
          </text>

          {/* X-axis label */}
          <text x={innerW / 2} y={innerH + 36} textAnchor="middle" fontSize={9} fill="rgba(160,170,210,0.55)" fontFamily="'JetBrains Mono', monospace">
            DATE
          </text>

          <g clipPath={`url(#${maskId})`}>
            {/* 30-day prediction zone */}
            {predictionZones && (
              <>
                <rect
                  x={predictionZones.zone30.x}
                  y={predictionZones.zone30.yTop}
                  width={Math.max(0, predictionZones.zone30.width)}
                  height={Math.max(0, predictionZones.zone30.yBottom - predictionZones.zone30.yTop)}
                  fill="rgba(77,124,255,0.08)"
                />
                <rect
                  x={predictionZones.zone90.x}
                  y={predictionZones.zone90.yTop}
                  width={Math.max(0, predictionZones.zone90.width)}
                  height={Math.max(0, predictionZones.zone90.yBottom - predictionZones.zone90.yTop)}
                  fill="rgba(77,124,255,0.04)"
                />
              </>
            )}

            {/* Trend line (dashed) */}
            {trendLine && (
              <line
                x1={trendLine.x1}
                y1={trendLine.y1}
                x2={trendLine.x2}
                y2={trendLine.y2}
                stroke="#4d7cff"
                strokeWidth={1.5}
                strokeDasharray="6,4"
                opacity={0.6}
              />
            )}

            {/* Data point circles */}
            {parsed.map((dp, i) => (
              <circle
                key={dp.analysis_id || i}
                cx={xScale(dp.date)}
                cy={yScale(dp.composite_score)}
                r={4}
                fill={TIER_COLORS[dp.risk_tier || "UNKNOWN"] || "#666"}
                stroke="#020208"
                strokeWidth={1.5}
                opacity={0.9}
              />
            ))}

            {/* Line connecting data points */}
            {parsed.length > 1 && (
              <path
                d={
                  d3
                    .line<(typeof parsed)[0]>()
                    .x((d) => xScale(d.date))
                    .y((d) => yScale(d.composite_score))
                    .curve(d3.curveMonotoneX)(parsed) ?? ""
                }
                fill="none"
                stroke="#4d7cff"
                strokeWidth={1.5}
                strokeLinecap="round"
                opacity={0.7}
              />
            )}
          </g>

          {/* UNINSURABLE threshold line at 85 */}
          <line
            x1={0}
            y1={yScale(UNINSURABLE_THRESHOLD)}
            x2={innerW}
            y2={yScale(UNINSURABLE_THRESHOLD)}
            stroke="#ef4444"
            strokeWidth={1}
            strokeDasharray="4,4"
            opacity={0.7}
          />
          <text
            x={innerW - 4}
            y={yScale(UNINSURABLE_THRESHOLD) - 4}
            textAnchor="end"
            fontSize={8}
            fill="#ef4444"
            opacity={0.85}
            fontFamily="'JetBrains Mono', monospace"
          >
            UNINSURABLE (85)
          </text>

          {/* Days to threshold annotation */}
          {daysToThreshold !== null && (
            <text
              x={innerW - 4}
              y={yScale(UNINSURABLE_THRESHOLD) + 12}
              textAnchor="end"
              fontSize={8}
              fill="#ef4444"
              opacity={0.7}
              fontFamily="'JetBrains Mono', monospace"
            >
              {daysToThreshold}d to threshold
            </text>
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
              <line x1={tooltip.x} y1={0} x2={tooltip.x} y2={innerH} stroke="rgba(255,255,255,0.2)" strokeWidth={1} pointerEvents="none" />
              <circle cx={tooltip.x} cy={tooltip.y} r={3} fill="white" opacity={0.8} pointerEvents="none" />
              <rect
                x={tooltip.x + 6}
                y={tooltip.y - 14}
                width={180}
                height={18}
                rx={3}
                fill="rgba(8,10,20,0.9)"
                stroke="rgba(255,255,255,0.15)"
                pointerEvents="none"
              />
              <text
                x={tooltip.x + 96}
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
      <div style={{ display: "flex", gap: 16, padding: "6px 16px 10px", flexWrap: "wrap" }}>
        {[
          { color: "#4d7cff", dash: false, label: "Historical trend" },
          { color: "#4d7cff", dash: true, label: "Regression line" },
          { color: "#ef4444", dash: true, label: "Uninsurable (85)" },
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
        {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((tier) => (
          <div
            key={tier}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 9,
              color: "rgba(160,170,210,0.7)",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            <div style={{ width: 6, height: 6, borderRadius: 3, background: TIER_COLORS[tier] }} />
            {tier}
          </div>
        ))}
      </div>
    </div>
  );
}
