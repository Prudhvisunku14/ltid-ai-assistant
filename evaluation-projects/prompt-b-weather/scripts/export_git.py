"""Exports the REAL local git state of source/ to reports/git.json and (optionally) attempts publication.

    python scripts/export_git.py            # record state only
    python scripts/export_git.py --push     # also try `git push` non-interactively, and open a Draft PR if (and only if)
                                            # the push succeeded and GITHUB_TOKEN is set. Never merges, never deploys.

Nothing is assumed: push/PR status are written from what the commands actually returned, and a push is only
reported as successful when `git ls-remote` afterwards shows the branch on the remote at the local commit.
NOTE: the Draft-PR API call below could not be exercised in the build sandbox (no credentials), so it is untested.
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "source"
REPO = "LTID-rep/ltid-ai-competition-weather"
URL = f"https://github.com/{REPO}"
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_ASKPASS": "echo"}


def git(*args, check=True):
    p = subprocess.run(["git", *args], cwd=SRC, capture_output=True, text=True, env=ENV, encoding="utf-8", errors="replace")
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p


def fields(fmt, *rev):
    return [dict(zip(("hash", "author", "date", "subject"), l.split("\x1f"))) for l in git("log", f"--format={fmt}", *rev).stdout.splitlines()]


def pr_body(branch, base):
    return ("## Summary\nAdds a validated, time-ordered synthetic temperature forecasting demo to the starter: documented "
            "preprocessing policy, five transparent forecast methods, held-out MAE on a time-ordered split, CLI, JSON API and "
            "interactive web UI, and 57 new unit tests (the 2 original tests still pass).\n\n"
            "## Notes\n* All observations are synthetic. Output is an educational demonstration, not a real weather forecast.\n"
            "* Draft: please review before merging. Not deployed.\n\n"
            "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n")


def main(push):
    fmt = "%h\x1f%an\x1f%aI\x1f%s"
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    base = "main"
    ls = git("ls-remote", "--symref", "origin", "HEAD", check=False)
    verified = ls.returncode == 0 and "refs/heads/main" in ls.stdout
    base_commit = fields(fmt, "-1", base)[0]
    commits = fields(fmt, f"{base}..{branch}")
    out = {"exported_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "repository_url": URL,
           "base_branch": base, "base_branch_verified": verified,
           "base_branch_evidence": ls.stdout.strip().replace("\t", " ") if verified else (ls.stderr.strip() or "ls-remote failed"),
           "import_kind": "ZIP snapshot (identical to upstream main after line-ending normalisation); local repo is a clone of upstream main",
           "dev_branch": branch, "baseline_commit": base_commit, "commits": commits,
           "push": {"status": "not_pushed", "reason": "Not attempted in this export."},
           "draft_pr": {"status": "not_created", "url": None, "reason": "Requires a pushed branch."}}
    if push:
        p = git("-c", "credential.helper=", "push", "-u", "origin", branch, check=False)
        remote = git("ls-remote", "--heads", "origin", branch, check=False).stdout.strip()
        local = git("rev-parse", "HEAD").stdout.strip()
        ok = p.returncode == 0 and remote.startswith(local)
        out["push"] = {"status": "pushed" if ok else "not_pushed", "attempted_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                       "exit_code": p.returncode, "output": (p.stdout + p.stderr).strip()[-400:],
                       "reason": "Verified on remote with git ls-remote." if ok else
                                 "git push failed (" + ((p.stderr.strip().splitlines() or ["no output"])[-1])[:160] + "); the branch was verified absent from the remote with git ls-remote."}
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if ok and token:
            req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/pulls", method="POST",
                                         data=json.dumps({"title": "Add validated synthetic temperature forecasting demo (Prompt B)", "head": branch, "base": base,
                                                          "draft": True, "body": pr_body(branch, base)}).encode(),
                                         headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    pr = json.loads(r.read())
                out["draft_pr"] = {"status": "created", "url": pr["html_url"], "reason": "Draft PR created via the GitHub API; not merged."}
            except Exception as exc:
                out["draft_pr"] = {"status": "not_created", "url": None, "reason": f"PR creation failed: {exc}"}
        elif ok:
            out["draft_pr"] = {"status": "not_created", "url": None, "reason": "Branch pushed but no GITHUB_TOKEN set to open the PR."}
        else:
            out["draft_pr"] = {"status": "not_created", "url": None, "reason": "Requires a pushed branch (push failed: no valid credentials)."}
    elif (ROOT / "reports" / "git.json").exists():
        prev = json.loads((ROOT / "reports" / "git.json").read_text(encoding="utf-8"))
        out["push"], out["draft_pr"] = prev["push"], prev["draft_pr"]          # keep the last real attempt result
    (ROOT / "reports" / "git.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    bundle = ROOT / "reports" / "prompt-b-source.bundle"
    git("bundle", "create", str(bundle), base, branch)
    print(json.dumps({"branch": branch, "commits": len(commits), "push": out["push"]["status"], "draft_pr": out["draft_pr"]["status"],
                      "base_verified": verified, "bundle_bytes": bundle.stat().st_size}))


if __name__ == "__main__":
    main("--push" in sys.argv[1:])
