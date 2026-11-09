# Scenario 01 — Northstar Studio website

A static, intentionally incomplete homepage for a fictional creative technology studio.

**Run:** Open `index.html` in a browser, or run `python -m http.server 8000` in this folder and browse to http://localhost:8000.

**Starter smoke tests:** `python -m unittest discover -s tests -v`.

**Your development agent must:** Read the corresponding Drive specification, explain the use of HTML/CSS/JS and alternatives, implement the specified enhancements, run tests, explain outcomes, and prepare a PR. The starter is *not* the solution. See `TASK_PUBLIC.md`.

## Release 1.0 implementation notes
- **Stack:** plain HTML5 + CSS + vanilla JavaScript (no build step, no external services) — runs from `file://` or any static server.
- **Navigation:** `#nav-toggle` button (`aria-expanded`/`aria-controls`), keyboard operable, closes with Esc, hidden without JS fallback (links stay visible).
- **Portfolio:** `data/projects-data.js` (JS array) rendered into `#project-grid`; artwork in `assets/` is original SVG.
- **Contact:** client-side validation with per-field errors and a polite `role="status"` message. **Local demo only — nothing is sent.**
- **Tests:** `python -m unittest discover -s tests -v` (static + Playwright browser; `pip install playwright && playwright install chromium`) and `node --test tests/validation.test.js`.
