"""
Live-deploy verification for https://kiranmohan-92.github.io/index-drift.html

Run as:
    BU_NAME=orbital-inspect browser-harness < scripts/verify-drift-live.py

Requires helpers pre-imported by browser-harness (goto, wait_for_load, js,
screenshot, page_info). Exit 0 = all checks passed, 1 = any check failed.
"""

import json
import sys

TARGET_URL = "https://kiranmohan-92.github.io/index-drift.html"

checks = []


def record(name, passed, detail=""):
    checks.append({"name": name, "passed": passed, "detail": str(detail)})


# ── 1. Navigate ────────────────────────────────────────────────────────────────
goto(TARGET_URL)
wait_for_load(timeout=15)

# ── 2. Canvas presence ─────────────────────────────────────────────────────────
canvas_exists = js("!!document.querySelector('#drift-bg')")
record("canvas_present", bool(canvas_exists), "#drift-bg element found" if canvas_exists else "#drift-bg missing")

# ── 3. Canvas non-zero computed dimensions ─────────────────────────────────────
# Use getBoundingClientRect (DPR-safe): checks rendered size, not the raw
# canvas width/height attributes which may lag until the shader resizes them.
rect = js("JSON.stringify(document.querySelector('#drift-bg')?.getBoundingClientRect() ?? {})")
try:
    r = json.loads(rect) if rect else {}
    w = r.get("width", 0)
    h = r.get("height", 0)
    canvas_sized = w > 0 and h > 0
    record("canvas_nonzero_size", canvas_sized, f"BoundingClientRect w={w} h={h}")
except Exception as e:
    record("canvas_nonzero_size", False, f"rect parse error: {e}")

# ── 4. Hero section present ────────────────────────────────────────────────────
hero_exists = js("!!document.querySelector('#hero')")
record("hero_section_present", bool(hero_exists), "#hero section found" if hero_exists else "#hero missing")

# ── 5. Hero name "Kiran Mohan" ─────────────────────────────────────────────────
hero_text = js("document.querySelector('.hero-name')?.innerText?.trim() ?? ''")
name_ok = "Kiran" in (hero_text or "") and "Mohan" in (hero_text or "")
record("hero_name_kiran_mohan", name_ok, f"hero-name text: {repr(hero_text)}")

# ── 6. Chrome gradient class applied to hero name ─────────────────────────────
# The CSS rule sets background-clip:text + a linear-gradient on .hero-name,
# so computed backgroundImage should contain "gradient".
hero_bg = js(
    "window.getComputedStyle(document.querySelector('.hero-name') ?? document.body)"
    ".backgroundImage"
)
chrome_gradient_ok = "gradient" in (hero_bg or "").lower()
record(
    "hero_name_chrome_gradient",
    chrome_gradient_ok,
    f"backgroundImage starts: {str(hero_bg)[:80]}",
)

# ── 7. Drift shader canvas z-index / position (fixed + z=0) ───────────────────
canvas_style = js(
    "JSON.stringify({position: window.getComputedStyle(document.querySelector('#drift-bg') ?? document.body).position,"
    " zIndex: window.getComputedStyle(document.querySelector('#drift-bg') ?? document.body).zIndex})"
)
try:
    cs = json.loads(canvas_style) if canvas_style else {}
    position_ok = cs.get("position") == "fixed"
    record(
        "canvas_fixed_position",
        position_ok,
        f"position={cs.get('position')} zIndex={cs.get('zIndex')}",
    )
except Exception as e:
    record("canvas_fixed_position", False, f"style parse error: {e}")

# ── 8. Screenshot ──────────────────────────────────────────────────────────────
SCREENSHOT_PATH = "/tmp/drift-live.png"
screenshot(SCREENSHOT_PATH, full=True)

# ── Summary ────────────────────────────────────────────────────────────────────
passed = all(c["passed"] for c in checks)

result = {
    "passed": passed,
    "checks": checks,
    "screenshot": SCREENSHOT_PATH,
}

print(json.dumps(result, indent=2))

sys.exit(0 if passed else 1)
