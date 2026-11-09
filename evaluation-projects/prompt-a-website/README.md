# Prompt A — Website Development (evaluation project)

| Folder | What it is | Data kind |
|---|---|---|
| `inputs/` | Evaluator's master prompt and the requirements text (transcribed from chat; the DOCX was not read directly) | imported |
| `original/` | Untouched snapshot of the supplied ZIP (`ltid-ai-competition-website-main`) — used for diffs | imported |
| `source/` | The **modified** website. Has its own local Git repo (baseline commit = original, then feature branch). In the delivered archive the nested `.git` is replaced by `reports/prompt-a-source.bundle` | real |
| `reports/` | `test-results.json`, `timeline.json`, `analysis.json`, `git.json`, screenshots — produced by real runs | real |
| `scripts/` | `run_evidence.py` (re-runs tests, rewrites test-results.json), `export_git.py` | — |

Imported snapshot ≠ GitHub repository: original GitHub history was not available. To restore the local history:
`git clone reports/prompt-a-source.bundle restored && cd restored && git checkout feature/northstar-homepage-upgrade`.

Run the site alone: `cd source && python -m http.server 8000`.
