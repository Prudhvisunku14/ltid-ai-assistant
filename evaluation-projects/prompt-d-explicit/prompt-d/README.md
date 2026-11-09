# DevPilot (Prompt D - Explicability)

A small tool-using engineering agent, standard library only. Every claim it prints is either **measured now** or **cited**;
anything it cannot do it says so (abstains, skips, or marks NOT ATTEMPTED).

```
python -m devpilot tools      # D1 / Prompt D.1  live tool assessment
python -m devpilot website    # D2 / D.2         DOCX spec -> site edits -> checks -> branch + draft PR
python -m devpilot weather    # D3 / D.3         synthetic forecast, MAE, error handling
python -m devpilot rag        # D4 / D.4         expense deadline (cited) + Company Z (abstains)
python -m devpilot change --project PATH --request "..."   # D5 / D.5  needs OPENAI_API_KEY
python -m devpilot change --demo                            # offline demo of the D5 loop (scripted, labelled)
python -m devpilot all        # everything, writes reports to out/
python -m unittest discover -s tests -t .                   # 23 tests (pytest also works)
scripts/run_in_docker.sh      # same tests in a no-network, cap-dropped container
```

## What each stage does (and its honest limits)

**D1 tools.** `data/tool_catalogue.json` holds declared permissions/costs *with source URLs*. `devpilot/tools.py` probes each tool live
(HTTP status, `gh auth status`, `docker info`...) and reports `verified | configured_unverified | unauthorized | unavailable | mock_only`.
A missing key or unreachable network is never reported as working. Costs are catalogue claims; only OpenAI token usage is measured.

**D2 website.** Reads the real DOCX (`REQ-n:` lines) with `zipfile`+XML, plans per requirement, edits the repo copy idempotently,
checks (static HTML, Node unit test of `validateContact`, Chromium test via Playwright when a browser is available - otherwise
reported as SKIPPED, never PASS), commits on a branch, writes `PR_DRAFT.md`, and opens a **draft** PR only if a remote and
`gh` auth exist. There is no merge code. Requirements without a handler are reported `UNSUPPORTED`.
Drive: uses a clearly labelled **mock** `data/drive_mock/website_spec.docx` unless `GDRIVE_ACCESS_TOKEN` is set (live download is not implemented; add it in `tools.py`/`website.py`).

**D3 weather.** `make_synthetic` creates data; everything is labelled SYNTHETIC. Chronological train/val/test, one-step-ahead rolling forecasts
(no look-ahead; tested), model chosen on validation only, test MAE computed once. Seven bad-input cases are demonstrated and rejected.

**D4 RAG.** Only authorized + approved + in-force + non-superseded documents are searchable (`data/policies/*.md` front matter).
Answers are extracted sentences, each citation machine-verified against the file. "Who approved Company Z?" abstains: the authorized
minutes say no approval was recorded; the unauthorized chat rumour is excluded and named as excluded.

**D5 change request.** `devpilot/change.py` contains no request-specific logic: analyse (file tree + AST symbols + baseline tests) -> plan (LLM) ->
implement (LLM, path-confined) -> test -> up to 3 repair rounds with failing output -> rollback if still red -> `evidence/<ts>/report.md|json|diff`.
At freeze time run: `python -m devpilot change --project <their project> --request "<their change>"`.
**It needs a live LLM**; without a key it changes nothing and says NOT ATTEMPTED. `--demo` uses scripted replies only to prove the machinery.

## Not verified in the build environment
No internet, OpenAI key, GitHub or Drive access was available when this was built, so D1 shows those as unavailable/mock and D5 was exercised
only with the scripted LLM. Run `python -m devpilot tools` on your machine after setting `.env` values to see real statuses.
