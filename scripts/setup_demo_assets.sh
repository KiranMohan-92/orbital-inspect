#!/usr/bin/env bash
# Populate backend/data/demo_images/ (gitignored runtime dir) from the
# in-repo demo fixtures so the /api/v1/demo/* endpoints work on a fresh clone.
#
# Image provenance (public sources, see frontend/public/demo_images/SOURCES.md):
#   iss_solar_panel.jpg    NASA STS-120 solar array wing tear (public domain)
#   hubble_solar_array.jpg NASA/ESA retrieved Hubble solar array close-up (public domain)
#   sentinel_1a.jpg        ESA Sentinel-1A onboard camera, solar array particle impact (CC BY-SA 3.0 IGO)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/frontend/public/demo_images"
DST="$REPO_ROOT/backend/data/demo_images"

mkdir -p "$DST"
cp "$SRC"/*.jpg "$DST"/
echo "Demo images installed to $DST:"
ls -la "$DST"/*.jpg
