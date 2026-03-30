import { useState, useCallback, useRef } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface RiskDimension {
  score: number;
  reasoning: string;
}

interface RiskMatrix {
  severity: RiskDimension;
  probability: RiskDimension;
  consequence: RiskDimension;
  composite: number;
}

export interface RiskMatrixDrilldownProps {
  riskMatrix: RiskMatrix;
  riskTier: string;
  className?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TIER_COLORS: Record<string, { primary: string; glow: string; label: string }> = {
  CRITICAL:    { primary: "#ef4444", glow: "rgba(239,68,68,0.4)",   label: "CRITICAL RISK" },
  HIGH:        { primary: "#f97316", glow: "rgba(249,115,22,0.4)",  label: "HIGH RISK" },
  SIGNIFICANT: { primary: "#eab308", glow: "rgba(234,179,8,0.35)",  label: "SIGNIFICANT RISK" },
  MODERATE:    { primary: "#84cc16", glow: "rgba(132,204,22,0.35)", label: "MODERATE RISK" },
  LOW:         { primary: "#22d3ee", glow: "rgba(34,211,238,0.3)",  label: "LOW RISK" },
};

function getTierStyle(tier: string) {
  const key = tier.toUpperCase().replace(/\s+/g, "_");
  return (
    TIER_COLORS[key] ??
    TIER_COLORS[Object.keys(TIER_COLORS).find((k) => key.includes(k)) ?? ""] ??
    { primary: "#4d7cff", glow: "rgba(77,124,255,0.35)", label: tier.toUpperCase() }
  );
}

function getScoreColor(score: number): string {
  if (score >= 5) return "#ef4444";
  if (score >= 4) return "#f97316";
  if (score >= 3) return "#eab308";
  return "#84cc16";
}

// ─── Circular Progress Arc ────────────────────────────────────────────────────

function CircularProgress({
  value,
  max,
  color,
  size = 100,
  strokeWidth = 7,
}: {
  value: number;
  max: number;
  color: string;
  size?: number;
  strokeWidth?: number;
}) {
  const r = (size - strokeWidth * 2) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(1, Math.max(0, value / max));
  const dash = pct * circ;
  const gap = circ - dash;

  // Start from top (-90 deg)
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      {/* Track */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="rgba(255,255,255,0.07)"
        strokeWidth={strokeWidth}
      />
      {/* Progress */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={`${dash} ${gap}`}
        strokeLinecap="round"
        style={{
          filter: `drop-shadow(0 0 4px ${color})`,
          transition: "stroke-dasharray 0.6s cubic-bezier(0.4,0,0.2,1)",
        }}
      />
    </svg>
  );
}

// ─── Score Bar ────────────────────────────────────────────────────────────────

function ScoreBar({
  score,
  max = 5,
  color,
}: {
  score: number;
  max?: number;
  color: string;
}) {
  const pct = (score / max) * 100;
  return (
    <div
      style={{
        width: "100%",
        height: 4,
        background: "rgba(255,255,255,0.08)",
        borderRadius: 2,
        overflow: "hidden",
        marginTop: 6,
      }}
    >
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          background: color,
          borderRadius: 2,
          boxShadow: `0 0 6px ${color}`,
          transition: "width 0.6s cubic-bezier(0.4,0,0.2,1)",
        }}
      />
    </div>
  );
}

// ─── Dimension Card ───────────────────────────────────────────────────────────

interface DimCardProps {
  title: string;
  abbrev: string;
  score: number;
  reasoning: string;
  index: number;
}

function DimensionCard({ title, abbrev, score, reasoning, index }: DimCardProps) {
  const [expanded, setExpanded] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const color = getScoreColor(score);

  const toggle = useCallback(() => setExpanded((v) => !v), []);

  // Stagger entrance animation delay
  const delay = `${index * 80}ms`;

  return (
    <div
      onClick={toggle}
      style={{
        flex: "1 1 0",
        minWidth: 140,
        background: "rgba(8,10,20,0.72)",
        border: `1px solid rgba(255,255,255,0.08)`,
        borderRadius: 8,
        padding: "14px 16px 12px",
        cursor: "pointer",
        position: "relative",
        overflow: "hidden",
        transition: "border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease",
        animationDelay: delay,
        backdropFilter: "blur(16px) saturate(120%)",
        WebkitBackdropFilter: "blur(16px) saturate(120%)",
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.borderColor = `${color}55`;
        el.style.transform = "translateY(-2px)";
        el.style.boxShadow = `0 8px 24px ${color}20`;
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.borderColor = "rgba(255,255,255,0.08)";
        el.style.transform = "translateY(0)";
        el.style.boxShadow = "none";
      }}
    >
      {/* Subtle color accent top border */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: `linear-gradient(90deg, ${color}00, ${color}cc, ${color}00)`,
          borderRadius: "8px 8px 0 0",
        }}
      />

      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 8,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 9,
              color: "rgba(160,170,210,0.55)",
              fontFamily: "'JetBrains Mono', monospace",
              letterSpacing: "0.1em",
              marginBottom: 2,
            }}
          >
            {abbrev}
          </div>
          <div
            style={{
              fontSize: 11,
              color: "rgba(200,210,240,0.9)",
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: 600,
            }}
          >
            {title}
          </div>
        </div>
        {/* Expand indicator */}
        <div
          style={{
            fontSize: 10,
            color: "rgba(160,170,210,0.4)",
            transition: "transform 0.2s ease",
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            marginTop: 2,
          }}
        >
          ▾
        </div>
      </div>

      {/* Score display */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 2,
          marginBottom: 4,
        }}
      >
        <span
          style={{
            fontSize: 36,
            fontWeight: 700,
            color: color,
            fontFamily: "'JetBrains Mono', monospace",
            lineHeight: 1,
            textShadow: `0 0 16px ${color}80`,
          }}
        >
          {score}
        </span>
        <span
          style={{
            fontSize: 14,
            color: "rgba(160,170,210,0.4)",
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          /5
        </span>
      </div>

      {/* Progress bar */}
      <ScoreBar score={score} color={color} />

      {/* Reasoning (collapsed: preview, expanded: full) */}
      <div
        ref={contentRef}
        style={{
          marginTop: 10,
          overflow: "hidden",
          maxHeight: expanded ? "200px" : "2.6em",
          transition: "max-height 0.35s cubic-bezier(0.4,0,0.2,1)",
        }}
      >
        <p
          style={{
            fontSize: 10,
            color: expanded
              ? "rgba(190,200,230,0.8)"
              : "rgba(140,150,180,0.5)",
            fontFamily: "'JetBrains Mono', monospace",
            lineHeight: 1.6,
            margin: 0,
            transition: "color 0.3s ease",
            display: expanded ? "block" : "-webkit-box",
            WebkitLineClamp: expanded ? undefined : 2,
            WebkitBoxOrient: "vertical" as const,
            overflow: expanded ? "visible" : "hidden",
          }}
        >
          {reasoning}
        </p>
      </div>

      {!expanded && (
        <div
          style={{
            fontSize: 9,
            color: "rgba(77,124,255,0.6)",
            fontFamily: "'JetBrains Mono', monospace",
            marginTop: 4,
          }}
        >
          click to expand ›
        </div>
      )}
    </div>
  );
}

// ─── Composite Display ────────────────────────────────────────────────────────

function CompositeDisplay({
  composite,
  severity,
  probability,
  consequence,
  riskTier,
}: {
  composite: number;
  severity: number;
  probability: number;
  consequence: number;
  riskTier: string;
}) {
  const tierStyle = getTierStyle(riskTier);
  const maxComposite = 125; // 5 × 5 × 5

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
        padding: "20px 16px",
        background: "rgba(8,10,20,0.72)",
        border: `1px solid ${tierStyle.primary}28`,
        borderRadius: 8,
        backdropFilter: "blur(16px) saturate(120%)",
        WebkitBackdropFilter: "blur(16px) saturate(120%)",
        boxShadow: `0 0 40px ${tierStyle.glow}, inset 0 0 40px rgba(0,0,0,0.3)`,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background glow */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at center, ${tierStyle.primary}0a 0%, transparent 70%)`,
          pointerEvents: "none",
        }}
      />

      {/* Formula */}
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10,
          color: "rgba(160,170,210,0.55)",
          letterSpacing: "0.05em",
          textAlign: "center",
        }}
      >
        COMPOSITE RISK SCORE
      </div>

      {/* Visual formula with actual numbers */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
        }}
      >
        {[
          { label: "S", value: severity, color: getScoreColor(severity) },
          { label: "×", value: null, color: "rgba(160,170,210,0.35)" },
          { label: "P", value: probability, color: getScoreColor(probability) },
          { label: "×", value: null, color: "rgba(160,170,210,0.35)" },
          { label: "C", value: consequence, color: getScoreColor(consequence) },
          { label: "=", value: null, color: "rgba(160,170,210,0.35)" },
        ].map((item, i) =>
          item.value !== null ? (
            <span
              key={i}
              style={{
                color: item.color,
                fontWeight: 700,
                fontSize: 13,
                textShadow: `0 0 8px ${item.color}60`,
              }}
            >
              {item.value}
            </span>
          ) : (
            <span key={i} style={{ color: item.color, fontSize: 11 }}>
              {item.label}
            </span>
          )
        )}
      </div>

      {/* Circular progress + composite number */}
      <div style={{ position: "relative", width: 100, height: 100 }}>
        <CircularProgress
          value={composite}
          max={maxComposite}
          color={tierStyle.primary}
          size={100}
          strokeWidth={7}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <span
            style={{
              fontSize: 30,
              fontWeight: 700,
              color: tierStyle.primary,
              fontFamily: "'JetBrains Mono', monospace",
              lineHeight: 1,
              textShadow: `0 0 20px ${tierStyle.primary}80`,
            }}
          >
            {composite}
          </span>
          <span
            style={{
              fontSize: 10,
              color: "rgba(160,170,210,0.4)",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            /{maxComposite}
          </span>
        </div>
      </div>

      {/* Risk tier label */}
      <div
        style={{
          fontSize: 12,
          fontWeight: 700,
          color: tierStyle.primary,
          fontFamily: "'JetBrains Mono', monospace",
          letterSpacing: "0.12em",
          textShadow: `0 0 12px ${tierStyle.primary}`,
          padding: "4px 14px",
          border: `1px solid ${tierStyle.primary}40`,
          borderRadius: 4,
          background: `${tierStyle.primary}12`,
        }}
      >
        {tierStyle.label}
      </div>

      {/* Percentile indicator */}
      <div
        style={{
          fontSize: 9,
          color: "rgba(160,170,210,0.45)",
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >
        {((composite / maxComposite) * 100).toFixed(0)}th percentile of max risk
      </div>
    </div>
  );
}

// ─── Main Export ──────────────────────────────────────────────────────────────

export default function RiskMatrixDrilldown({
  riskMatrix,
  riskTier,
  className = "",
}: RiskMatrixDrilldownProps) {
  const { severity, probability, consequence, composite } = riskMatrix;

  const dimensions: DimCardProps[] = [
    {
      title: "Severity",
      abbrev: "SV",
      score: severity.score,
      reasoning: severity.reasoning,
      index: 0,
    },
    {
      title: "Probability",
      abbrev: "PB",
      score: probability.score,
      reasoning: probability.reasoning,
      index: 1,
    },
    {
      title: "Consequence",
      abbrev: "CQ",
      score: consequence.score,
      reasoning: consequence.reasoning,
      index: 2,
    },
  ];

  return (
    <div
      className={className}
      style={{
        fontFamily: "'JetBrains Mono', monospace",
        width: "100%",
      }}
    >
      {/* Section header */}
      <div
        style={{
          fontSize: 11,
          color: "rgba(77,124,255,0.9)",
          letterSpacing: "0.1em",
          marginBottom: 12,
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >
        RISK MATRIX ANALYSIS
      </div>

      {/* Three dimension cards */}
      <div
        style={{
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
          marginBottom: 12,
        }}
      >
        {dimensions.map((dim) => (
          <DimensionCard key={dim.abbrev} {...dim} />
        ))}
      </div>

      {/* Composite score display */}
      <CompositeDisplay
        composite={composite}
        severity={severity.score}
        probability={probability.score}
        consequence={consequence.score}
        riskTier={riskTier}
      />
    </div>
  );
}
