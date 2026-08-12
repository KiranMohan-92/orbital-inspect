/**
 * Public landing page — the revenue front door.
 * Lives at /landing.html (separate Vite entry); the operator console stays at /.
 * Copy discipline: this product is a public-source risk SCREEN with fail-closed
 * escalation — never claim underwriting authority.
 */
import { useEffect, useRef, useState, type FormEvent } from "react";
import HeroScene from "./HeroScene";

const CONTACT_EMAIL = "kiranrocksbigtime@gmail.com";

// ─── Scroll reveal ────────────────────────────────────────────────────────────

function useRevealOnScroll() {
  const ref = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const targets = root.querySelectorAll(".reveal");
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.15 }
    );
    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  }, []);
  return ref;
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const TICKER_ITEMS = [
  ["SCREEN LATENCY P95", "< 45 SEC"],
  ["PIPELINE COMPLETION SLO", "99.5%"],
  ["EVIDENCE AGENTS", "5 STAGED"],
  ["BACKEND TESTS", "244 PASSING"],
  ["FAIL-CLOSED ESCALATION", "ENFORCED"],
  ["DEPLOY MODE", "SELF-HOSTED APP"],
  ["SPACE ECONOMY", "$630B+"],
  ["DATA SOURCES", "PUBLIC / AUDITABLE"],
];

const AGENTS = [
  {
    step: "STAGE 01",
    name: "Classification",
    color: "var(--agent-classification)",
    desc: "Verifies the image shows the claimed asset class. Rejects out-of-domain inputs outright — fail closed, never guess.",
  },
  {
    step: "STAGE 02",
    name: "Visual Damage",
    color: "var(--agent-vision)",
    desc: "Localizes anomalies with bounding boxes, severity grades, and per-finding confidence you can audit.",
  },
  {
    step: "STAGE 03",
    name: "Environment",
    color: "var(--agent-environment)",
    desc: "Correlates orbital regime, conjunction history, and space-weather exposure from public catalogs.",
  },
  {
    step: "STAGE 04",
    name: "Failure Modes",
    color: "var(--agent-failure)",
    desc: "Maps observed damage to subsystem failure pathways and time-to-degradation estimates.",
  },
  {
    step: "STAGE 05",
    name: "Risk Synthesis",
    color: "var(--agent-insurance)",
    desc: "Composes a screening priority with explicit evidence gaps. Incomplete evidence escalates to human review — always.",
  },
];

const TIERS = [
  {
    name: "DRIFT WATCH",
    price: "Free",
    period: "public portfolio",
    blurb: "Follow our public demo fleet and methodology. Kick the tires before you commit.",
    features: [
      "Public demo portfolio access",
      "Sample risk screens with full evidence chains",
      "Methodology documentation",
      "Community support",
    ],
    cta: { label: "View live demo", href: "./" },
    featured: false,
  },
  {
    name: "MISSION",
    price: "$1,500",
    period: "per month · billed annually",
    blurb: "For operators screening their own fleet.",
    features: [
      "Up to 25 tracked assets",
      "100 risk screens / month",
      "Degradation trend forecasting",
      "Signed PDF reports",
      "Email support, 1 business day",
    ],
    cta: { label: "Start a pilot", mailtoSubject: "Orbital Inspect — Mission pilot" },
    featured: false,
  },
  {
    name: "UNDERWRITER",
    price: "$4,800",
    period: "per month · billed annually",
    blurb: "For insurers and brokers screening risk across books.",
    features: [
      "Unlimited fleets and assets",
      "Full REST API + SSE streaming",
      "Evidence lineage export for audit",
      "SSO / role-based access",
      "Priority support, 4-hour response",
    ],
    cta: { label: "Talk to us", mailtoSubject: "Orbital Inspect — Underwriter plan" },
    featured: true,
  },
  {
    name: "SOVEREIGN",
    price: "Custom",
    period: "annual contract",
    blurb: "For defense primes and agencies with boundary requirements.",
    features: [
      "Self-hosted app; air-gap only if you bring a model endpoint",
      "Helm chart + your own model endpoints",
      "ITAR / CUI handling workflow",
      "Dedicated engineering support",
      "Custom evidence-source integration",
    ],
    cta: { label: "Request briefing", mailtoSubject: "Orbital Inspect — Sovereign deployment" },
    featured: false,
  },
];

function mailto(subject: string, body = "") {
  return `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Landing() {
  const rootRef = useRevealOnScroll();
  const [leadEmail, setLeadEmail] = useState("");

  const handleLeadSubmit = (e: FormEvent) => {
    e.preventDefault();
    const body = `Contact: ${leadEmail}\n\nI'd like to learn more about Orbital Inspect.`;
    window.location.href = mailto("Orbital Inspect — demo request", body);
  };

  return (
    <div className="landing-root" ref={rootRef as React.RefObject<HTMLDivElement>}>
      <div className="l-coords">51.9° N · 4.4° E — ORBITAL INSPECT GROUND SEGMENT</div>

      {/* ── Nav ── */}
      <nav
        className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-6 py-4"
        style={{
          background: "rgba(2,2,8,0.78)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(77,124,255,0.08)",
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center"
            style={{ border: "1.5px solid var(--accent-orbital)", background: "var(--accent-orbital-dim)" }}
          >
            <div className="w-2 h-2 rounded-full" style={{ background: "var(--accent-orbital)" }} />
          </div>
          <span className="text-sm tracking-[0.22em]" style={{ fontWeight: 500 }}>
            ORBITAL INSPECT
          </span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-xs tracking-[0.18em]" style={{ color: "var(--text-secondary)" }}>
          <a href="#method" className="hover:text-white transition-colors">METHOD</a>
          <a href="#platform" className="hover:text-white transition-colors">PLATFORM</a>
          <a href="#pricing" className="hover:text-white transition-colors">PRICING</a>
        </div>
        <a href="./" className="l-btn l-btn--ghost" style={{ padding: "0.55rem 1.1rem" }}>
          Launch console
        </a>
      </nav>

      {/* ── Hero ── */}
      <header className="l-hero">
        <div className="l-hero-canvas">
          <HeroScene />
        </div>
        <div className="l-hero-content">
          <div className="hero-stagger" style={{ maxWidth: "640px" }}>
            <p className="l-kicker" style={{ marginBottom: "1.6rem" }}>
              Satellite risk intelligence · evidence-first
            </p>
            <h1 className="l-display" style={{ fontSize: "clamp(3rem, 7vw, 5.4rem)", marginBottom: "1.8rem" }}>
              Price orbital risk on <em>evidence,</em> not estimates.
            </h1>
            <p className="l-body" style={{ maxWidth: "480px", marginBottom: "2.6rem" }}>
              Upload satellite imagery. Five staged AI agents return a public-source risk screen —
              damage findings, evidence gaps, and review-required actions — in under 45 seconds.
              When evidence is incomplete, the system escalates to a human. It never invents certainty.
            </p>
            <div className="flex flex-wrap gap-4">
              <a href="./" className="l-btn l-btn--scan">Launch live console →</a>
              <a href={mailto("Orbital Inspect — pilot inquiry")} className="l-btn l-btn--ghost">
                Request a pilot
              </a>
            </div>
          </div>
        </div>
        <div className="l-ticker">
          <div className="l-ticker-track">
            {[...TICKER_ITEMS, ...TICKER_ITEMS].map(([k, v], i) => (
              <span key={i}>
                {k} <b>{v}</b>
              </span>
            ))}
          </div>
        </div>
      </header>

      {/* ── 01 · The problem ── */}
      <section className="l-section" id="problem">
        <div className="l-rule reveal">
          <span className="l-index">01 / THE GAP</span>
        </div>
        <div className="grid md:grid-cols-2 gap-12 items-start">
          <h2 className="l-display reveal" style={{ fontSize: "clamp(2rem, 4vw, 3.2rem)" }}>
            A $630B economy is underwritten on <em>incomplete evidence.</em>
          </h2>
          <div className="l-body reveal reveal-d2">
            <p style={{ marginBottom: "1.2rem" }}>
              Thousands of active satellites. Rising conjunction rates. Insurance capacity retreating
              after record loss years. Yet condition assessment still runs on scattered public data,
              manual review, and institutional gut feel.
            </p>
            <p>
              Orbital Inspect turns public evidence — imagery, orbital catalogs, conjunction data,
              space weather — into one auditable screening decision: what do we know, what is missing,
              and what needs human review before capital moves.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-20">
          {[
            ["$630B+", "space economy at risk"],
            ["45s", "p95 screen latency"],
            ["99.5%", "pipeline completion SLO"],
            ["100%", "decisions human-approved"],
          ].map(([v, l], i) => (
            <div key={l} className={`reveal reveal-d${i + 1}`}>
              <div className="l-stat-value">{v}</div>
              <div className="l-kicker" style={{ marginTop: "0.8rem", fontSize: "0.62rem" }}>{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 02 · Method ── */}
      <section className="l-section" id="method">
        <div className="l-rule reveal">
          <span className="l-index">02 / METHOD</span>
        </div>
        <h2 className="l-display reveal" style={{ fontSize: "clamp(2rem, 4vw, 3.2rem)", maxWidth: "700px", marginBottom: "1.4rem" }}>
          Five agents. One auditable <em>chain of evidence.</em>
        </h2>
        <p className="l-body reveal reveal-d1" style={{ maxWidth: "560px", marginBottom: "3.5rem" }}>
          Every screen runs the same staged pipeline. Each stage emits its own findings, confidence,
          and provenance — streamed live to the console so reviewers watch the reasoning, not just the verdict.
        </p>
        <div className="l-pipeline reveal reveal-d2">
          {AGENTS.map((a) => (
            <div className="l-agent" key={a.name}>
              <div className="l-agent-bar" style={{ background: a.color }} />
              <div className="l-agent-step">{a.step}</div>
              <h3
                className="l-display"
                style={{ fontSize: "1.55rem", margin: "0.7rem 0 0.9rem", color: a.color }}
              >
                {a.name}
              </h3>
              <p className="l-body" style={{ fontSize: "0.78rem", lineHeight: 1.65 }}>{a.desc}</p>
            </div>
          ))}
        </div>
        <p className="l-body reveal" style={{ marginTop: "2rem", fontSize: "0.78rem", color: "var(--text-tertiary)" }}>
          Fail-closed by design: a degraded stage or evidence gap forces FURTHER_INVESTIGATION.
          The platform screens and prioritizes — underwriting authority stays with your team.
        </p>
      </section>

      {/* ── 03 · Platform ── */}
      <section className="l-section" id="platform">
        <div className="l-rule reveal">
          <span className="l-index">03 / PLATFORM</span>
        </div>
        <div className="grid md:grid-cols-3 gap-10">
          {[
            {
              t: "INSPECT",
              d: "Single-asset deep screens: visual damage overlays, evidence lineage, per-stage agent output, signed PDF export for the deal file.",
            },
            {
              t: "PREDICT",
              d: "Fleet-wide degradation trends with time-to-threshold forecasting. Know which asset needs attention next quarter, not after the claim.",
            },
            {
              t: "PROTECT",
              d: "ITAR/CUI-aware classification workflow, role-based access, full audit trail. Self-host the app; default screening still needs a model API unless you bring your own endpoint.",
            },
          ].map((f, i) => (
            <div key={f.t} className={`reveal reveal-d${i + 1}`}>
              <h3 className="l-display" style={{ fontSize: "2.1rem", marginBottom: "1rem" }}>
                <em style={{ color: "var(--accent-orbital)" }}>{f.t}</em>
              </h3>
              <p className="l-body" style={{ fontSize: "0.85rem" }}>{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── 04 · Pricing ── */}
      <section className="l-section" id="pricing">
        <div className="l-rule reveal">
          <span className="l-index">04 / PRICING</span>
        </div>
        <h2 className="l-display reveal" style={{ fontSize: "clamp(2rem, 4vw, 3.2rem)", marginBottom: "3.5rem" }}>
          One bad screen costs more than <em>a year of this.</em>
        </h2>
        <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-5">
          {TIERS.map((tier, i) => (
            <div key={tier.name} className={`l-tier reveal reveal-d${i + 1} ${tier.featured ? "l-tier--featured" : ""}`}>
              {tier.featured && (
                <span
                  className="l-kicker"
                  style={{ color: "var(--accent-scan)", fontSize: "0.6rem", position: "absolute", top: "0.9rem", right: "1rem" }}
                >
                  Most adopted
                </span>
              )}
              <div>
                <div className="l-kicker" style={{ marginBottom: "1.1rem" }}>{tier.name}</div>
                <div className="l-tier-price">
                  {tier.price}
                  <br />
                  <small>{tier.period}</small>
                </div>
              </div>
              <p className="l-body" style={{ fontSize: "0.8rem" }}>{tier.blurb}</p>
              <ul>
                {tier.features.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <a
                href={"href" in tier.cta && tier.cta.href ? tier.cta.href : mailto(tier.cta.mailtoSubject ?? "Orbital Inspect inquiry")}
                className={`l-btn ${tier.featured ? "l-btn--scan" : "l-btn--ghost"}`}
                style={{ marginTop: "auto", justifyContent: "center" }}
              >
                {tier.cta.label}
              </a>
            </div>
          ))}
        </div>
        <p className="l-body reveal" style={{ marginTop: "2rem", fontSize: "0.74rem", color: "var(--text-tertiary)" }}>
          All paid plans include onboarding with our engineering team. Annual contracts, invoiced. Source available under BSL 1.1.
        </p>
      </section>

      {/* ── Final CTA ── */}
      <section className="l-section" style={{ paddingBottom: "5rem" }}>
        <div
          className="reveal"
          style={{
            border: "1px solid rgba(0,212,255,0.25)",
            background:
              "radial-gradient(ellipse 70% 120% at 50% 0%, rgba(0,212,255,0.07), transparent 60%), rgba(4,5,12,0.9)",
            padding: "4.5rem 2rem",
            textAlign: "center",
          }}
        >
          <h2 className="l-display" style={{ fontSize: "clamp(2.2rem, 5vw, 3.6rem)", marginBottom: "1.2rem" }}>
            See your fleet the way <em>capital sees it.</em>
          </h2>
          <p className="l-body" style={{ maxWidth: "460px", margin: "0 auto 2.4rem" }}>
            Tell us about your fleet or book. We answer within one business day.
          </p>
          <form
            onSubmit={handleLeadSubmit}
            className="flex flex-col sm:flex-row gap-3 justify-center items-stretch"
            style={{ maxWidth: "560px", margin: "0 auto" }}
          >
            <input
              type="email"
              required
              value={leadEmail}
              onChange={(e) => setLeadEmail(e.target.value)}
              placeholder="you@operator.space"
              aria-label="Work email"
              style={{
                flex: 1,
                background: "var(--bg-input)",
                border: "1px solid rgba(255,255,255,0.14)",
                padding: "0.95rem 1.2rem",
                fontFamily: "var(--font-tele)",
                fontSize: "0.82rem",
                color: "#fff",
                outline: "none",
              }}
            />
            <button type="submit" className="l-btn l-btn--scan" style={{ justifyContent: "center" }}>
              Request demo
            </button>
          </form>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer
        className="flex flex-col md:flex-row items-center justify-between gap-4 px-8 py-8"
        style={{ borderTop: "1px solid rgba(77,124,255,0.1)" }}
      >
        <span className="text-xs tracking-[0.18em]" style={{ color: "var(--text-tertiary)" }}>
          ORBITAL INSPECT · SATELLITE RISK INTELLIGENCE
        </span>
        <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          BSL 1.1 · Screening intelligence only — not an insurance product ·{" "}
          <a href="https://github.com/KiranMohan-92/orbital-inspect" style={{ color: "var(--text-secondary)" }}>
            GitHub
          </a>
        </span>
      </footer>
    </div>
  );
}
