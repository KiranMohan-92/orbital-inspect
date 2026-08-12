#!/usr/bin/env python3
"""Concierge Evidence Pack generator — the shipped buyer-kit entry point.

Examples:
  python -m scripts.generate_evidence_pack \\
    --from-demo-cache data/demo_cache/sentinel_1a.json \\
    --name "SENTINEL-1A" --norad 39634 \\
    --out-dir ../docs/buyer-kit/packs --stem sentinel-1a
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.evidence_pack_service import (  # noqa: E402
    analysis_from_demo_cache,
    assert_pack_is_customer_safe,
    build_evidence_pack,
    write_pack_artifacts,
)


def _load_analysis(args: argparse.Namespace) -> dict:
    if args.from_demo_cache:
        return analysis_from_demo_cache(args.from_demo_cache)
    if args.from_analysis_json:
        return json.loads(Path(args.from_analysis_json).read_text(encoding="utf-8"))
    raise SystemExit("Provide --from-demo-cache or --from-analysis-json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an Orbital Inspect Evidence Pack")
    parser.add_argument("--from-demo-cache", type=Path)
    parser.add_argument("--from-analysis-json", type=Path)
    parser.add_argument("--cdm", type=Path, help="Optional buyer-supplied CCSDS CDM (KVN)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--norad", default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--stem", required=True)
    parser.add_argument("--generated-at", default=None, help="Freeze timestamp for reproducible packs")
    args = parser.parse_args(argv)

    analysis = _load_analysis(args)
    cdm_text = args.cdm.read_text(encoding="utf-8") if args.cdm else None
    pack = build_evidence_pack(
        analysis=analysis,
        cdm_text=cdm_text,
        asset_name=args.name,
        norad_id=args.norad,
        generated_at=args.generated_at,
    )
    assert_pack_is_customer_safe(pack)
    paths = write_pack_artifacts(pack, args.out_dir, args.stem)
    print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))
    print(json.dumps(pack, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
