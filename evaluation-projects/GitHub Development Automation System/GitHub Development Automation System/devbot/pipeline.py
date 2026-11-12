"""Orchestrates the whole workflow. Default is DRY-RUN: all work happens in a throw-away copy."""
from __future__ import annotations
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from . import analyzer, editor, planner, prompts
from .git_ops import Git, GitError, clone, parse_github_slug
from .github_client import GitHubClient, write_local_draft
from .llm import LLM
from .safety import SafetyError, validate_branch_name
from .test_runner import run_tests


@dataclass
class Options:
    repo: str                       # local path or https://github.com/owner/name
    request: str
    live: bool = False              # False => dry-run (default)
    auto_approve: bool = False      # --yes
    base: Optional[str] = None
    max_repairs: int = 2
    out_dir: Path = Path("devbot_output")
    allow_repos: list[str] = field(default_factory=list)
    token: Optional[str] = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN"))
    pr_on_failure: bool = False


@dataclass
class RunResult:
    status: str
    branch: str = ""
    files_changed: list[str] = field(default_factory=list)
    tests_ok: bool = False
    repairs_used: int = 0
    pr_location: str = ""
    report_path: str = ""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "change"


def _step(log: Callable, n: int, title: str) -> None:
    log(f"\n=== Step {n}: {title} " + "=" * max(3, 60 - len(title)))


def run(opts: Options, llm: LLM, log: Callable[[str], None] = print,
        approve: Optional[Callable[[str], bool]] = None) -> RunResult:
    mode = "LIVE" if opts.live else "DRY-RUN (no repository changes will be made)"
    log(f"devbot | mode: {mode} | llm: {llm.name}")
    opts.out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="devbot-"))
    try:
        # 1 -- connect ---------------------------------------------------------------------------
        _step(log, 1, "Connect to repository")
        src = _connect(opts, tmp, log)
        git0 = Git(src)
        if not git0.is_repo():
            raise SafetyError(f"{src} is not a git repository")
        slug = parse_github_slug(git0.remote_url() or "")
        _authorize(opts, slug, log)
        base = opts.base or git0.default_branch()
        head_before = git0.run("rev-parse", "HEAD")

        if opts.live:
            if not git0.is_clean():
                raise SafetyError("working tree has uncommitted changes; commit/stash them first")
            work = src
        else:
            work = tmp / "scratch"
            shutil.copytree(src, work, symlinks=True)
            log(f"dry-run: working in a scratch copy, original repo is untouched ({src})")
        git = Git(work)

        # 2/3 -- analyse -------------------------------------------------------------------------
        _step(log, 2, "Analyse structure, languages, frameworks, tools")
        report = analyzer.analyze(work)
        sources = analyzer.read_source_context(work, report.files)
        report.overview = planner.explain_repo(llm, report, sources)
        log(f"Languages : {report.languages}")
        log(f"Frameworks: {report.frameworks or 'none detected'}")
        log(f"Pkg mgrs  : {report.package_managers or 'none'}")
        log("Dev tools : " + (", ".join(f"{t['tool']} ({t['purpose']})" for t in report.dev_tools) or "none"))
        log(f"Test cmd  : {' '.join(report.test_command) or 'none detected'}")
        log(f"Overview  : {report.overview}")
        log("Key files :")
        for kf in report.key_files:
            log(f"  - {kf['path']}: {kf['purpose']}")

        # 4 -- plan + approval -------------------------------------------------------------------
        _step(log, 3, "Plan the change")
        log(f"Request: {opts.request}")
        plan = planner.make_plan(llm, opts.request, report, sources)
        plan_text = plan.render()
        log(plan_text)
        if not _approved(opts, approve, plan_text):
            log("Plan not approved. Nothing was changed.")
            return RunResult("aborted-not-approved")

        # 5 -- branch ----------------------------------------------------------------------------
        _step(log, 4, "Create separate branch")
        branch = validate_branch_name(f"devbot/{_slug(opts.request)}-{datetime.now():%Y%m%d%H%M%S}")
        if not opts.live:
            log(f"[dry-run] would create branch {branch} in {src}; creating it in the scratch copy only")
        git.create_branch(branch)
        log(f"on branch {branch} (base: {base})")

        # baseline tests
        _step(log, 5, "Baseline tests (before any edit)")
        baseline = run_tests(work, report.test_command)
        log(f"baseline: {'PASS' if baseline.ok else 'FAIL'} ({baseline.command or 'n/a'})")

        # 7 -- edit ------------------------------------------------------------------------------
        _step(log, 6, "Modify source code")
        ctx = {p: sources.get(p, "(new file)") for p in plan.files_to_change}
        ctx.update({p: t for p, t in sources.items() if p not in ctx and p.startswith(("tests/", "test"))})
        edits = editor.generate_edits(llm, work, opts.request, plan_text, ctx)
        touched = editor.apply_edits(work, edits)
        log("modified: " + ", ".join(touched))

        # 8 -- test + repair ---------------------------------------------------------------------
        _step(log, 7, "Run tests and repair")
        result = run_tests(work, report.test_command)
        repairs = 0
        while not result.ok and repairs < opts.max_repairs:
            repairs += 1
            log(f"tests FAILED -> repair attempt {repairs}/{opts.max_repairs}\n{_tail(result.output)}")
            diagnosis, fix = editor.generate_repair(llm, work, opts.request, result.output, touched)
            log(f"diagnosis: {diagnosis}")
            touched = sorted(set(touched) | set(editor.apply_edits(work, fix)))
            result = run_tests(work, report.test_command)
        log(f"tests: {'PASS' if result.ok else 'FAIL'} after {repairs} repair attempt(s)")
        if not result.ok:
            log(_tail(result.output))

        # 9 -- summary + commit ------------------------------------------------------------------
        _step(log, 8, "Summarise changes")
        git.run("add", "-A")
        pre_diff = git.run("diff", "--cached")
        summ = llm.complete_json("summary", prompts.SUMMARY, f"REQUEST: {opts.request}\nDIFF:\n{pre_diff[:20000]}")
        git.commit_all(summ.get("commit_message", summ["title"]))
        stat = git.diff_stat(base)
        log(stat)
        body = _pr_body(summ["body_markdown"], stat, result, repairs, opts.live)

        # 10 -- draft PR -------------------------------------------------------------------------
        _step(log, 9, "Draft pull request")
        location = ""
        pr_ok = result.ok or opts.pr_on_failure
        if not pr_ok:
            log("Tests still failing: not pushing and not opening a PR. Branch left for human review.")
        elif not opts.live:
            location = str(write_local_draft(opts.out_dir, branch, base, summ["title"], body))
            log(f"[dry-run] would push {branch} and open a DRAFT PR titled: {summ['title']}")
            log(f"[dry-run] PR preview written to {location}")
        elif slug and opts.token:
            git.push_branch(branch, opts.token)
            location = GitHubClient(opts.token).create_draft_pr(slug, branch, base, summ["title"], body)
            log(f"draft PR opened (NOT merged): {location}")
        else:
            location = str(write_local_draft(opts.out_dir, branch, base, summ["title"], body))
            log(f"no GitHub remote/token: draft PR saved locally at {location}")
        log("devbot never merges pull requests and never deploys. A human must review and merge.")

        if not opts.live:
            assert Git(src).run("rev-parse", "HEAD") == head_before and Git(src).is_clean(), "original repo changed!"
            log("verified: original repository unchanged by dry-run")

        res = RunResult("ok" if result.ok else "tests-failing", branch, touched, result.ok, repairs, location)
        rp = opts.out_dir / f"report-{datetime.now():%Y%m%d-%H%M%S}.json"
        rp.write_text(json.dumps({**res.__dict__, "mode": "live" if opts.live else "dry-run", "request": opts.request,
                                  "plan": plan.__dict__, "analysis": report.to_dict(), "diff": git.diff(base)},
                                 indent=2, default=str), encoding="utf-8")
        res.report_path = str(rp)
        log(f"report: {rp}")
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _connect(opts: Options, tmp: Path, log) -> Path:
    if re.match(r"^(https://|git@)github\.com", opts.repo):
        dest = tmp / "clone"
        log(f"cloning {opts.repo}")
        clone(opts.repo, dest, opts.token)
        return dest
    p = Path(opts.repo).expanduser().resolve()
    if not p.is_dir():
        raise SafetyError(f"repository path not found: {p}")
    log(f"local repository: {p}")
    return p


def _authorize(opts: Options, slug: Optional[str], log) -> None:
    if opts.allow_repos and slug and slug not in opts.allow_repos:
        raise SafetyError(f"{slug} is not in --allow-repo {opts.allow_repos}")
    if opts.live and slug:
        if not opts.token:
            raise SafetyError("live mode on a GitHub repo needs GITHUB_TOKEN")
        if slug not in opts.allow_repos:
            raise SafetyError(f"live mode requires explicit authorisation: add --allow-repo {slug}")
        GitHubClient(opts.token).verify_access(slug)
        log(f"authorised: token has push access to {slug}")
    elif slug:
        log(f"GitHub repo detected: {slug} (dry-run: no write access needed)")


def _approved(opts: Options, approve, plan_text: str) -> bool:
    if opts.auto_approve:
        return True
    if approve:
        return approve(plan_text)
    if sys.stdin.isatty():
        return input("\nApprove this plan? [y/N] ").strip().lower() in ("y", "yes")
    return False


def _tail(text: str, n: int = 15) -> str:
    return "\n".join("    | " + l for l in text.splitlines()[-n:])


def _pr_body(body: str, stat: str, tr, repairs: int, live: bool) -> str:
    return (f"{body}\n\n## Diff stat\n```\n{stat}\n```\n\n## Automated checks\n"
            f"- Command: `{tr.command or 'n/a'}`\n- Result: **{'PASS' if tr.ok else 'FAIL'}**\n"
            f"- Auto-repair attempts: {repairs}\n\n---\n_Draft PR generated by devbot "
            f"({'live' if live else 'dry-run preview'}). Human review required; devbot does not merge or deploy._")
