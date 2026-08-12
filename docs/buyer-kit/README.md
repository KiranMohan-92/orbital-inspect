# Buyer kit — Evidence Pack + pilot terms

Take this folder to a broker or underwriter.

| Artifact | Path |
|---|---|
| Pilot SOW ($12,000 / 60 days / 15 assets) | [`../legal/PILOT-SOW.md`](../legal/PILOT-SOW.md) |
| Disclaimer (no bind / no underwrite) | [`../legal/DISCLAIMER.md`](../legal/DISCLAIMER.md) |
| SENTINEL-1A public-data pack | [`packs/sentinel-1a.json`](packs/sentinel-1a.json) + PDF |
| ISS public conjunction pack (buyer-supplied CDM → computed Pc) | [`packs/iss-conjunction.json`](packs/iss-conjunction.json) + PDF |
| LANDSAT-8 uneventful LEO pack | [`packs/landsat-8.json`](packs/landsat-8.json) + PDF |

Regenerate with the shipped generator:

```bash
cd backend
python -m scripts.generate_evidence_pack --from-demo-cache data/demo_cache/sentinel_1a.json \
  --name SENTINEL-1A --norad 39634 --out-dir ../docs/buyer-kit/packs --stem sentinel-1a
```
