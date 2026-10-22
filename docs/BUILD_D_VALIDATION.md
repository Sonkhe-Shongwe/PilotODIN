# Build D: Verified status and remaining release gates

**Date:** 22 October 2026  
**Baseline:** PilotODIN Build C, including its Python backend and Hybrid Ollama/cloud AI controls.

## Verified in this environment

- Build D Canvas TSX and modified App routing TSX passed TypeScript transpilation and syntax diagnostics with installed TypeScript.
- Legacy Python tests plus Build D's new end-to-end investigation contract tests passed: **179 tests** in the final run.
- Generated the Build D static visual-review HTML using the project's actual CSS and calculated medians from the bundled synthetic property sample. Chromium screenshots were captured at 1440×900 and 390×844 using system Chromium; no horizontal document overflow in the static review.
- ZIP archive integrity checked after packaging.

## Not verified and must not be assumed

- Frontend `npm run build` (npm package registry could not be resolved in the authoring environment).
- Running React application screenshot and Playwright interaction tests (no frontend dependencies installed here).
- Windows installer, Tauri IPC/sidecar lifecycle, restart recovery under Windows, and 8 GB memory-performance benchmarks.
- Real Ollama inference from *inside PilotODIN* on the user's machine. The user's earlier screenshots confirmed model readiness; the runtime call must still be checked in the app.

## First Windows acceptance story

Upload `examples/demo_property_prices.csv` → create investigation → obtain a saved snapshot → compute a `Province` / `PropertyPrice` median comparison → inspect evidence → inspect Bedrooms missingness → download a report → restart → confirm persistence → test ODIN interpretation without cloud consent.

**Important:** The screenshot review represents layout only. It includes no evidence artifact identifiers from a live runtime session.
