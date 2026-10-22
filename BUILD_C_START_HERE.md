# PilotODIN Build C: Hybrid ODIN Intelligence

This ZIP is **the complete Build B source with an additive local-first AI integration**. It keeps the new Investigation Canvas, the old Studio, dataset versioning, experiments, existing cloud connectors, Tauri foundation and tests. It is not a standalone HTML demo.

## First steps on Windows

1. **Back up your existing PilotODIN folder and data.** Extract this archive into a new folder. Do not overwrite your active installation while testing.
2. Continue installing the Python and frontend dependencies using the existing project instructions in `BUILD_B_START_HERE.md` and `desktop/README.md`.
3. Install Ollama from https://ollama.com/download/windows. It runs independently from PilotODIN.
4. In PowerShell, download one small model with `ollama pull qwen3:1.7b`, then confirm with `ollama list`. Download occurs only after you choose to run the command.
5. Start PilotODIN normally. In **Studio → AI Settings** choose **Hybrid: Ollama, then opted-in cloud**, keep **Allow local Ollama inference** checked, and set **Local model** to `qwen3:1.7b`.
6. Click **Save AI preferences**, then **Test local Ollama**. It checks whether Ollama is responding and the named model is installed. It does not run an inference or download a model.
7. Import `examples/demo_property_prices.csv` in Studio and select **New Canvas**. Start an investigation, execute a verified local computation and use **Ask ODIN** in the right panel to request an interpretation.
8. Cloud is **off by default**. To enable it, add a provider credential in Studio AI Settings, explicitly allow sharing bounded dataset summaries, and enable cloud reasoning. User questions may themselves contain sensitive information, so do not type private data when cloud sharing is enabled.

## Operating modes

- **Hybrid (default)**: Try Ollama on `127.0.0.1:11434`. If unavailable, try configured cloud providers *only after both cloud enablement and aggregate-sharing consent*. Otherwise use verified deterministic local analysis.
- **Local**: Ollama, then deterministic local analytics. No cloud calls even if cloud credentials exist.
- **Cloud first**: Configured and consented cloud providers first, then Ollama, then deterministic local analytics. Without consent it cannot use cloud services.
- In any mode users can choose **Ollama only** or **Verified local analytics (no LLM)** for a workspace.

## What is new in Build C

- `backend/ai_provider.py`: fixed-loopback Ollama integration, model validation, local status probing, routing, failures and conservative memory settings.
- `backend/main.py`: settings contracts and `GET /api/ai/local/status` (local-only, desktop-auth protected).
- `frontend/src/AIWorkspace.tsx`: operating mode, local model, timeout, local probe and clear cloud-consent controls.
- `frontend/src/InvestigationCanvas.tsx`: Ask ODIN alongside the actual persisted evidence. AI text is **not** stored as a verified tool artifact and cannot modify data.
- `frontend/src/investigation-canvas.css`: compact local AI composer styling.
- `tests/test_hybrid_local_ai.py`: isolated tests with simulated Ollama/cloud responses; no actual provider keys required.

## Verified / pending

- **Verified here:** 178 Python tests pass with `PYTHONPATH=. pytest -q`; the changed TSX files parse successfully using TypeScript.
- **Not verified here:** actual model inference on Windows, installed frontend dependencies and full `npm run build`, Windows 11 Tauri packaging, end-to-end browser interactions, 8 GB RAM usage during simultaneous local inference and ML.
- PilotODIN does not install Ollama or pull a model automatically, and does not provide free cloud quotas or bypass provider usage policies.
- See `docs/BUILD_C_HYBRID_INTELLIGENCE.md` for technical and privacy details.
