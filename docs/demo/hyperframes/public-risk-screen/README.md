# Orbital Inspect - Public Risk Screen HyperFrames Demo

Premium 32-second motion demo for PR #1 and repo-facing product storytelling.

## Preview

```bash
cd docs/demo/hyperframes/public-risk-screen
npx.cmd hyperframes preview --port 3017
```

Open:

```text
http://localhost:3017/#project/public-risk-screen
```

## Validate And Render

```bash
cd docs/demo/hyperframes/public-risk-screen
npx.cmd hyperframes lint
npx.cmd hyperframes inspect --samples 15
npx.cmd hyperframes render --fps 60 --quality high --output ..\..\assets\video\orbital-inspect-public-risk-screen-v1.mp4
```

The composition intentionally positions Orbital Inspect as a public-source screening and evidence-gap triage product. It avoids final underwriting or certification claims.
