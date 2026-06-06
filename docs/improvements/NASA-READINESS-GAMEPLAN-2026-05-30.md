# Orbital Inspect → NASA/SpaceX-Grade: Gap Analysis & Game Plan

Date: 2026-05-30
Method: 7-subsystem code audit (multi-agent) + first-hand code review + cited 2026 web research.
Evidence file: `.omx/context/nasa-readiness-evidence-harvest.json`
Source refresh: 2026-06-06 spot-check confirmed the live Starlink Space Safety CDM/trajectory
docs, OSC TraCSS page, and NASA SBIR/STTR 2026 information hub still support the core roadmap
claims. Re-verify solicitation-specific dates and topic numbers before external use.

---

## 0. The one-paragraph truth

Orbital Inspect is an **honest, well-engineered public-data screening product** with a genuinely
disciplined authority layer (`assessment_mode_service.py` fail-closes to `FURTHER_INVESTIGATION`
and already names `covariance_cdm_quality` as a required evidence class). But the thing that would
make NASA or SpaceX pay is **not** the agent count, the UI, or the "self-evolving" framing. It is
**standards-native orbital evidence + computed collision probability + verifiable assurance
artifacts** — and almost none of that exists in code. The product already speaks the right
vocabulary at its *gate*; it has **no engine behind the gate**. Closing that specific distance is
the entire game.

---

## 1. Brutal truths (what the audit actually found)

| # | Brutal truth | Evidence |
|---|---|---|
| 1 | The **"5-agent AI pipeline" is sequential prompt-chaining**, not agentic reasoning. No tool loop, no planning, no inter-agent messaging. Stages pass JSON *strings* to the next. | `orchestrator.py:246-294`; runtime map **4.5/10** |
| 2 | **Single-model dependency** (Gemini) with no ensemble, second-opinion, self-consistency, or model-disagreement detection. Output uses Gemini JSON-mode (`response_mime_type="application/json"`, `gemini_service.py:150`), so JSON *validity* is decoder-constrained — but **no `response_schema` is passed**, so the field-level contract is prompt-instructed only (shape can drift). | runtime map |
| 3 | The **"agent-evolution evals" are `grep`** (`file_contains`/`json_field_equals`). Zero behavioral or accuracy evals. They verify *strings exist in files*, not that the system behaves correctly. | `run_agent_evals.py:144-199`; evals map **3.5/10** |
| 4 | The **self-evolving "closed loop" is ~0% implemented** — `backend/autoresearch`, `backend/knowledge`, `backend/harness`, `agent_evolution` **do not exist**. The brainstorming plan oversells ~6,000 lines of nonexistent infrastructure. | dir check; self-evolution map **2.5/10** |
| 5 | **No CCSDS handling** (no OEM/OMM/CDM/NDM/KVN parsers) and **no covariance ingestion or computed Pc**. Collision probability is *parsed/read-through*, never computed. **This is the core NASA/SpaceX requirement.** | data map **3.5/10**; decision map **4.0/10** |
| 6 | **No SGP4 / propagation library** installed — propagation is permanently unavailable. The "orbital environment" stage is the LLM *narrating* debris/weather, not computing flux. | data map; `orbital_environment_agent` |
| 7 | Core risk number is an **RPN-style S×P×C product** (severity×probability×consequence; the server *overwrites* the model's value to enforce `composite = S×P×C`, `insurance_risk_agent.py:140`). Multiplying ordinal 1–5 scores is statistically invalid, not actuarial, and not a probability. | decision map |
| 8 | **No accuracy/calibration measurement** of AI outputs against ground truth; `DatasetRegistry` is a metadata catalog with **no data pipeline**; **no reproducibility-from-SHA** for the AI path; the full pipeline is **never run against a real model in CI** (fully stubbed). | evals map |
| 9 | **Zero ATO artifacts** — no NIST 800-53 / NPR 7150.2 control mapping, no SSP, no POA&M. ITAR/CUI marking is *computed but never enforced* on API responses/downloads (no enforcement in `middleware/`/`api/`); "air-gap" claim is contradicted by the hard Gemini SaaS dependency; the audit log has **no tamper-evidence** (no hash-chaining/append-only) and audit rows fall under retention purge. | ops map **5.5/10** |
| 10 | Much of the API surface has **no operator UI**; "continuous monitoring," multi-region DR, and 3D "Mission Control" are **documentation/placeholder-grade**. | product map **5.5/10** |

**Net:** the README/AGENTS docs describe a system ~2 maturity tiers above the code. That gap is itself
a NASA red flag (NASA evaluates *evidence*, not narrative). Closing the doc↔reality gap is step zero.

---

## 2. Current-state scorecard (audited)

| Subsystem | Maturity /10 |
|---|---|
| API / Frontend / Product | 5.5 |
| Ops / Security / Compliance | 5.5 |
| Runtime agent pipeline & resilience | 4.5 |
| Decision / Risk / Authority | 4.0 |
| Evidence / Data / Provenance | 3.5 |
| Evals / Tests / Verifiability | 3.5 |
| Self-evolution / control plane | 2.5 |

Dimension scores (current → achievable in 12 mo): performance-vs-goal 4→8 · verifiability 3→8 ·
self-evolution 2→7 · evals 3→8 · **nasa-spacex-fit 2→8 (the moat)** · architecture 4→8.

---

## 3. North star (redefine "world's best" for THIS use case)

> **The world's best system here is not the most autonomous — it is the one whose every risk number
> is traceable to standards-native evidence, carries calibrated uncertainty, and refuses to answer
> when the evidence can't support it.** Autonomy is a *delivery* feature; verifiable truth under
> uncertainty is the *product*.

This is also why the existing fail-closed discipline is the strongest asset — it is the exact
epistemic posture NASA CARA and Starlink Space Safety operate under (NULL Pc when covariance is
absent/non-PSD). Build the engine *up to* the gate that already exists.

---

## 4. The moat: standards-native orbital evidence (what NASA/SpaceX actually require)

These are now concrete, sourced requirements — not vibes:

- **CCSDS message support**: OEM (Orbit Ephemeris Message, CCSDS 502.0-B), OMM (Orbit Mean-Elements,
  the modern TLE replacement), CDM (Conjunction Data Message, CCSDS 508.0-B), KVN/XML encodings.
  *Speak these and you can exchange data with Space-Track, TraCSS, and Starlink; don't and you're a toy.*
- **Operator-ephemeris ingestion** in **MEME J2000.0**, km / km·s⁻¹, with **a positive-semidefinite
  covariance per state vector**; tag `state_source` (`operator_ephemeris` vs sensor). (Starlink API spec.)
- **Computed Pc** via standard methods (Foster/Chan/Alfano/Patera), with **hard-body radius** and
  **NULL Pc when covariance is missing or non-PSD** — the same rule SpaceX publishes. SpaceX maneuver
  threshold **Pc > 3e-7**; classic threshold **1e-4**.
- **SP vs SGP4 separation**: SGP4 from TLE/OMM for screening; special-perturbations/operator ephemeris
  for decisions. Never silently mix.
- **Covariance realism / quality gates**: frame, epoch, PSD check, condition number, scale sanity.
- **Assurance artifacts**: NASA-STD-7009 model-credibility pedigree (V&V evidence, uncertainty
  quantification, recommended-use bounds), NPR 7150.2 software classification + traceability,
  IV&V-style independent evidence. *NASA buys evidence, not output.*

Sources: [Starlink CDMs](https://docs.space-safety.starlink.com/docs/tutorial-basics/cdms/) ·
[Starlink Trajectories](https://docs.space-safety.starlink.com/docs/tutorial-basics/trajectories/) ·
[Space-Track Spaceflight Safety Handbook v1.7](https://www.space-track.org/documents/SFS_Handbook_For_Operators_V1.7.pdf) ·
[NASA Conjunction Assessment & Collision Avoidance (OCE-51)](https://nodis3.gsfc.nasa.gov/OCE_docs/OCE_51.pdf).

---

## 5. Target architecture (what makes it world-class)

```
              ┌──────────────────────── EVIDENCE BACKBONE (the moat) ────────────────────────┐
              │ CCSDS I/O (OEM/OMM/CDM/KVN) · operator-ephemeris ingest (MEME J2000, PSD cov) │
              │ SGP4/SP propagation (orekit/astropy) · covariance validators · Pc engine      │
              │ content-hashed, signed provenance on every datum                              │
              └───────────────────────────────────┬──────────────────────────────────────────┘
                                                   │ structured, validated evidence (not strings)
        ┌──────────────────────────────────────────▼─────────────────────────────────────────┐
        │ DETERMINISTIC RISK CORE (auditable, no LLM in the number)                            │
        │ computed Pc + uncertainty · physics-based exposure · calibrated scores w/ CIs        │
        └──────────────────────────────────────────┬─────────────────────────────────────────┘
                                                   │
        ┌──────────────────────────────────────────▼─────────────────────────────────────────┐
        │ LLM REASONING LAYER (explanation + triage, NEVER the safety number)                  │
        │ multi-model (Gemini+Claude+…) cross-check · decoder-constrained JSON · tool-calling   │
        │ cited grounding · disagreement → FURTHER_INVESTIGATION                                │
        └──────────────────────────────────────────┬─────────────────────────────────────────┘
                                                   │
        ┌──────────────────────────────────────────▼─────────────────────────────────────────┐
        │ AUTHORITY GATE (already strong — keep) → operator UI / CDM export / signed report     │
        └──────────────────────────────────────────────────────────────────────────────────────┘

        ┌──────────────────── AGENT EVOLUTION CONTROL PLANE (production-bounded) ──────────────┐
        │ run ledger → failure taxonomy → eval store (BEHAVIORAL) → isolated experiment →       │
        │ promotion gate (eval-gated, no self-approve) → rollback monitor                       │
        └──────────────────────────────────────────────────────────────────────────────────────┘
```

**The decisive architectural decision:** *the LLM never produces the safety-critical number.* Pc,
covariance quality, and decision thresholds are deterministic, testable code. The LLM explains,
triages, and drafts — which is exactly the boundary NASA's emerging AI-assurance posture can accept.
This also dissolves the single-model risk and the "hallucinated Pc" problem.

---

## 6. Self-evolving / "Hermes-like" — done right, production-bounded

The existing PRD's *philosophy* is correct ("evolution not drift"); the *implementation* is absent.
Build the **minimum real closed loop** before any autonomy:

1. **Agent-run ledger** (DB): every agent/eval run — model, prompt version, inputs, outputs, cost,
   latency, degraded flag, override outcome. *Without this you cannot tell improvement from anecdote.*
2. **Behavioral eval store** replacing grep graders: golden cases with ground truth (e.g., known
   conjunctions with published Pc; CCSDS round-trip fixtures; covariance-PSD edge cases). Graders run
   the *actual* code/pipeline and assert outcomes + calibration, not string presence.
3. **Isolated experiment factory** (git worktrees) with hypothesis + expected eval delta + rollback.
4. **Promotion gate**: deterministic tests pass + behavioral evals improve-or-neutral + release-critical
   regressions 100% green + review artifact exists + no authority weakening. **No self-merge, no
   self-approval** (and *enforce* it — today it's a self-authored rubber stamp).
5. **Rollback monitor**: eval pass rate, degraded-run rate, `FURTHER_INVESTIGATION` rate, review-reject
   rate, cost/latency per successful task.
6. **Validator-gated autoresearch loop** (the genuinely valuable autonomy): mission → validator (source
   URLs + required fields) → cited requirement-delta artifact → architect review → eval case. Stops on
   *validation evidence*, not model confidence — mirroring the product's own fail-closed rule.

SOTA context to borrow from (not reinvent): ADAS / Gödel-agent self-modification, DSPy-style
eval-driven pipeline optimization, "AI-Scientist" conjecture loops — but **all gated by behavioral
evals**, which is the difference between compounding and drift.

---

## 7. How to land a NASA/SpaceX deal NOW (entry paths, sourced)

The market window is open *today*:

- **TraCSS (Office of Space Commerce)** — production release anticipated **2026**; updated specs
  published **Jan 22 2026**; OSC is **soliciting "Commercial Conjunction Assessment Screening
  Services" via GSA's Global Data Marketplace**, and running pathfinders (COLA Gap Pathfinder added
  Kayhan). Pilot users include **SpaceX, Iridium, OneWeb, Maxar, Planet, Intelsat, Amazon Kuiper**.
  → *This is the single most concrete on-ramp.* ([OSC TraCSS](https://space.commerce.gov/traffic-coordination-system-for-space-tracss/) ·
  [Commercial CA Screening solicitation/Pathfinder](https://space.commerce.gov/office-of-space-commerce-announces-new-commercial-pathfinder-project-for-tracss/) ·
  [SI 2.0 sources sought](https://space.commerce.gov/office-of-space-commerce-solicits-sources-for-tracss-system-integrator-2-0/))
- **NASA SBIR/STTR** — now a **rolling Broad Agency Announcement** (released **Apr 17 2026**, open to
  **Sep 30 2027**); explicitly funds AI for mission planning, **autonomous conjunction assessment**,
  ML collision avoidance. Phase I ≈ **$225K**, non-dilutive, fast. ([NASA SBIR 2026 hub](https://www.nasa.gov/sbir_sttr/nasa-sbir-sttr-program-program-year-2026-information-hub/) ·
  [SAM.gov BAA](https://sam.gov/workspace/contract/opp/bf991b7587b1438ca7930a9b840635dc/view))
- **USSF SpaceWERX / JCO / TAP Lab (Apollo)** and **SDA Unified Data Library** onboarding — defense SSA
  on-ramps; pair with SBIR for STRATFI/TACFI matching.
- **Reality check on incumbents' path:** the OSC **Consolidated Pathfinder spent $15.5M across 5
  contractors**; **LeoLabs** grew USG bookings **+180% since 2024 ($29.4M YTD Sep 2025)** and licensed
  its Object Catalog to DoC+USSF; **Slingshot** hit **CMMC L2 (Feb 2026)**. → A newcomer wins on a
  *differentiated capability* (verifiable, evidence-first, insurance-bridged), not on out-tracking
  radars it doesn't own. ([OSC pathfinder spend](https://space.commerce.gov/office-of-space-commerce-places-orders-for-ssa-data-quality-monitoring-pathfinder/) ·
  [LeoLabs award](https://www.prnewswire.com/news-releases/leolabs-receives-contract-from-the-us-department-of-commerce-and-us-space-force-to-jointly-license-its-object-catalog-for-space-safety-and-security-missions-302635996.html))

**Compliance artifacts to start now (gate every gov deal):** NPR 7150.2 software classification +
requirements traceability; NASA-STD-7009 model-credibility package; SBOM signing + SLSA provenance;
NIST 800-53 control mapping → SSP/POA&M (FedRAMP/IL trajectory); SSO/SAML + MFA + PIV/CAC; tamper-
evident (append-only, hash-chained) audit log; ITAR/CUI *enforcement* on responses/downloads.

### The lighthouse pilot (what earns credibility)
**"Verifiable conjunction screening + evidence-gap report on a real operator's fleet."** Ingest the
operator's **OEM/ephemeris (with covariance)** and Space-Track CDMs, **compute Pc** with PSD validation
and **NULL when covariance is bad**, emit a **signed CCSDS-compatible CDM + NASA-7009 credibility
sheet**, and show the fail-closed gate in action. One credible operator/insurer reference + a TraCSS
pathfinder data-quality result = the proof points that convert.

---

## 8. Monetization — make it earn

**Buyers (in order of reachability):**
1. **Space insurers / reinsurers / brokers** — *the fastest first dollar.* Hard market: ~$550–580M
   global capacity, **2023 claims ~$995M (loss ratio ~200%)**, war-risk exclusions widening,
   "structurally mispriced LEO risk," and **underwriters beginning to require demonstrated SSA practices
   as a condition of coverage.** An evidence-first, auditable risk screen is *exactly* an underwriting
   input. ([WTW Marketplace Realities 2026](https://www.wtwco.com/en-us/insights/2025/10/insurance-marketplace-realities-2026-aviation-and-space))
2. **Satellite operators** (esp. mid-size LEO constellations) — conjunction screening + maneuver
   decision support + regulatory evidence.
3. **Civil/defense SSA** — TraCSS commercial CA screening services; SDA/UDL; allied agencies.

**Offerings:** (a) **Underwriting Risk Evidence Pack** per asset/policy (insurers) — productize the
existing screen, but with computed Pc + credibility sheet; (b) **Conjunction Screening API** (per-asset
/ per-CDM, SaaS); (c) **Compliance/evidence exports** (CCSDS CDM + audit). **Revenue model:** SBIR
(non-dilutive seed) → insurer pilot retainers → per-asset/API ARR → gov data-services contract.
**Market frame:** commercial SSA $1.69B(2025)→$1.82B(2026)→$2.61B(2031) @7.5% CAGR; in-orbit insurance
the fastest-growing segment (~11% CAGR). ([SSA market](https://www.mordorintelligence.com/industry-reports/space-situational-awareness-systems-market))

**First-dollar plan:** file 1–2 **NASA SBIR Phase I** proposals (autonomous CA / AI-assured risk) +
sign **1 insurer or broker pilot** for the Underwriting Risk Evidence Pack. Those two fund the moat build.

---

## 9. Roadmap (12 months, evidence-gated)

| Phase | Weeks | Deliverables | Success criteria |
|---|---|---|---|
| **0. Honesty + foundation** | 1–3 | Reconcile docs↔code (stop over-claiming); add SGP4/SP propagation (orekit/astropy); content-hash + sign provenance; enforce ITAR/CUI on responses | Docs match reality; propagation works on real TLE/OEM; provenance hashes populated |
| **1. Standards-native evidence (MOAT)** | 3–10 | CCSDS OEM/OMM/CDM parse+emit (KVN/XML); operator-ephemeris ingest (MEME J2000, PSD covariance); covariance validators | Round-trip CCSDS fixtures pass; reject non-PSD covariance |
| **2. Deterministic Pc engine** | 8–14 | Computed Pc (Foster/Chan/Alfano) + hard-body radius; **NULL Pc when covariance bad**; replace FMEA-RPN with calibrated risk + CIs | Pc matches published reference cases; NULL rule verified; calibration measured |
| **3. Behavioral evals + assurance** | 10–18 | Behavioral eval store (golden conjunctions, CCSDS, covariance edges); accuracy/calibration vs ground truth; NASA-7009 credibility package; reproducible-from-SHA eval runs in CI | Evals run real code; calibration reported; 7009 pack reviewable |
| **4. LLM reasoning layer (re-scoped)** | 14–20 | Multi-model cross-check; decoder-constrained JSON; LLM out of the safety number; disagreement→escalate | No LLM in Pc path; cross-model disagreement triggers gate |
| **5. Control plane + pilot** | 18–30 | Run ledger, promotion gate (enforced no-self-approve), rollback monitor, validator-gated autoresearch; **lighthouse operator/insurer pilot**; SBIR delivery | Closed loop live; pilot reference secured; ATO artifacts started |

---

## 10. Top risks

| Risk | Mitigation |
|---|---|
| ITAR/EAR on orbital data & covariance | US-person controls, data-handling boundary, counsel review *before* operator data touches the system |
| Over-claiming to NASA (current doc↔code gap) destroys credibility | Phase 0 honesty pass; lead with evidence + credibility sheets, never narrative |
| LLM-in-the-loop rejected for safety decisions | Architecture *removes* LLM from the safety number by design |
| Incumbents own sensor data | Don't compete on observations — compete on verifiable analytics + insurance bridge; consume their/Space-Track/TraCSS data |
| Session/usage limits stalling autonomous runs (seen during this very audit) | Checkpoint long agent jobs; durable evidence harvest; budget-aware scheduling |

---

## 11. Immediate next 30 days

1. **Phase 0 honesty pass** — make README/AGENTS match code; delete/clearly-mark the unbuilt
   autoresearch/knowledge/harness plans as "proposed."
2. **Spike the moat** — install propagation lib; write a CCSDS **CDM parser + Pc-from-covariance**
   prototype against published reference cases; prove **NULL-Pc-on-bad-covariance** end to end.
3. **Replace ≥3 grep evals with behavioral evals** (run the pipeline with an evidence gap → assert
   `FURTHER_INVESTIGATION`; covariance non-PSD → NULL Pc; CCSDS round-trip).
4. **File NASA SBIR Phase I** (rolling BAA is open) on AI-assured autonomous conjunction assessment.
5. **Open 1 insurer/broker pilot conversation** for the Underwriting Risk Evidence Pack.
6. **Register for TraCSS** updates + the GSA Commercial CA Screening solicitation; map the data-quality
   pathfinder as a target.

---

*Caveats / verify before quoting externally:* market-size figures vary widely by source; the full
8-dossier web-research phase was truncated by a session usage limit, so procurement/competitor facts
here come from a focused 5-query search batch (sourced inline) — re-verify TraCSS solicitation dates
and SBIR topic numbers against the live .gov pages before any proposal submission.
