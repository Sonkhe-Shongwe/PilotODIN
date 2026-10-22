# Build C integration: local-first Hybrid ODIN

Status: implemented in source; real Windows runtime validation outstanding. Baseline: Build B Investigation Canvas.

## Contract

A calculation is performed by an approved local Python analytics tool. The LLM, when available, provides a narrative interpretation of bounded computed facts. LLM text never executes arbitrary Python or shell code, edits datasets, creates a verified evidence artifact, or silently uploads raw rows.

Default settings: `intelligence_mode = hybrid`, `local_model_enabled = true`, `local_model = qwen3:1.7b`, `local_timeout_seconds = 60`, `cloud_enabled = false`, `share_aggregates = false`.

The router path is:

1. **Hybrid**: local Ollama completion first.
2. If local unavailable and explicit saved cloud consent is present, try available cloud providers in the configured order, observing existing rate-limit cooldowns.
3. If nothing succeeds, respond with deterministic local analytics; identify the source in the returned metadata.
4. `local` mode bypasses all cloud providers; `cloud` mode reverses the first two priorities but preserves cloud consent checks.
5. An explicit `selected_provider=ollama` never automatically escalates to cloud.

Local status endpoint: `GET /api/ai/local/status`. This uses `GET /api/tags` on the fixed `http://127.0.0.1:11434` address and checks for a configured model. This is **not** an inference benchmark. User-provided URLs and model-controlled Python/shell execution are not supported. The request bypasses proxies, limits output size and uses a timeout. Inference calls `POST /api/chat` with streaming disabled and an output/context limit, and unloads the model after a response (`keep_alive = 0`) to reduce ongoing memory pressure on 8 GB hardware.

Cloud consent persists in existing settings and credential storage. Keys continue to use Windows DPAPI in production. A hosted provider may receive limited column descriptions, computed aggregates and **the user's typed question**. Prompts can contain personally identifying or sensitive information. No cloud route is used without both `cloud_enabled` and `share_aggregates` true. Local Ollama runs without a key or quota-based token billing, but compute and RAM are constrained.

## New canvas boundaries

The **Ask ODIN** form is separate from the four allowlisted, evidence-persisting tool operations. It calls the existing authenticated `/api/projects/{id}/ai/insight` API, validates returned dataset version before showing the answer, and labels local LLM, cloud LLM and deterministic guidance differently. A mode switch / project switch clears pending AI interpretation. Version-bound evidence remains independent of any AI explanation.

## Acceptance checklist on Windows 11

1. With no Ollama installed and cloud disabled, the request returns deterministic local analytics and the canvas remains usable.
2. With `ollama pull qwen3:1.7b`, status detects the local model, and a question uses `provider=ollama` with no cloud traffic.
3. With an Ollama failure and cloud disabled, no cloud requests are generated.
4. With cloud enabled and explicit sharing consent, a local model failure can trigger the configured cloud provider; a quota or provider failure returns a transparent local fallback.
5. Local-only mode forbids cloud requests, irrespective of stored credentials.
6. When changing projects or dataset versions, clear older AI interpretation or label stale evidence, and never present model prose as a verified tool run.
7. Benchmark memory usage and response latency on an 8 GB Windows machine, including while an analytics or ML job is running.
8. Run `npm install && npm run build`, desktop packaging, and browser interaction tests. These have **not** been proven by the source-only test run.

## Testing

`PYTHONPATH=. pytest -q` reported **178 passing Python tests**. The TypeScript parser reported no syntax errors for the changed `.tsx` modules. Full TypeScript type-checking and Vite compilation were blocked here because npm dependencies are not installed. Ollama response quality and latency were not benchmarked, since no model runtime was installed in the test environment.

This is an integration milestone, not a claim of completed 1.0 Windows release readiness.
