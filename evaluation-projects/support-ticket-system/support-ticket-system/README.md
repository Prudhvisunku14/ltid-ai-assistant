# AI-Supported Customer Support Ticket System

Users submit tickets; GPT classifies them (technical issue / billing / general inquiry), recommends a
priority and explains why. Staff can correct everything by hand, move tickets through
Open → In Progress → Resolved, and watch a live dashboard. Tickets are stored in SQLite.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # add OPENAI_API_KEY (optional)
uvicorn app.main:app --reload                           # http://localhost:8000
pytest                                                  # 32 automated tests, no network/API key needed
```
Without `OPENAI_API_KEY` the app still works: a free rule-based classifier is used instead.
Docker: `docker build -t tickets . && docker run -p 8000:8000 -v tickets:/data -e OPENAI_API_KEY=sk-... tickets`

## Architecture
```
 Browser (index.html, vanilla JS)
        │  JSON over HTTP
        ▼
 FastAPI  app/main.py ──────────► validation (Pydantic, app/models.py)
    │                │
    │                └─► Classifier interface (app/classifier.py)
    │                        ├─ OpenAIClassifier   → GPT (JSON mode)   ← category, priority, reasoning
    │                        └─ RuleBasedClassifier → keywords          ← free fallback
    ▼
 TicketRepository (app/db.py) ──► SQLite file (data/tickets.db)
```
Key decisions
* **Classifier is an interface.** The API depends on `classify(title, description)`, so GPT can be swapped,
  mocked in tests, or replaced by the rule-based version. If GPT errors, times out, or returns invalid JSON,
  the ticket is still saved using the fallback (reasoning says so) – a ticket is never lost to an LLM outage.
* **GPT is used only where it adds value**: classification + priority + written reasoning. Everything else uses
  free/open-source components.
* **Human always wins.** Manual values are marked `manual`; the original suggestion is kept in
  `ai_category` / `ai_priority`, so the dashboard can report how often people overrode the AI.
* **Disable auto-classification** in two ways: untick "Classify automatically" on the form and pick the
  category yourself (the LLM is not called at all), or set `AUTO_CLASSIFY_ENABLED=false` to turn it off globally.
* **Prompt-injection hardening**: ticket text is wrapped in `<ticket>` tags, the model is told it is untrusted
  data, output is forced to JSON and validated against enums before use. The UI escapes all text (no XSS) and
  SQL uses bound parameters.

## Role of each tool
| Tool | Role | Cost |
|---|---|---|
| OpenAI GPT (`gpt-4o-mini`, configurable) | Category, priority and reasoning | Paid API (cheap, optional) |
| FastAPI + Uvicorn | REST API, serves the dashboard | Free / OSS |
| Pydantic | Input validation, enums, response schemas | Free / OSS |
| SQLite (`sqlite3`, stdlib) | Persistent ticket storage, no server needed | Free / public domain |
| HTML + vanilla JS | Ticket form, dashboard, inline editing (no build step) | Free |
| python-dotenv | Loads `.env` configuration | Free / OSS |
| pytest + httpx (TestClient) | Automated tests | Free / OSS |
| Docker (optional) | Packaging | Free |

## API
| Method & path | Purpose |
|---|---|
| `POST /api/tickets` | Create. Body: `title`, `description`, optional `auto_classify` (default true), `category`, `priority` |
| `GET /api/tickets?status=&category=&priority=` | List / filter |
| `GET /api/tickets/{id}` | One ticket |
| `PATCH /api/tickets/{id}` | Correct `category`, `priority` or change `status` |
| `GET /api/stats` | Dashboard counts by status, category, priority, plus manual corrections |
| `GET /api/config` | Active classifier, whether auto-classification is enabled |
Interactive docs: `/docs`.

## Tests (`pytest`, 32 tests)
* `tests/test_api.py` – submit, validation, AI vs manual mode, global disable, LLM crash resilience,
  corrections, status workflow, filters, dashboard counts, persistence across restarts, UI served.
* `tests/test_classifier.py` – rule engine, GPT happy path and prompt shape, every failure mode falls back,
  reasoning truncation, classifier selection. GPT is mocked, so tests are free and deterministic.
* `tests/test_db.py` – zero-filled stats, update whitelist, SQL-injection safety.

## Configuration (`.env`)
`OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`), `DATABASE_PATH` (default `data/tickets.db`),
`AUTO_CLASSIFY_ENABLED` (default `true`).

## Possible next steps
Authentication / roles, assignee field, pagination, PostgreSQL via the repository class, an
"AI accuracy" metric from `manually_corrected`, re-classify button.
