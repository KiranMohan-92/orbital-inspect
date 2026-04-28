# Karpathy LLM Wiki Strategy for Orbital Inspect

Date: April 18, 2026

## Executive Summary

Orbital Inspect already has a strong raw-evidence and audit substrate:

- canonical assets, aliases, and reference profiles in `backend/db/models.py`
- reusable evidence records and analysis-evidence lineage in `backend/db/models.py` and `backend/db/repository.py`
- persisted analysis events, decision workflow, governance, reports, fleet trends, and offline eval hooks across `backend/main.py` and `backend/services/`

What it does not yet have is the layer Andrej Karpathy is now implicitly optimizing for: a compiled, persistent, queryable knowledge layer that sits between raw evidence and each new reasoning run.

My judgment:

- Karpathy's April 4, 2026 `llm-wiki` idea file is directly relevant to Orbital Inspect.
- Rohit Ghumare's April 18, 2026 `LLM Wiki v2` gist is useful, but only after translation into Orbital Inspect's stricter provenance, governance, and multi-tenant requirements.
- The right move is not "add an Obsidian clone."
- The right move is to turn Orbital Inspect from an evidence-rich analysis system into an evidence-rich analysis system with compiled institutional memory.

That means:

1. keep raw evidence as source of truth
2. compile claims, precedents, and workflows into a durable knowledge layer
3. use that layer for context engineering, human review, and fleet intelligence
4. never allow unreviewed compiled knowledge to bypass fail-closed underwriting logic

## Source Grounding

The latest directly inspectable long-form source from Andrej Karpathy I found is his `llm-wiki` gist, created on April 4, 2026:

- https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Two earlier Karpathy signals still matter because they explain how to use the wiki pattern correctly:

- June 19, 2025: `Andrej Karpathy: Software Is Changing (Again)` at YC AI Startup School
  - https://www.youtube.com/watch?v=LCEmiRjPEtQ
- June 25, 2025: Karpathy's `context engineering` post, which defines the real systems problem as packing the context window with the right information for the next step
  - surfaced in Techmeme: https://www.techmeme.com/250628/h1150

The user-linked extension gist is:

- April 18, 2026: Rohit Ghumare, `LLM Wiki v2`
  - https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2

Important dating point: as of April 18, 2026, I did not find a newer directly inspectable Karpathy long-form source than the April 4, 2026 gist. The repo plan below is therefore grounded primarily in that gist, plus his June 2025 context-engineering and Software 3.0 framing.

Everything below that maps those sources into Orbital Inspect is my inference, not a claim that Karpathy explicitly prescribed this exact architecture for this repo.

## What Karpathy Is Actually Saying

### 1. Stop re-deriving; start compiling

Karpathy's core complaint with standard RAG is not that retrieval is useless. It is that the system keeps rediscovering the same knowledge from raw documents every time. His proposed fix is a persistent wiki maintained by the LLM, where synthesis accumulates.

For Orbital Inspect, this is the key leap:

- today: every new analysis reassembles evidence, prior analyses, reference profiles, and stage outputs mostly per run
- target: the system should also maintain compiled knowledge about assets, subsystems, anomalies, failure signatures, operator patterns, and precedent cases

### 2. The schema is the product

Karpathy's architecture has three layers:

- raw sources
- wiki
- schema

Orbital Inspect already has strong raw sources. It partially has a schema through `AGENTS.md`, service boundaries, prompt files, and governance policy. It does not yet have the middle compiled-knowledge layer in a first-class form.

This matters because Orbital Inspect is not a toy coding-agent workspace. It is an insurance and operational-intelligence system. The schema has to encode:

- what counts as a claim
- what counts as a precedent
- what can influence runtime decisions
- what requires human validation
- how confidence changes with recency and contradiction
- what is tenant-scoped, global, classified, or non-exportable

### 3. Context engineering beats prompt engineering

Karpathy's June 25, 2025 observation is the most operationally important one for this repo: the problem is not clever prompts, it is assembling the right context for the next step.

Orbital Inspect is already a context-heavy system:

- the 5-agent pipeline
- evidence bundles
- reference profiles
- historical analyses
- fleet trends
- governance and human review state

The next level is to make this context compiled and selective rather than merely available.

### 4. Partial autonomy beats blind autonomy

From Karpathy's Software 3.0 framing, the winning application shape is not "turn the human off." It is "push autonomy up where it compounds, keep the human where risk concentrates."

Orbital Inspect already follows this principle well:

- fail-closed outputs
- `FURTHER_INVESTIGATION` escalation
- human review requirements
- governance holds

The wiki strategy should strengthen that pattern, not weaken it.

### 5. The human should curate; the system should maintain

Karpathy's core product insight is that humans abandon knowledge bases because maintenance is annoying. The LLM should do the bookkeeping.

For Orbital Inspect, the bookkeeping burden is not just notes. It is:

- cross-case precedent maintenance
- contradiction tracking across evidence sources
- subsystem-specific anomaly pattern extraction
- prompt and policy drift tracking
- keeping asset baseline knowledge current as new public and internal evidence arrives

## What Rohit's LLM Wiki v2 Adds

Rohit's gist is useful because it extends Karpathy's intentionally abstract pattern into production concerns. The strongest additions are:

### 1. Memory lifecycle

This is the most important extension.

The gist adds:

- confidence scoring
- supersession
- forgetting and retention curves
- consolidation tiers from working memory to procedural memory

This maps extremely well to Orbital Inspect because your data already has strong provenance and time semantics. The missing piece is not storage; it is lifecycle.

### 2. Typed graph structure

The shift from flat pages to entities and typed relationships is exactly right for orbital intelligence.

Relevant entity classes for this repo would include:

- asset
- subsystem
- orbit regime
- anomaly
- evidence source
- failure mechanism
- environmental stressor
- insurance claim pattern
- operator
- precedent case
- mitigation action

### 3. Hybrid retrieval

BM25 plus vectors plus graph traversal is directionally right, but not all at once.

For Orbital Inspect, the ordering should be:

1. lexical plus structured filters
2. graph traversal over typed entities and relations
3. optional embeddings where semantic recall is genuinely needed

This repo is audit-heavy and domain-bounded. Over-indexing on embeddings too early would create opaque behavior without enough gain.

### 4. Automation hooks

The gist's event-driven mindset is highly compatible with this codebase:

- on new evidence ingest
- on completed analysis
- on decision review completion
- on scheduled fleet refresh
- on contradiction detection
- on benchmark failure

Orbital Inspect already has durable points to hook:

- `evidence_ingest_service.py`
- `post_analysis_service.py`
- `fleet_ingestion_service.py`
- `retention_service.py`
- `dataset_registry_service.py`

### 5. Crystallization

Rohit's "crystallization" idea is excellent for this repo.

Every finished analysis should not only remain a finished analysis. It should optionally produce:

- normalized case summary
- extracted claims
- detected anomaly signatures
- precedent links
- lessons for prompt/policy tuning

This is how the system compounds instead of just storing reports.

## Where Orbital Inspect Already Has a Head Start

The repo is closer to a Karpathy-compatible system than it may look.

### Raw source layer already exists

Orbital Inspect already stores:

- reusable evidence records with provider, URL, confidence, capture time, and tags
- reference profiles
- ingest run history
- persisted analysis events
- reports
- baseline references and telemetry summaries on analyses

That is stronger than most LLM wiki implementations, which start from loose markdown files.

### Provenance discipline already exists

`backend/models/provenance.py` already encodes a worldview Karpathy's pattern needs:

- source types
- field provenance
- confidence calibration
- derivation chains

This is a major advantage. It means the compiled memory layer can be rigorous rather than vibes-only.

### Governance discipline already exists

`backend/services/decision_policy_service.py` and `backend/services/governance_service.py` already enforce:

- fail-closed logic
- blocked decisions
- explicit human review
- policy-versioned rationale

That is the right skeleton for safe knowledge compilation.

### Temporal history already exists

The repo already thinks in time:

- captured vs ingested timestamps
- analysis timelines
- trend analysis
- retention policies
- SLO freshness concepts

This is exactly what a knowledge lifecycle needs.

## The Critical Insight for Orbital Inspect

Karpathy's wiki pattern should not be implemented here as a notes feature.

It should be implemented as a compiled orbital intelligence layer with four jobs:

1. compress raw evidence into reusable claims and precedents
2. improve context packs for the 5-agent pipeline
3. improve human review speed and consistency
4. create fleet-level memory across time, subsystems, and operators

The right conceptual model is:

- evidence records are the facts and observations
- analyses are the reasoning episodes
- compiled knowledge is the durable memory
- decision workflow is the authority boundary

## What To Build

### Karpathy-Style Target Shape

The right first move is not "build the memory platform."

The right first move is to prove one compounding loop:

1. a completed analysis produces an inspectable compiled artifact
2. that artifact is reused in the next similar analysis
3. one agent performs better because it received the right prior context
4. the human can inspect exactly what memory was used and why

If that loop works, then broader memory infrastructure is justified.
If that loop does not work, then the platform should not be built out further.

### The Magic Demo

The plan should optimize for a single obvious demo:

- analysis A finishes
- Orbital Inspect crystallizes analysis A into a case page plus a small set of candidate claims
- analysis B arrives for a similar asset, subsystem, or anomaly family
- Orbital Inspect builds a compact context pack from that prior case
- one downstream agent uses it
- the analyst can see both the compiled case page and the exact context pack that influenced the new run

That is the Karpathy-native product test for this repo.

### Minimal Vertical Slice

Start with one agent, one memory surface, one retrieval path.

Recommended first target:

- agent: `insurance_risk`
- reason: it benefits most directly from precedent, contradiction handling, and reusable synthesized case memory

The smallest useful loop is:

- raw evidence and analysis outputs stay as source of truth
- one human-inspectable case page is generated per completed analysis
- a compact precedent context pack is built only for `insurance_risk`
- the result is measured against baseline behavior

### Target Architecture After the Thin Slice Proves Value

Add a middle layer between raw evidence and runtime reasoning, but in stages.

### Layer 1: Raw Evidence and Episodes

Keep current source of truth unchanged:

- `evidence_records`
- `analysis_evidence_links`
- `asset_reference_profiles`
- `ingest_runs`
- `analyses`
- `analysis_events`
- `reports`

### Layer 2: Inspectable Compiled Memory

This is the first new layer and should be visibly browseable by humans.

Start with:

- `knowledge_documents`
  - human-readable case pages, asset dossiers, precedent pages, anomaly summaries
- `knowledge_runs`
  - crystallize, refresh, lint, and context-pack generation runs
- `context_packs`
  - per-agent, per-task snapshots of retrieved memory

Only add canonical structured claims when the thin slice proves useful:

- `knowledge_claims`
  - atomic claims with provenance and confidence

Only add graph-heavy coordination later if needed:

- `knowledge_edges`
- `knowledge_reviews`

### Layer 3: Schema and Runtime Policy

Add a schema document that tells agents how compiled knowledge is created and when it is allowed into runtime context.

This should define:

- what qualifies as a case page
- what qualifies as a claim
- which claims are runtime-eligible
- which agent may consume which memory class
- tenant and classification scoping
- human review and supersession rules
- retention and decay policies

## Proposed Data Model

### Minimal Start

The first implementation should resist over-modeling.

Minimum viable primitives:

### `knowledge_documents`

Fields should cover:

- `id`
- `org_id`
- `asset_id`
- `subsystem_id`
- `document_type`
  - `case_page`, `asset_dossier`, `precedent_page`, `anomaly_summary`
- `title`
- `body_markdown`
- `summary_json`
- `derived_from_analysis_id`
- `classification`
- `status`
  - `generated`, `reviewed`, `approved`, `superseded`
- `created_at`
- `updated_at`

### `knowledge_runs`

Fields should cover:

- `id`
- `org_id`
- `run_type`
  - `crystallize`, `refresh`, `lint`, `build_context_pack`
- `status`
- `source_analysis_id`
- `output_document_id`
- `metrics_json`
- `created_at`
- `completed_at`

### `context_packs`

Fields should cover:

- `id`
- `org_id`
- `analysis_id`
- `agent_name`
- `pack_type`
- `sources_json`
- `content_json`
- `token_estimate`
- `created_at`

### Expanded Model Once the Loop Works

Only after the vertical slice proves value should the repo introduce richer canonical structures.

### `knowledge_claims`

Expanded fields:

- `id`
- `org_id`
- `asset_id`
- `subsystem_id`
- `claim_type`
- `claim_text`
- `normalized_payload_json`
- `confidence_score`
- `confidence_basis_json`
- `claim_status`
  - `proposed`, `reviewed`, `approved`, `rejected`, `superseded`
- `supersedes_claim_id`
- `derived_from_analysis_id`
- `last_confirmed_at`
- `last_accessed_at`
- `decay_profile`
- `classification`
- `runtime_eligible`
- `created_at`
- `updated_at`

### `knowledge_edges`

Typed relations such as:

- `supports`
- `contradicts`
- `supersedes`
- `caused`
- `similar_to`
- `same_failure_family`
- `affects_subsystem`
- `precedent_for`
- `mitigated_by`
- `derived_from`

## How This Helps Orbital Inspect Specifically

### 1. Better per-analysis context packs

Today the system can fetch relevant evidence. With compiled knowledge it can also inject:

- prior anomaly families on the same subsystem
- similar cases from the same orbit regime
- known contradictions for this asset baseline
- operator-specific maintenance and trend patterns
- historically effective mitigation actions

This raises quality without requiring the agents to rediscover patterns from scratch.

### 2. Faster human review

Human review should not open a case from zero. It should open with:

- current risk summary
- top supporting evidence
- top contradicting evidence
- nearest historical precedents
- what changed since last review
- why the decision policy landed where it did

That is a direct application of Karpathy's "compiled knowledge" idea to underwriting operations.

### 3. Fleet memory instead of only fleet metrics

The current trend and portfolio surfaces tell you what is happening.
The compiled layer can tell you what kind of thing keeps happening.

That means:

- recurring failure families
- subsystem clusters with similar degradation signatures
- operators with repeated evidence gaps
- orbits and environmental conditions associated with escalations

### 4. Better prompt and policy iteration

Compiled memory should not only be about satellites. It should also capture:

- prompt failures
- parsing failures
- recurring evidence gaps
- false confidence patterns
- benchmark misses

That becomes a self-improving loop for the product.

## What Not To Do

### 1. Do not treat markdown as the source of truth

Karpathy's gist is local-first and markdown-centric because it optimizes for personal knowledge work.

Orbital Inspect is a governed production system.

Use markdown pages as inspection artifacts and operator-facing documents, but keep canonical claims and relations in the database.

### 2. Do not let compiled knowledge bypass provenance

Every compiled claim must point back to:

- evidence records
- analysis outputs
- review actions
- source timestamps

If a claim cannot be traced, it cannot be runtime-eligible.

### 3. Do not merge tenant and global memory casually

This repo already has organization boundaries. The compiled layer must have scoping:

- global public knowledge
- tenant-shared private knowledge
- case-private working memory
- operator-only notes

### 4. Do not use embeddings as the first answer to every problem

Orbital Inspect has strong typed structure. Start with:

- Postgres full-text or BM25-like search
- filters on asset, subsystem, source type, time, orbit regime, classification
- graph traversal

Add vectors only where semantic recall proves necessary.

### 5. Do not allow automatic contradiction resolution to change decisions silently

Contradictions should create:

- reviewable proposals
- supersession suggestions
- context-pack warnings

They should not rewrite authoritative case memory without traceable review.

## Implementation Plan

### Phase 0: Pick the Thin Slice and Define the Demo

Time: 1 to 2 days

Deliverables:

- choose one agent, one anomaly family or precedent type, and one retrieval question
- define the magic demo in concrete terms
- define what counts as success before any infrastructure build-out

Recommended starting question:

- "Can prior insurance-risk precedents improve the next `insurance_risk` synthesis for similar cases?"

Repo impact:

- update this architecture note
- add a tiny schema/policy note for the thin slice only

Success criterion:

- the team can explain the demo in one paragraph and identify exactly which next-step decision should improve

### Phase 1: Crystallize Completed Analyses into Inspectable Case Pages

Time: 3 to 5 days

Deliverables:

- on completed analysis, generate one human-inspectable case page
- include compact structured summary data sufficient to power later retrieval
- persist the page and the run metadata

Repo impact:

- `backend/db/models.py`
- `backend/db/repository.py`
- new `backend/services/knowledge_crystallizer.py`
- hook from `backend/services/post_analysis_service.py`

Success criterion:

- every selected completed analysis yields a case page an analyst can browse and verify

### Phase 2: Build a Context Pack for One Agent

Time: 3 to 5 days

Deliverables:

- build a compact precedent context pack only for `insurance_risk`
- source it from the new case pages plus existing evidence lineage
- persist the exact pack for audit and replay

Repo impact:

- new `backend/services/context_pack_service.py`
- prompt-assembly changes near the `insurance_risk` agent call path
- persistence of context pack summaries for audit

Success criterion:

- one new analysis can consume prior compiled case memory in a targeted, inspectable way

### Phase 3: Prove Uplift Before Expanding Scope

Time: 2 to 4 days

Deliverables:

- offline eval set for precedent retrieval and insurance-risk synthesis
- compare baseline vs context-pack-assisted behavior
- measure token cost, latency, and citation quality

Repo impact:

- new tests beside `backend/tests/test_offline_eval.py`
- likely `test_context_pack_service.py`
- likely `test_knowledge_crystallizer.py`

Success criterion:

- the thin slice shows measurable improvement or the plan is revised before further platform work

### Phase 4: Add Canonical Claims and Human Review

Time: 4 to 6 days

Deliverables:

- introduce `knowledge_claims` only after the thin slice works
- add human review states, runtime eligibility, and supersession
- keep case pages as first-class inspectable artifacts

Repo impact:

- `backend/db/models.py`
- `backend/db/repository.py`
- new `backend/services/knowledge_service.py`

Success criterion:

- compiled memory becomes structured without becoming opaque

### Phase 5: Add Search and Traversal Only as Needed

Time: 5 to 8 days

Deliverables:

- lexical search over case pages and claims
- graph traversal over typed relations if retrieval quality requires it
- optional vector retrieval behind a feature flag only if evals justify it

Recommendation:

- start with Postgres and explicit graph walks
- do not introduce external search infra first

Success criterion:

- "find similar cases" becomes reliably useful without creating a disproportionate platform burden

### Phase 6: Expand to More Agents and Fleet Memory

Time: 5 to 8 days

Deliverables:

- extend context packs to additional agents if they show real benefit
- add asset dossiers, precedent pages, and fleet-memory summaries
- expand contradiction detection, decay, and retention policy

Special rule:

- architecture and mission baseline claims decay slowly
- transient anomaly interpretations decay faster
- runtime eligibility expires unless reconfirmed

Success criterion:

- the system compounds across agents and fleets without losing inspectability or governance

### Phase 7: Full Safety Gates

Time: 3 to 5 days

Deliverables:

- tests proving runtime decisions never rely on unreviewed or tenant-incompatible claims
- contradiction handling and decay policy tests
- benchmarks for latency and token usage at expanded scope

Success criterion:

- the larger memory layer remains fail-closed and auditable

## Recommended First 30 Days

If I were operating as Karpathy-style product architect on this repo, I would do this in order:

1. pick one agent and one precedent question
2. generate inspectable case pages from completed analyses
3. feed those pages back into one next-step context pack
4. prove uplift with evals before expanding scope
5. only then add canonical claims, review states, and broader retrieval

This order matters because the product needs one visible compounding loop before it needs a large memory platform.

## Success Metrics

Track these from day one:

- percentage of targeted completed analyses that crystallize successfully
- percent of new analyses in the thin slice that receive a context pack
- average citations per case page
- contradiction rate per 100 claims
- stale-claim rate
- percent of runtime context tokens sourced from compiled memory vs raw evidence
- delta in `insurance_risk` eval quality with and without context packs
- decision-review time reduction
- precedent retrieval precision on eval cases
- token reduction per analysis
- analyst override rate before and after compiled memory

## The Deepest Fit With Orbital Inspect

The deepest overlap between Karpathy's latest thinking and Orbital Inspect is this:

- Karpathy: the bottleneck is not reading, it is maintaining and reusing synthesized knowledge
- Orbital Inspect: the bottleneck is not collecting more orbital data, it is turning evidence into reusable operational intelligence

That is why this gist matters here.

Orbital Inspect already knows how to gather evidence and produce a result.
The next moat is making each result permanently improve the next one.

## Bottom Line

Karpathy's `llm-wiki` should help Orbital Inspect in one specific way:

It should push the product from "provable per-case reasoning" to "provable per-case reasoning plus compounding institutional memory."

Rohit's `LLM Wiki v2` is helpful because it identifies the missing production mechanics:

- lifecycle
- supersession
- graph structure
- automation
- quality control
- collaboration

But the implementation for this repo must be stricter than either gist:

- database-first for canonical claims
- provenance-first for every compiled assertion
- governance-first for runtime eligibility
- tenant-aware and classification-aware throughout

But the first implementation should also be thinner than this memo originally proposed:

- one agent before five
- one compounding demo before a platform
- inspectable case pages before heavy abstraction
- proven uplift before graph and retrieval expansion

If built that way, this is not a side feature.
It is the architecture that can make Orbital Inspect meaningfully smarter every week without becoming less trustworthy.

## References

- Andrej Karpathy, `llm-wiki`, created April 4, 2026:
  - https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Andrej Karpathy, personal site, accessed April 18, 2026:
  - https://karpathy.ai/
- Andrej Karpathy, `Andrej Karpathy: Software Is Changing (Again)`, June 19, 2025:
  - https://www.youtube.com/watch?v=LCEmiRjPEtQ
- Techmeme aggregation of Karpathy's June 25, 2025 `context engineering` post:
  - https://www.techmeme.com/250628/h1150
- Rohit Ghumare, `LLM Wiki v2`, last active April 18, 2026:
  - https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
