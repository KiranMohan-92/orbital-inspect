# Orbital Inspect Evidence Pack — Disclaimer

**Read this before attaching a pack to a submission file.**

1. **Screening only.** Public-data packs are issued with screening-only authority. They list what public evidence shows, what is missing, and what a human should request next.

2. **No underwriting. No bind.** Do not treat an Evidence Pack as a quote, binder, loss probability, financial exposure, or a recommendation to bind or decline coverage. Those decisions belong to a licensed underwriter with private evidence.

3. **NULL is not zero.** If collision probability is printed as NULL, covariance was missing, not positive-semidefinite, or no CDM was supplied. NULL is a refused calculation, not a safe miss.

4. **Public catalog columns are not computed Pc.** CelesTrak / SOCRATES listings are read-through context. Computed Pc appears only from a buyer-supplied CCSDS CDM processed by the deterministic Foster/Akella-Alfriend path.

5. **Uncalibrated imagery.** Visual notes without range, scale, and calibration metadata are not physical damage dimensions and are not power-loss measurements.

6. **Public-data-only default.** Unless a separate addendum says otherwise, Orbital Inspect processes public sources and files the buyer chose to upload. The buyer is responsible for export-control status of any CDM or ephemeris they send.

7. **Reproduction.** A pack is authentic only if its JSON `reproducibility.input_hash` and `reproducibility.software_sha` match a regeneration from the same inputs and software revision.

Pilot commercial terms (USD $12,000 / 60 days / 15 assets) are in `PILOT-SOW.md`. This disclaimer forbids relying on the pack as underwriting.
