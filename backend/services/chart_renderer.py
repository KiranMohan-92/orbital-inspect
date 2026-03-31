"""
Publication-quality chart renderer for NASA-style PDF reports.
All functions return PNG bytes suitable for embedding in PDFs.
"""
import io

import matplotlib
matplotlib.use('Agg')  # headless rendering, no GUI
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

DARK_BG = '#0a0a14'
LIGHT_TEXT = '#e4e6ef'
DIM_TEXT = '#8890a8'
GRID_COLOR = '#1a1a2e'

# Severity color thresholds for scores 1-5
_SCORE_COLORS = {
    1: '#22c55e',
    2: '#22c55e',
    3: '#eab308',
    4: '#f97316',
    5: '#ef4444',
}

# Risk tier thresholds for composite score (max 125)
_RISK_TIERS = [
    (37,  'LOW RISK',      '#22c55e'),
    (75,  'MODERATE RISK', '#eab308'),
    (100, 'HIGH RISK',     '#f97316'),
    (125, 'CRITICAL RISK', '#ef4444'),
]


def _save_figure(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format='png',
        dpi=150,
        bbox_inches='tight',
        facecolor=fig.get_facecolor(),
        edgecolor='none',
    )
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _score_color(score: int) -> str:
    score = max(1, min(5, int(score)))
    return _SCORE_COLORS[score]


def _risk_tier(composite: int, max_score: int = 125) -> tuple[str, str]:
    """Return (label, color) for a composite score."""
    proportion = composite / max_score if max_score else 0
    scaled = proportion * 125  # normalise to 0-125 scale for tier lookup
    for threshold, label, color in _RISK_TIERS:
        if scaled <= threshold:
            return label, color
    return _RISK_TIERS[-1][1], _RISK_TIERS[-1][2]


# ---------------------------------------------------------------------------
# 1. Risk Matrix Chart
# ---------------------------------------------------------------------------

def render_risk_matrix_chart(
    severity_score: int,
    probability_score: int,
    consequence_score: int,
    composite: int,
    severity_reasoning: str = '',
    probability_reasoning: str = '',
    consequence_reasoning: str = '',
) -> bytes:
    """
    Three vertical bars (Severity, Probability, Consequence) on a dark
    background plus a composite score label.

    Returns PNG bytes.
    """
    fig, ax = plt.subplots(figsize=(8, 3))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    bars = [
        ('S', severity_score,    severity_reasoning),
        ('P', probability_score, probability_reasoning),
        ('C', consequence_score, consequence_reasoning),
    ]

    x_positions = [0.5, 2.0, 3.5]

    for x, (label, score, reasoning) in zip(x_positions, bars):
        color = _score_color(score)

        # Bar background (max height = 5)
        ax.bar(x, 5, width=0.8, color=GRID_COLOR, zorder=1)
        # Actual bar
        ax.bar(x, score, width=0.8, color=color, zorder=2, alpha=0.92)

        # Score number on bar
        ax.text(
            x, score / 2, str(score),
            ha='center', va='center',
            color='white', fontsize=18, fontweight='bold',
            fontfamily='monospace', zorder=3,
        )

        # Label above bar
        ax.text(
            x, 5.25, label,
            ha='center', va='bottom',
            color=LIGHT_TEXT, fontsize=11, fontweight='bold',
            fontfamily='monospace',
        )

        # Reasoning text below bar (truncate if too long)
        short_reason = (reasoning[:22] + '…') if len(reasoning) > 22 else reasoning
        ax.text(
            x, -0.35, short_reason,
            ha='center', va='top',
            color=DIM_TEXT, fontsize=6.5, fontfamily='monospace',
            wrap=True,
        )

    # Composite score label (right side)
    ax.text(
        5.2, 2.5,
        f'{composite}\n/ 125',
        ha='center', va='center',
        color=LIGHT_TEXT, fontsize=22, fontweight='bold',
        fontfamily='monospace',
    )
    ax.text(
        5.2, 1.1,
        'COMPOSITE',
        ha='center', va='center',
        color=DIM_TEXT, fontsize=7, fontfamily='monospace',
    )

    ax.set_xlim(-0.2, 6.0)
    ax.set_ylim(-0.8, 6.0)
    ax.set_xticks([])
    ax.set_yticks(range(1, 6))
    ax.yaxis.set_tick_params(labelcolor=DIM_TEXT, labelsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_ylabel('Score', color=DIM_TEXT, fontsize=8, fontfamily='monospace')
    ax.yaxis.label.set_color(DIM_TEXT)
    ax.tick_params(colors=DIM_TEXT)

    fig.tight_layout(pad=0.6)
    return _save_figure(fig)


# ---------------------------------------------------------------------------
# 2. Degradation Timeline
# ---------------------------------------------------------------------------

def render_degradation_timeline(
    design_life_years: float | None,
    estimated_age_years: float | None,
    remaining_life_years: float | None,
    power_margin_pct: float | None,
    annual_degradation_pct: float | None,
) -> bytes:
    """
    Power margin (%) vs time chart with history line, projection dashes,
    critical threshold, and EOL markers.

    Returns PNG bytes.
    """
    # Defaults for missing values
    design_life = design_life_years if design_life_years is not None else 15.0
    age = estimated_age_years if estimated_age_years is not None else 0.0
    remaining = remaining_life_years if remaining_life_years is not None else max(0.0, design_life - age)
    power_margin = power_margin_pct if power_margin_pct is not None else 100.0
    degradation = annual_degradation_pct if annual_degradation_pct is not None else 0.0

    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    x_max = max(design_life * 1.1, age + remaining + 1, 20)

    # Build history line: power started at 100% at year 0
    # and declined at `degradation` pct per year
    if age > 0 and degradation > 0:
        hist_x = np.linspace(0, age, max(2, int(age * 20)))
        hist_y = np.clip(100.0 - degradation * hist_x, 0, 100)
    else:
        hist_x = np.array([0.0, age])
        hist_y = np.array([100.0, power_margin])

    ax.plot(hist_x, hist_y, color='#60a5fa', linewidth=2, label='Power Margin (history)')

    # Projection: dashed line from current age forward to EOL
    proj_end = age + remaining
    if proj_end > age and degradation >= 0:
        proj_x = np.linspace(age, proj_end, max(2, int(remaining * 20 + 1)))
        proj_y = np.clip(power_margin - degradation * (proj_x - age), 0, 100)
        ax.plot(proj_x, proj_y, color='#60a5fa', linewidth=2,
                linestyle='--', label='Projection', alpha=0.7)

    # Critical threshold
    ax.axhline(15, color='#ef4444', linestyle='--', linewidth=1.2,
               label='Critical threshold (15%)', alpha=0.85)

    # Current age vertical line
    ax.axvline(age, color='#3b82f6', linewidth=1.5,
               label=f'Current age ({age:.1f} yr)', alpha=0.9)

    # Design life EOL vertical line
    ax.axvline(design_life, color='#6b7280', linestyle='--', linewidth=1.2,
               label=f'Design EOL ({design_life:.0f} yr)', alpha=0.7)

    # Revised EOL if it differs meaningfully from design life
    revised_eol = age + remaining
    if abs(revised_eol - design_life) > 0.5:
        ax.axvline(revised_eol, color='#f97316', linewidth=1.5, linestyle='-.',
                   label=f'Revised EOL ({revised_eol:.1f} yr)', alpha=0.85)

    ax.set_xlim(0, x_max)
    ax.set_ylim(0, 110)
    ax.set_xlabel('Years', color=LIGHT_TEXT, fontsize=9, fontfamily='monospace')
    ax.set_ylabel('Power Margin (%)', color=LIGHT_TEXT, fontsize=9, fontfamily='monospace')
    ax.tick_params(colors=DIM_TEXT, labelsize=8)
    ax.xaxis.label.set_color(LIGHT_TEXT)
    ax.yaxis.label.set_color(LIGHT_TEXT)

    ax.grid(True, color=GRID_COLOR, linewidth=0.6, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)

    legend = ax.legend(
        fontsize=7, facecolor=DARK_BG, edgecolor=GRID_COLOR,
        labelcolor=DIM_TEXT, loc='upper right',
    )

    fig.tight_layout(pad=0.8)
    return _save_figure(fig)


# ---------------------------------------------------------------------------
# 3. Damage Distribution
# ---------------------------------------------------------------------------

def render_damage_distribution(damages: list[dict]) -> bytes:
    """
    Horizontal bar chart grouped by severity.

    Returns PNG bytes.
    """
    SEVERITY_ORDER = ['CRITICAL', 'SEVERE', 'MODERATE', 'MINOR']
    SEVERITY_COLORS_MAP = {
        'CRITICAL': '#ef4444',
        'SEVERE':   '#f97316',
        'MODERATE': '#eab308',
        'MINOR':    '#22c55e',
    }

    fig, ax = plt.subplots(figsize=(6, 3))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    if not damages:
        ax.text(
            0.5, 0.5, 'No anomalies detected',
            ha='center', va='center', transform=ax.transAxes,
            color=DIM_TEXT, fontsize=13, fontfamily='monospace',
        )
        ax.set_axis_off()
        fig.tight_layout(pad=0.6)
        return _save_figure(fig)

    # Count by severity
    counts = {sev: 0 for sev in SEVERITY_ORDER}
    for d in damages:
        sev = d.get('severity', 'MINOR').upper()
        if sev in counts:
            counts[sev] += 1
        else:
            counts['MINOR'] += 1

    # Only render severities that have at least 1 item
    present = [(sev, counts[sev]) for sev in SEVERITY_ORDER if counts[sev] > 0]
    labels = [p[0] for p in present]
    values = [p[1] for p in present]
    colors = [SEVERITY_COLORS_MAP[p[0]] for p in present]

    y_pos = range(len(labels))
    bars = ax.barh(list(y_pos), values, color=colors, height=0.55, alpha=0.88)

    # Count labels on bars
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
            str(val),
            va='center', color=LIGHT_TEXT, fontsize=9, fontfamily='monospace',
        )

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, color=LIGHT_TEXT, fontsize=8, fontfamily='monospace')
    ax.set_xlabel('Count', color=DIM_TEXT, fontsize=8, fontfamily='monospace')
    ax.tick_params(colors=DIM_TEXT, labelsize=8)
    ax.set_xlim(0, max(values) + 1.5)
    ax.grid(axis='x', color=GRID_COLOR, linewidth=0.6, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)

    fig.tight_layout(pad=0.8)
    return _save_figure(fig)


# ---------------------------------------------------------------------------
# 4. Composite Gauge
# ---------------------------------------------------------------------------

def render_composite_gauge(composite: int, max_score: int = 125) -> bytes:
    """
    Semicircular arc gauge showing composite risk score.

    Returns PNG bytes.
    """
    fig, ax = plt.subplots(figsize=(4, 3))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)
    ax.set_aspect('equal')
    ax.axis('off')

    proportion = max(0.0, min(1.0, composite / max_score if max_score else 0))

    # Background arc (full 180 degrees, left to right = pi to 0)
    theta_bg = np.linspace(np.pi, 0, 200)
    r = 1.0
    thickness = 0.22
    r_inner = r - thickness

    # Draw background track
    ax.fill_between(
        np.concatenate([r * np.cos(theta_bg), r_inner * np.cos(theta_bg[::-1])]),
        np.concatenate([r * np.sin(theta_bg), r_inner * np.sin(theta_bg[::-1])]),
        color=GRID_COLOR, zorder=1,
    )

    # Color segments: green 0-30%, yellow 30-60%, orange 60-72%, red 72-100%
    # (mapped to 0-125 scale)
    segment_defs = [
        (0,    30,  '#22c55e'),
        (30,   60,  '#eab308'),
        (60,   90,  '#f97316'),
        (90,   125, '#ef4444'),
    ]

    for seg_start, seg_end, seg_color in segment_defs:
        seg_start_norm = seg_start / max_score
        seg_end_norm = seg_end / max_score
        fill_norm = proportion  # how far the gauge fills

        actual_start = seg_start_norm
        actual_end = min(seg_end_norm, fill_norm)
        if actual_end <= actual_start:
            break

        # Map [0,1] proportion to angles [pi, 0]
        angle_start = np.pi - actual_start * np.pi
        angle_end = np.pi - actual_end * np.pi

        theta_seg = np.linspace(angle_start, angle_end, 100)
        outer_x = r * np.cos(theta_seg)
        outer_y = r * np.sin(theta_seg)
        inner_x = r_inner * np.cos(theta_seg[::-1])
        inner_y = r_inner * np.sin(theta_seg[::-1])

        ax.fill(
            np.concatenate([outer_x, inner_x]),
            np.concatenate([outer_y, inner_y]),
            color=seg_color, zorder=2, alpha=0.9,
        )

    # Score tier color for text
    tier_label, tier_color = _risk_tier(composite, max_score)

    # Center number
    ax.text(
        0, 0.28, str(composite),
        ha='center', va='center',
        color=tier_color, fontsize=28, fontweight='bold',
        fontfamily='monospace', zorder=5,
    )
    ax.text(
        0, 0.05, f'/ {max_score}',
        ha='center', va='center',
        color=DIM_TEXT, fontsize=10, fontfamily='monospace', zorder=5,
    )
    ax.text(
        0, -0.18, tier_label,
        ha='center', va='center',
        color=tier_color, fontsize=8, fontweight='bold',
        fontfamily='monospace', zorder=5,
    )

    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.45, 1.25)

    fig.tight_layout(pad=0.5)
    return _save_figure(fig)
