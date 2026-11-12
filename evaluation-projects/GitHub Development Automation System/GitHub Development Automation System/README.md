# devbot - AI Software Maintenance Automation (GPT + GitHub)

Takes a natural-language change request, plans it, branches, edits code, runs tests, auto-repairs failures,
and opens a **draft** pull request. It never merges and never deploys.

Pure Python 3.9+ standard library + the `git` CLI. No pip installs needed.

## Quick start (offline demo, no API key)
```bash
./demo/run_demo.sh            # fictional repo "bookshop-api", scripted GPT replies
python3 -m unittest discover -s tests -t .   # devbot's own tests (9)
```
The demo shows: (1) dry-run leaves the repo untouched, (2) live run creates a branch + commit + draft-PR file,
`main` is never modified. The scripted first edit has a deliberate off-by-one bug so you see test failure -> auto-repair.

## Real use with GPT and GitHub
```bash
export OPENAI_API_KEY=sk-...           # optional: DEVBOT_MODEL=gpt-4o-mini (default)
export GITHUB_TOKEN=ghp_...            # fine-grained token: Contents RW + Pull requests RW on ONE repo

python3 -m devbot analyze --repo ./my-project                      # read-only report
python3 -m devbot run --repo https://github.com/you/repo --request "Add input validation to signup"   # DRY-RUN (default)
python3 -m devbot run --repo https://github.com/you/repo --request "..." --live --allow-repo you/repo  # real branch + draft PR
```
You are asked to approve the plan before any edit (`--yes` skips the prompt).

## Pipeline (maps to the requirements)
| # | Requirement | Module |
|---|---|---|
| 1 | Connect to authorised repo | `pipeline._connect/_authorize`, `github_client.verify_access` (needs `--allow-repo` + token with push access for live mode) |
| 2 | Structure, languages, frameworks | `analyzer.analyze` |
| 3 | Explain key files and dev tools | `analyzer` (docstrings, config detection) + GPT `explain` |
| 4 | Natural-language request | `cli run --request` |
| 5 | Plan + tools required (free/OSS noted) | `planner.make_plan` |
| 6 | Separate branch `devbot/<slug>-<timestamp>` | `git_ops.create_branch` |
| 7 | Modify code after approval | `editor.generate_edits/apply_edits` |
| 8 | Run tests, repair (max `--max-repairs`, default 2) | `test_runner`, `editor.generate_repair` |
| 9 | Summary + draft PR | `llm summary`, `github_client.create_draft_pr(draft=True)` |
| 10 | Dry-run | default mode: everything runs in a scratch copy; original repo verified unchanged |
| 11 | No merge / no deploy | `safety.py` allow-list: no `merge`, `rebase`, `reset`, force-push, push to protected branches; workflow files are not editable |

## Safety rules (safety.py)
- Dry-run is the default; `--live` is explicit. Live mode needs a clean working tree.
- git allow-list only; forced pushes and protected branches (`main`, `master`, ...) refused.
- Model-proposed edits are validated: inside repo, not `.git`, not secrets (`.env`, `*.pem`...), not `.github/workflows/`, max 10 files, 200 KB each.
- PRs are always created with `draft: true`. There is no merge function in the code base.
- If tests still fail after repairs, nothing is pushed (unless `--pr-on-failure`).
- Tokens are passed via a git http header, not stored in `.git/config`, and masked in errors.
- Caution: running tests executes the repository's code, so only point devbot at repos you trust.

## Tools used (all free/open-source except GPT)
git, Python `unittest` (or pytest/npm/go/cargo/mvn auto-detected), GitHub REST API (free). The only paid piece is
the OpenAI API; set `OPENAI_BASE_URL` to use any OpenAI-compatible server (e.g. a local open-source model).

## Layout
```
devbot/  safety.py git_ops.py llm.py analyzer.py planner.py editor.py test_runner.py github_client.py pipeline.py cli.py
demo/    make_demo_repo.py (fictional repo)  demo_script.py (scripted GPT)  run_demo.sh
tests/   test_devbot.py
```
