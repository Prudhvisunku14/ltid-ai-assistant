# LTID Assistant

An AI-software-engineering **evidence platform**: a light-theme dashboard (React + TypeScript + Vite + Tailwind, FastAPI backend) that lets an evaluator inspect project work. It includes **Prompt A — Website Development**, **Prompt B — Weather Forecasting Demo**, **Prompt C — LTID AI Competition – RAG**, **Prompt D — DevPilot Explainability**, and five further projects: the **Inventory** system, **Appointment booking**, **Expense management**, **Support tickets** and the **Document change monitor**.

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
| Prompt C — LTID AI Competition – RAG (`evaluation-projects/ltid-ai-competition-rag-final`) | **Real**: the supplied standard-library RAG project (`prompt-c-rag/`, its own local git repo, 1 commit, no remote) plus a **web interface added by this integration** (`web_demo/`: ask, document upload, optional LLM toggle). 51 checks re-run here: 18 project tests, 17 web-interface tests, 16 browser checks (Edge). Retrieval is BM25 keyword search: **no embeddings, no vector database**. LLM rephrasing is optional and was **never run against a live model**. Known gap: it answers an *international* hotel-limit question with the *domestic* limit (see `docs/REQUIREMENTS_CHECK.md`). The earlier Prompt C implementation was replaced and archived locally |
| Prompt D DevPilot (`evaluation-projects/prompt-d-explicit/prompt-d`) | **Real local source**; 23 passing recorded unittest cases. Dashboard describes its five stages and displays recorded tests; it does not trigger tool probes, file edits, or remote actions |
| Inventory (`evaluation-projects/inventory-system/inventory`) | **Real**; its own local git repository (5 commits, no remote, nothing pushed). 24 unit/HTTP tests and a 10-step browser test pass (browser test run on Edge). One uncommitted fix: `/favicon.ico` returned 404 |
| Appointment booking, Expense management, Support tickets, Document change monitor (`evaluation-projects/<name>/`) | **Real uploaded folders**: 25, 64, 32 and 23 passing tests, re-run here and recorded in each `reports/`. No git history or baseline was supplied, so the dashboard shows no code changes for them. Small edits made: configurable `HOST` (Flask apps, docchange) and `tzdata` in two requirements files for Windows |
| Support tickets — GPT classification | **Not exercised**: no OpenAI key here. Only the rule-based fallback ran; GPT is covered by mocked tests |
| Document change monitor — live Google Drive mode | **Not exercised** against the real folder (no credentials). Covered by tests with a fake Drive service |
| Expense management — identity | A demo user picker, **not real authentication** |
| Requirements check | `docs/REQUIREMENTS_CHECK.md` maps every written requirement (Scenarios 01–03 and the project-context rules) to its evidence |
| Gallery projects other than the nine above | **Placeholders**, labelled, excluded from counts |
| `docker compose up` | Config validated, and the stack has been started on the developer's machine (containers observed running: dashboard, API, Prompt A/B previews, inventory and the four new apps). Container-level behaviour was only spot-checked; the apps' functions were verified natively |
| Deployment | **Not deployed.** An InsForge project (`ltid-assistant`) was created and linked, but no backend or frontend has been deployed to it: the backend deploy needs `flyctl`, which could not be installed. InsForge Compute has no persistent volumes, so the SQLite-backed apps would lose data on redeploy |

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
| Inventory management app | http://localhost:8003 |
| Appointment booking app | http://localhost:8004 |
| Expense management app | http://localhost:8005 |
| Support ticket app | http://localhost:8006 |
| Document change monitor | http://localhost:8007 |
| LTID AI Competition – RAG (Prompt C) | http://localhost:8008 |

## Run locally (every project, without Docker)

Start each service in its own terminal, from the repository root. Prerequisites: **Python 3.12** and **Node.js 20+**. Microsoft Edge (or Chromium) is needed only for the browser tests.

### 1. Dashboard and API (needed to see anything)
```bash
python -m venv .venv                                  # Windows: .venv\Scripts\python ; Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pip install -r backend/requirements.txt
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --port 8001      # API on :8001 (docs at /docs)

cd frontend && npm install && npm run dev -- --port 3000                      # dashboard on :3000
```
Then open http://localhost:3000. The API must run on port 8001, or set `VITE_API_URL` before `npm run dev`.

### 2. Project applications
Install each project's requirements once, then start it. Each one keeps its database in a temporary or local file (see the env variables).

| Project | Port | Install (once) | Start |
|---|---|---|---|
| Prompt A — website | 8000 | none (static files) | `cd evaluation-projects/prompt-a-website/source && python -m http.server 8000` |
| Prompt B — weather demo | 8002 | none (standard library) | `cd evaluation-projects/prompt-b-weather/source && python -m weather_app --serve --port 8002` |
| Inventory | 8003 | none (standard library) | `cd evaluation-projects/inventory-system/inventory && INVENTORY_PORT=8003 python -m app` |
| Appointment booking | 8004 | `pip install -r requirements.txt` | `cd evaluation-projects/appointment-booking/appointment-booking && PORT=8004 python run.py` |
| Expense management | 8005 | `pip install -r requirements.txt` | `cd evaluation-projects/expense-system/expense-system && PORT=8005 python run.py` |
| Support tickets | 8006 | `pip install -r requirements.txt` | `cd evaluation-projects/support-ticket-system/support-ticket-system && uvicorn app.main:app --port 8006` |
| Document change monitor | 8007 | none (standard library) | `cd evaluation-projects/docchange/docchange && PORT=8007 python run.py` |
| **Prompt C — LTID AI Competition – RAG** | 8008 | none (standard library) | `cd evaluation-projects/ltid-ai-competition-rag-final/web_demo && PORT=8008 python server.py` |

On Windows, use `set VAR=value&& ...` or set the variable first, for example `set PORT=8004` and then `python run.py`.

Optional settings:
- Appointment: `BOOKING_DB` (database file), `ADMIN_TOKEN` (change the default `admin123`).
- Expense: `EXPENSE_DB` (database file), `SEED_DEMO=0` for an empty database.
- Support: `DATABASE_PATH`, and `OPENAI_API_KEY` for GPT classification. Without a key, the rule-based classifier is used.
- Document change monitor: `HISTORY_DB` (history file). Open the app and click **Scan all documents** to fill its history.

### 3. Prompt C (RAG) command line, and Prompt D
Prompt C also runs from the command line (the web app above uses the same `rag_app` package):
```bash
cd evaluation-projects/ltid-ai-competition-rag-final/prompt-c-rag
python -m rag_app --demo                                   # acceptance questions
python -m rag_app -q "When must an expense claim be submitted?"
python -m unittest discover -s tests -v                    # 18 project tests
cd ../web_demo && python -m unittest discover -s tests -v  # 17 web-interface tests
python ui_check.py                                         # 16 browser checks (needs Playwright + Edge/Chrome)
```
Optional LLM rephrasing (Prompt C): set `OPENAI_API_KEY`, or `RAG_LLM_BASE_URL` for a local OpenAI-compatible server such as Ollama, before starting. Without either, the web interface says so and answers extractively. Never put a key in a file that is committed.

```bash
cd evaluation-projects/prompt-d-explicit/prompt-d
python -m devpilot weather          # other stages: tools, website, rag, change --demo, all
python -m unittest discover -s tests -t . -v
```
Prompt D's `change` stage needs `OPENAI_API_KEY`; `change --demo` works offline.

### 4. Tests for the uploaded projects
```bash
cd evaluation-projects/appointment-booking/appointment-booking && python -m pytest -v
cd evaluation-projects/expense-system/expense-system && python -m pytest -v
cd evaluation-projects/support-ticket-system/support-ticket-system && python -m pytest -v
cd evaluation-projects/inventory-system/inventory && python -m unittest discover -s tests -t . -v
cd evaluation-projects/docchange/docchange && python -m unittest discover -s tests -v
```
(`pytest` needs `pip install pytest` in the active environment; the requirements files list it.)

### 5. Refresh the evidence the dashboard shows
```bash
.venv/Scripts/python evaluation-projects/scripts/collect_external.py        # re-runs the three uploaded projects, rewrites reports/
.venv/Scripts/python evaluation-projects/scripts/verify_projects.py http://localhost:3000   # browser checks; needs Playwright + Edge, all apps running
```

No API keys are needed to browse everything. Copy `.env.example` to `.env` only to set URLs/optional keys.

## Layout
```
frontend/    React app (pages, components, services)        backend/    FastAPI (api, services, agents, integrations, models) + tests
evaluation-projects/prompt-a-website/{inputs,original,source,reports,scripts}
evaluation-projects/prompt-b-weather/{inputs,original,source,reports,scripts}      (source = upstream clone + agent branch; reports/*.json = recorded evidence)
evaluation-projects/ltid-ai-competition-rag-final/{prompt-c-rag,web_demo,reports}   (prompt-c-rag = supplied RAG project with its own git repo; web_demo = web interface + tests added by this integration)
evaluation-projects/prompt-d-explicit/prompt-d/{data,devpilot,tests,workspace}     (docs/test_results.txt = recorded local unittest run)
evaluation-projects/inventory-system/{inventory,original,reports,scripts}
evaluation-projects/appointment-booking/{appointment-booking,reports}   evaluation-projects/expense-system/{expense-system,reports}   evaluation-projects/support-ticket-system/{support-ticket-system,reports}
evaluation-projects/docchange/{docchange,reports}   evaluation-projects/scripts/{collect_external.py,verify_projects.py}
docker/  docker-compose.yml  .env.example  start.sh  start.bat
```
The backend never runs generated code: it only reads files/JSON. The generated site is served by a separate read-only nginx container.

## Tests
```bash
cd backend && pytest                                                    # 7 API tests (incl. path traversal, no-fake-data checks)
cd evaluation-projects/prompt-a-website && python scripts/run_evidence.py   # re-runs the site tests, rewrites reports/test-results.json
cd evaluation-projects/ltid-ai-competition-rag-final/prompt-c-rag && python -m unittest discover -s tests -v
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
