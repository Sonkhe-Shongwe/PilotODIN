# PilotODIN v0.4 Multi-AI Macro Update

## Highlights

- Hybrid intelligence across Overview, Understand, Data Quality, Explore, Prepare, Model Lab, Evaluate, Predict Studio, and Ask ODIN.
- Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`) for routine requests; Gemini 3 Flash (`gemini-3-flash-preview`) for deeper analysis. Google may retire or change model availability; routing automatically falls back if the configured model fails.
- Groq (`llama-3.3-70b-versatile`) and OpenRouter (`openrouter/free`) as ordered, optional fallback providers.
- No cloud keys are needed to use the app. A local, deterministic dataset interpretation remains available offline.
- AI Settings page saves credentials for the backend, never in frontend code or browser local storage. On Windows, API keys are encrypted at rest using the user's Windows DPAPI. On other operating systems, UI-entered keys are session-only; environment variables can be used instead.
- Cloud inference is **disabled by default**. You must explicitly consent to sharing **limited column metadata and aggregates**, then enable cloud reasoning. Prompt content excludes raw dataset rows, data samples, category examples, customer records, original files and input feature values.
- AI can't modify data or train models by itself. Cleaning and model training stay under the existing approval and validation workflow.
- Optional auto-insights setting. Off by default to protect free request quotas.
- Explore's initial X/Y suggestions avoid identifier-like fields and prefer business measures. Skewed numeric columns may default to median summaries.

## Upgrade your existing folder

1. Stop PilotODIN (close or interrupt backend/frontend terminals).
2. **Back up** your existing `PilotODIN/data` folder before applying the patch.
3. Open the `PilotODIN` folder **inside** your extracted `PilotODIN_v0.2B_Increment1_Full_Project` folder (the folder containing `backend`, `frontend`, `.venv`, `Start_PilotODIN.bat`).
4. Extract the update ZIP and **copy its contents**, e.g., `backend`, `frontend`, `tests`, `docs`, and README, directly into that inner `PilotODIN` folder. Choose *Replace files in destination* when Windows asks. **Do not delete `data`, `.venv` or `frontend/node_modules`.**
5. Start PilotODIN using the existing `Start_PilotODIN.bat` launcher. No new Python or frontend dependencies were introduced.
6. Open **AI Settings** on the left, paste the *new* Gemini key in the Gemini field and click **Save**. Never paste API keys into chat, commit them into git, or store them in frontend source files.
7. Check **I permit sending bounded dataset summaries...**, then enable cloud reasoning and click **Save AI preferences**.
8. Open **Ask ODIN** and ask a question about the demo dataset. A successful response will identify its cloud provider and model. If cloud providers are unavailable, the response will clearly identify the local fallback.
9. (Optional) Add Groq/OpenRouter keys later. Their absence does not break the application.

## Tests

- Python backend: `py -m pytest -q` (if pytest is installed in your development environment). 102 tests passed in the authoring environment.
- Frontend: open a terminal in `frontend`, then `npm.cmd run build` with npm dependencies installed. This MUST be run locally; the author's isolated environment had no access to npm dependencies for a true Vite production build.
- Manual smoke: AI Settings → save Gemini key → enable cloud → Ask ODIN → Data Quality → Explore → Prepare/Model Lab → Evaluate → Predict Studio → verify AI interpretation and existing ML still work.
- Test offline fallback by turning cloud reasoning off in AI Settings.
- Test provider failover by using two legitimate API keys and exhausting or disabling the primary service; provider limits depend on your accounts. Do not intentionally expose credentials in bug screenshots.

## Privacy and limitations

- Cloud prompts include column names, row/column counts, numeric statistics, issue categories, affected-row counts, and optional model metrics; this metadata can still be sensitive. Cloud providers have separate retention and data-use policies, especially on free tiers.
- Cloud input includes user-typed questions; don't enter private records or personal information in questions you send to the cloud.
- No LLM model is hosted on your 8 GB laptop. Local fallback is an analytical rules engine, not a neural LLM.
- Gemini, Groq and OpenRouter rate limits and model names can change without notice; the service may fall back locally.
- An unconfigured provider is skipped; an invalid key / quota / timeout is reported as a sanitized status, without exposing secrets.
- This release does not contain a standalone Windows `Setup.exe`. It uses the existing launcher and your installed Python and Node tools.
- Live external provider calls and a complete Vite production build **were not performed in the authoring environment**. HTTP message formats, failovers and provider failure modes were tested using mocked responses.
- AI suggestions are advisory and can be wrong. Source changes still require existing approval; only local engines compute statistics and carry out transformations.
