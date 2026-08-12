# Orbital Inspect — Pilot Statement of Work

**Product:** Orbital Inspect Evidence Pack — Public Risk Screen  
**Pilot term:** 60 days from the later of signature or first delivered pack  
**Fee:** USD **$12,000**, payable on signature (invoice / PO)  
**Included volume:** **15 assets**, two refresh cycles during the term  
**Additional assets:** USD $600 each, written confirmation required  

## 1. Deliverable

For each nominated asset (NORAD catalog number, plus optional imagery, operator notes, and optional Conjunction Data Message), Orbital Inspect will deliver an Evidence Pack as PDF and JSON within 48 hours of a complete request. Each pack states:

- public evidence present and missing against an underwriting-evidence ledger
- claims that are blocked because required private evidence is absent
- a next **human** action (`continue_screen`, `request_telemetry`, `request_cdm`, or `escalate_specialist`)
- collision probability **only** when the buyer supplies a usable CDM; otherwise explicit `Pc = NULL` and a written reason
- a reproducibility stamp (input hash + software SHA)

Delivery is concierge (secure email or shared folder). The web application is a demonstration surface, not a condition of this SOW.

## 2. What this is not

The Evidence Pack is a **public-data risk screen**. It is **not**:

- an offer to insure, a quote, a binder, or a bind / decline decision
- an underwriting determination or actuarial loss probability
- a NASA, Space Force, or other official inspection certificate
- live SpaceX Stargaze or TraCSS conjunction screening

The buyer must **not rely** on any pack as underwriting, as a reason to bind or decline coverage, or as a substitute for operator telemetry, calibrated imagery, or a licensed collision-assessment service.

## 3. Data scope

Default scope is **public sources only** (catalog, conjunction listings, space weather, registry metadata, and buyer-uploaded imagery). If the buyer uploads a CDM or other ephemeris, the buyer remains solely responsible for export-control classification and for authorizing Orbital Inspect to process that file for this pilot. This SOW does not include classified, ITAR-controlled, or CUI holdings unless the parties sign a separate addendum.

## 4. Authority and human review

Every public-data pack is issued with `decision_authority = SCREENING_ONLY`. Recommended actions are requests for evidence or specialist review. They are not coverage recommendations. Final use of any pack is the buyer’s human review.

## 5. Professional-services limitation

This is a fixed-fee professional-services pilot of a screening artifact. It is provided without warranty that any particular submission will be bound, declined, or priced. Liability is limited to the fees paid under this SOW. Neither party is required to proceed to a subscription.

## 6. Conversion (optional)

If the buyer wants a second slate or a login after the pilot, the parties may convert to a monthly subscription (indicative: USD $2,500 / month for 25 assets) or ad-hoc packs (indicative: USD $750 / pack) under a separate order. Those figures are not a commitment in this SOW.

## 7. Signatures

| | Buyer | Orbital Inspect |
|---|---|---|
| Name | | |
| Title | | |
| Date | | |
| Signature | | |
