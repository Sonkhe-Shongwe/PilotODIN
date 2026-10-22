# PilotODIN v0.6 Experience Update

## What changes
- **App shell and navigation:** Independent scrolling for the sidebar and main workspace. Responsive overlay sidebar on narrow windows, calmer visual design, fluid active/hover/pressed states, and reduced-motion support.
- **Fast workspace access:** Press Ctrl+K to search workspaces and navigate by keyboard. The app shows an immediate route response and remembers scroll positions.
- **State continuity:** Explore chart settings, Data Quality inspector selection, and Ask ODIN chat state persist when switching between workspaces (within the same open app session). Switching projects still resets these views safely.
- **Clearer loading feedback:** Buttons and long-running AI analysis show live busy states and real elapsed time, not fabricated percentages or success indicators. Global operations show confirmation toasts; charts use smooth updates.
- **Cloud routing resilience:** A Gemini 502/503/504 response tries one alternate Gemini model before switching to the next configured independent provider. A 429 quota response moves directly to the next provider without repeated calls. Groq's routine model default is updated to `openai/gpt-oss-120b`.
- **Startup provider checks:** When and only when the user already opted into cloud reasoning and aggregate sharing, startup triggers a limited background model connection check for configured providers. Checks are cached for 15 minutes per running backend process. Checks send a fixed `READY` prompt, never dataset rows. No cloud AI key or actual model is packaged.
- **Insight caching:** Cloud responses are cached for up to 10 minutes; failed cloud attempts that yielded local fallback are cached only 45 seconds. Manual Refresh overrides the cache.
- **Safety unchanged:** Data modifications remain governed by validated Quality approval/undo/versioning; no AI-generated code execution; existing model validation and reliability warnings remain in place.

## Tests
- 127 backend pytest tests passed, including 9 new tests covering safe startup verification, cached health checks, overload fallback, 429 handling, and credential isolation.
- All frontend `.tsx` / `.ts` files passed TypeScript parsing, plus a compiler consistency check with local type stubs because this environment does not have the real React/lucide packages installed.
- **Not yet verified in this environment:** A genuine Vite production build, a rendered browser interaction/performance test on Windows, live cloud API connections using user credentials, and a packaged Windows `.exe` installer. Existing batch launcher remains in place.

## Installation
Apply the update to the **inner `PilotODIN` folder** (where `backend`, `frontend`, `.venv` and `data` already exist). Do not replace/delete `.venv`, `frontend/node_modules`, `data`, existing experiments or stored credentials. No new Python/Node dependencies were added.

## Known limitations
- Local intelligence remains the deterministic Python analytics toolset; installing or training a capable local LLM is not part of this UX release. No claim of cloud-model parity on 8 GB RAM.
- Provider connectivity depends on external APIs, changing quotas and network conditions; connected status is verified when a handshake succeeds, not guaranteed for later requests.
- No native self-contained Windows installer yet; `Start_PilotODIN.bat` continues to launch the application.
- Rich offline analysis and general autonomy beyond verified tools remain longer-term work.
