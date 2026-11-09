# LTID Assistant

An AI-software-engineering **evidence platform**: a light-theme dashboard (React + TypeScript + Vite + Tailwind, FastAPI backend) that lets an evaluator inspect project work. It includes **Prompt A — Website Development**, **Prompt B — Weather Forecasting Demo**, **Prompt C — Grounded RAG**, and **Prompt D — DevPilot Explainability**.

## What is real, and what is not
| Item | Status |
|---|---|
| Prompt A modified website (`evaluation-projects/prompt-a-website/source`) | **Real**, built from the supplied ZIP |
| 24 automated checks (17 Python incl. 7 Playwright browser tests, 7 Node) and 5 screenshots | **Real** runs, results in `reports/` |
| Local Git baseline + feature branch + commit | **Real, local only** |
| GitHub push / Draft PR | **NOT done.** No valid credentials; remote unreachable. Dashboard shows `not pushed` / `not created`, no PR URL |
| Requirements DOCX / Google Drive | **Not read directly**; text pasted by the evaluator was used |
| OpenAI / OpenCode / n8n integration | **Structure only** (`backend/app/agents`); not exercised |
| Prompt B weather app (`evaluation-projects/prompt-b-weather/source`) | **Real**: the supplied repo extended in place (stdlib Python, no dependencies). Imported as a **ZIP snapshot** (verified identical to upstream `main` a7022f3) |
| Prompt B tests: 2 starter + 59 unit + 23 browser (Playwright/Edge); 73 dashboard checks | **Real** runs, results in `evaluation-projects/prompt-b-weather/reports/` |
| Prompt B requirements DOCX | **Read directly** from Google Drive through the connector |
| Prompt B Git | Real local clone of upstream `main` + branch `ltid-assistant/prompt-b-weather` + commit. **Push attempted and FAILED (authentication); no Draft PR exists.** Dashboard shows `not pushed` / `not created` |
| Prompt B data | The supplied observations are **synthetic**; every forecast is labelled "not a real weather forecast" |
| Prompt C RAG project (`evaluation-projects/prompt-c-rag/ltid-ai-competition-rag-main`) | **Real local source and knowledge base**; 29 passing recorded unittest cases. No live LLM service or application preview is configured |
| Prompt D DevPilot (`evaluation-projects/prompt-d-explicit/prompt-d`) | **Real local source**; 23 passing recorded unittest cases. Dashboard describes its five stages and displays recorded tests; it does not trigger tool probes, file edits, or remote actions |
| Gallery projects other than Prompts A, B, C and D | **Placeholders**, labelled, excluded from counts |
| `docker compose up` | Config validated (`docker compose config`) but **not run** (no Docker daemon in the build sandbox); services were verified natively |
| Deployment | **Not deployed** |

## Run (one command)
```bash
docker compose up --build      # or ./start.sh  /  start.bat (falls back to native if Docker is off)
```
| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API (+ `/docs`, `/health`) | http://localhost:8001 |
| Prompt A live preview (isolated nginx, read-only static files) | http://localhost:8000 |
| Prompt B weather demo (isolated Python process, source mounted read-only) | http://localhost:8002 |

Native run (a project-local virtualenv avoids global-Python problems):
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r backend/requirements.txt     # Windows; on Linux/macOS use .venv/bin/python
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --port 8001
cd evaluation-projects/prompt-a-website/source && python -m http.server 8000
cd evaluation-projects/prompt-b-weather/source && python -m weather_app --serve --port 8002     # no dependencies
cd frontend && npm i && npm run build && npx vite preview --port 3000
```
> If `docker compose` is already running an older build, run `docker compose up --build` again: containers keep the code they were built with, so Prompt B only appears after a rebuild.

No API keys are needed to browse everything. Copy `.env.example` to `.env` only to set URLs/optional keys.

## Layout
```
frontend/    React app (pages, components, services)        backend/    FastAPI (api, services, agents, integrations, models) + tests
evaluation-projects/prompt-a-website/{inputs,original,source,reports,scripts}
evaluation-projects/prompt-b-weather/{inputs,original,source,reports,scripts}      (source = upstream clone + agent branch; reports/*.json = recorded evidence)
evaluation-projects/prompt-c-rag/ltid-ai-competition-rag-main/{knowledge_base,rag_app,tests,docs}
evaluation-projects/prompt-d-explicit/prompt-d/{data,devpilot,tests,workspace}     (docs/test_results.txt = recorded local unittest run)
docker/  docker-compose.yml  .env.example  start.sh  start.bat
```
The backend never runs generated code: it only reads files/JSON. The generated site is served by a separate read-only nginx container.

## Tests
```bash
cd backend && pytest                                                    # 7 API tests (incl. path traversal, no-fake-data checks)
cd evaluation-projects/prompt-a-website && python scripts/run_evidence.py   # re-runs the site tests, rewrites reports/test-results.json
cd evaluation-projects/prompt-c-rag/ltid-ai-competition-rag-main && python -m unittest discover -s tests -v
cd evaluation-projects/prompt-d-explicit/prompt-d && python -m unittest discover -s tests -t . -v
```
Site tests need `pip install playwright && playwright install chromium`.

### Prompt B (weather)
```bash
cd evaluation-projects/prompt-b-weather/source
python -m unittest discover -s tests -v                      # 59 tests (stdlib only)
python -m weather_app --city Tokyo --days 3 --format text    # also: --evaluate, --demo, --serve
# from the platform root, with the venv + `pip install playwright` (uses the installed Edge/Chrome):
.venv/Scripts/python evaluation-projects/prompt-b-weather/scripts/run_evidence.py      # starter tests, unit tests, browser checks -> reports/*.json
.venv/Scripts/python evaluation-projects/prompt-b-weather/scripts/build_timeline.py
.venv/Scripts/python evaluation-projects/prompt-b-weather/scripts/verify_platform.py --ui http://localhost:3000 --api http://localhost:8001   # needs all services running
```
Method, split, preprocessing policy and limitations are documented in `evaluation-projects/prompt-b-weather/source/README.md` and in the dashboard (Prompt B → Data & Method, Evaluation, Final Report).

## Publishing Prompt B to GitHub (manual, needs a token with push access)
```bash
cd evaluation-projects/prompt-b-weather/source        # a clone of upstream main; `origin` is already LTID-rep/ltid-ai-competition-weather
git push -u origin ltid-assistant/prompt-b-weather
gh pr create --draft --base main --head ltid-assistant/prompt-b-weather
# or: python ../scripts/export_git.py --push   (needs GITHUB_TOKEN to open the Draft PR); then rerun scripts/run_evidence.py + build_timeline.py
```
The base branch `main` was verified with `git ls-remote`. A `git bundle` of the branch is in `reports/prompt-b-source.bundle`. Never merge or deploy automatically.

## Publishing Prompt A to GitHub (manual, needs a token)
```bash
git clone evaluation-projects/prompt-a-website/reports/prompt-a-source.bundle site && cd site
git checkout feature/northstar-homepage-upgrade
git remote add origin https://github.com/LTID-rep/ltid-ai-competition-website.git   # confirm default branch first (assumed: main)
git push -u origin feature/northstar-homepage-upgrade
gh pr create --draft --base main --head feature/northstar-homepage-upgrade
```
Never merge or deploy automatically. Then update `reports/git.json` so the dashboard reflects the real PR.
(The bundle's baseline commit is the imported ZIP snapshot, not the real GitHub history; if the PR is opened from a fresh clone of the real repo, copy `source/` files onto a new branch instead.)

## Deployment
- **Frontend:** `cd frontend && VITE_API_URL=https://api.example.com npm run build`, host `dist/` on any static host (SPA fallback to `index.html`; see `docker/nginx-spa.conf`).
- **Backend:** `docker/backend.Dockerfile` or `uvicorn app.main:app`; set `CORS_ORIGINS` to the frontend origin, `PROMPT_A_PREVIEW_URL` to the deployed preview, and mount/ship `evaluation-projects/`. Health checks: `/health`, `/api/health`. Secrets only via environment variables.
- **Prompt A preview:** any static host; the site has no build step (publish `source/` minus `tests/` and `screenshots/`).
- Frontend and backend deploy independently. A database is not required (data is file-based); add SQLAlchemy/Postgres if run history must persist.
# ltid-ai-assistant
