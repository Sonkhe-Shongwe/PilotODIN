# PilotODIN v0.5: Consolidated AI and Reliability Release

## Scope delivered in this update

- **User interface:** independent scrollable left navigation; collapsible sidebar; removed duplicated horizontal navigation; restrained neutral interface overrides; better responsive layouts; reduced-motion accessibility.
- **AI routing:** global preferred provider (Smart Auto, Gemini, Groq, OpenRouter, local); per-workspace preference, with fallback routing; local-safe Markdown subset rendering; genuine provider handshake and status/latency in Settings; auto-handshake at startup *for users who have already consented to cloud use*; longer permitted request timeout.
- **AI tools:** explicit, allowlisted read-only investigations for quality summaries, overview facts, numerical distributions and chart recommendations; no arbitrary Python execution, data modification or private row transmission from tool calls.
- **Data freshness:** live profile of current approved working dataset version in Understand and Overview; refresh on quality changes.
- **Explore:** intelligently recommended charts; avoids identifier fields by default; skew-aware mean/median checks; selectable relevant investigations and existing visual charts preserved.
- **Model Lab:** random, group-aware and chronological splitting; chosen split/group/date column is excluded from predictors; existing fold-local preprocessing and untouched holdout; baseline score and failure-to-beat-baseline warnings.
- **Evaluate:** classification accuracy in percent, macro F1/precision/recall, labelled confusion matrix and class-level support; regression MAE/RMSE/R² with explicit disclaimer that R² is not accuracy; model-comparison bars; bounded actual-versus-predicted scatter for regression; conservative reliability warnings based on baseline, R² and small sample.
- **Predict Studio:** predicted outcome and target label; warning about unreliable fitted model; numeric input warnings for values beyond ranges observed in training; existing fitted preprocessing and class probabilities.
- **Preservation:** no update to stored database, uploads, model artifacts or encrypted API keys; backwards compatible with old experiments (new metric fields are optional).

## Automated verification performed

- **118 backend tests passed** (102 existing plus 16 added). Included credential handshake, rejected invalid models/preferences, failover, time/group splits, classification metric labels, reliability warnings, chart suggestions, live profiles, allowlisted tools and the earlier upload/clean/train/predict tests.
- TypeScript/TSX syntax checked with installed TypeScript CLI; a **limited semantic check** was also run with temporary type declarations for React/Lucide due to missing npm dependencies. Temporary declarations are excluded from this package.
- Backend smoke upgrade: test suite run after overlaying this update onto the reconstructed v0.4 codebase.

## Not verified or out of scope for claims of completion

- **No live cloud API key** was used in automated tests. Provider HTTP behaviour uses stubs; click *Test connection* in your Windows application to verify your keys and quota access.
- **Full `npm run build` was not executable in this environment** because frontend npm packages could not be installed here. Your existing Windows installation already has those dependencies; run the included self-test and send the full error output if build fails.
- No Windows installer / standalone EXE has been packaged. The project still uses the one-click local launcher and installed Python/Node runtimes.
- No arbitrary conversational agent executes data transformations or multi-step modelling autonomously. AI recommendations and read-only investigations are grounded in verified local tools; consequential changes still require user action.
- No guarantee of calibrated probabilities, validated domain meaning, causal interpretation, superior predictive performance, perfect AI output or perfect 100k×50 responsiveness on every 8 GB machine.
- Advanced notebook-specific visualisations, batch prediction, multi-table relational modelling, automatic model tuning, and a rich configurable dashboard remain beyond this tested release. Do not label these completed.

## Correctness principles

- Classification accuracy is a percent of held-out correct labels. F1 is a distinct percentage-like score.
- Regression has no universal accuracy %. R² measures fit against a constant-mean reference, not prediction accuracy; it can be negative.
- A model can rank first and still be worse than a simple baseline. A warning is now issued.
- Chronological/grouped validation requires correctly identified split columns and sufficient independent records. It may reject unsuitable small datasets.
- Cloud providers can change quotas and prices. All automated failover and connection checks use the user's own configured credentials; local-only remains selectable.
