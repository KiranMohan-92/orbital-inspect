# Browser-Harness Live-Deploy Verification Lane

## What this is

`verify-drift-live.py` is a **live-Chrome smoke test** that hits the real deployed URL
(`https://kiranmohan-92.github.io/index-drift.html`) through your actual Windows
Chrome instance via CDP. It runs **after** a GitHub Pages deploy, not during local dev.

## Why it complements Playwright, not replaces it

| Concern | Playwright (e2e/) | browser-harness (scripts/) |
|---|---|---|
| Backend API correctness | Yes — full stack against local server | No |
| DOM logic, auth flows, portfolio | Yes — deterministic, fast, CI-friendly | No |
| **Live DPR / GPU canvas rendering** | No — JSDOM/headless, canvas is a stub | **Yes** |
| **Real Chrome compositor stack** | No | **Yes** |
| **GitHub Pages CDN delivery** | No — hits localhost | **Yes** |
| **Post-deploy regression** | No — pre-deploy only | **Yes** |

The harness cannot stub responses or inject tokens — that is Playwright's job.
The harness can see the actual rendered canvas dimensions, CSS computed values,
and real network-delivered assets — things Playwright's synthetic browser misses.

## Checks performed

1. `canvas_present` — `#drift-bg` element exists in DOM
2. `canvas_nonzero_size` — `getBoundingClientRect()` returns width > 0 and height > 0 (DPR-safe; avoids the raw `canvas.width` / `canvas.height` attributes which can read as the 300×150 default before the shader resizes them)
3. `hero_section_present` — `#hero` section rendered
4. `hero_name_kiran_mohan` — `.hero-name` inner text contains "Kiran" and "Mohan"
5. `hero_name_chrome_gradient` — computed `backgroundImage` on `.hero-name` contains "gradient" (confirms the chrome/gold CSS is applied)
6. `canvas_fixed_position` — `#drift-bg` has `position: fixed` (confirms shader layer is in the viewport stack, not collapsed to 0px)

Screenshot is always saved to `/tmp/drift-live.png` (full page).

## How to run

### Prerequisites

Chrome must be running on Windows with remote-debugging enabled:

```powershell
# Run once in PowerShell (or add to a shortcut):
chrome.exe --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 --user-data-dir=C:\chrome-profiles\orbital-inspect
```

WSL firewall note — if CDP is unreachable from WSL, run once in an admin PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Chrome CDP" -Direction Inbound -Protocol TCP -LocalPort 9222 -Action Allow
```

### Run the smoke test

```bash
# From the orbital-inspect repo root:
BU_NAME=orbital-inspect browser-harness < scripts/verify-drift-live.py
```

Expected output (all checks pass):

```json
{
  "passed": true,
  "checks": [
    {"name": "canvas_present",            "passed": true, "detail": "#drift-bg element found"},
    {"name": "canvas_nonzero_size",       "passed": true, "detail": "BoundingClientRect w=1920 h=1080"},
    {"name": "hero_section_present",      "passed": true, "detail": "#hero section found"},
    {"name": "hero_name_kiran_mohan",     "passed": true, "detail": "hero-name text: 'Kiran\\nMohan'"},
    {"name": "hero_name_chrome_gradient", "passed": true, "detail": "backgroundImage starts: linear-gradient(…)"},
    {"name": "canvas_fixed_position",     "passed": true, "detail": "position=fixed zIndex=0"}
  ],
  "screenshot": "/tmp/drift-live.png"
}
```

Exit code is `0` on pass, `1` on any failure.

## Wiring into GitHub Actions (post-deploy)

Add this job **after** the Pages deploy job in your workflow:

```yaml
verify-live:
  name: Live smoke test (browser-harness)
  runs-on: self-hosted          # must be a runner with Chrome + browser-harness installed
  needs: deploy
  steps:
    - uses: actions/checkout@v4

    - name: Start Chrome with CDP
      run: |
        google-chrome-stable \
          --headless=new \
          --remote-debugging-port=9222 \
          --remote-debugging-address=0.0.0.0 \
          --no-sandbox \
          --disable-gpu &
        sleep 2

    - name: Install browser-harness
      run: uv tool install -e /path/to/browser-harness-kiran

    - name: Run live smoke test
      run: BU_NAME=orbital-inspect browser-harness < scripts/verify-drift-live.py

    - name: Upload screenshot
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: drift-live-screenshot
        path: /tmp/drift-live.png
```

> Note: on a self-hosted Windows runner, replace the Chrome launch command with the
> PowerShell equivalent and adjust the `uv tool install` path accordingly.

## Known caveats

- **WSL ↔ Windows bridge**: Chrome runs on Windows; the browser-harness daemon
  runs in WSL. The daemon auto-discovers the Windows host IP via `/etc/resolv.conf`
  nameserver. If Chrome is not started with `--remote-debugging-address=0.0.0.0`
  the daemon will fail to connect.
- **GitHub Pages cold start**: after a deploy, Pages CDN propagation can take
  30–90 seconds. If you run the test immediately after the deploy job completes,
  add a `wait` or poll loop before invoking the harness.
- **Canvas size on first load**: the Drift WebGL shader resizes the canvas in a
  `requestAnimationFrame` callback. The check uses `getBoundingClientRect()` (CSS
  computed size) rather than the raw `canvas.width` attribute to avoid a race
  with the shader's resize logic.
