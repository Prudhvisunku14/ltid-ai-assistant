"""GitHub access: verify authorisation and open DRAFT pull requests. There is deliberately no merge function."""
from __future__ import annotations
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str):
        self.token = token

    def _req(self, method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            API + path, method=method, data=json.dumps(body).encode() if body else None,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "devbot"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise GitHubError(f"GitHub API {e.code} on {method} {path}: {e.read().decode()[:300]}") from None

    def verify_access(self, slug: str) -> dict:
        info = self._req("GET", f"/repos/{slug}")
        if not info.get("permissions", {}).get("push"):
            raise GitHubError(f"Token has no push permission on {slug}")
        return info

    def create_draft_pr(self, slug: str, head: str, base: str, title: str, body: str) -> str:
        data = self._req("POST", f"/repos/{slug}/pulls",
                         {"title": title, "head": head, "base": base, "body": body, "draft": True})
        return data["html_url"]


def write_local_draft(out_dir: Path, branch: str, base: str, title: str, body: str) -> Path:
    """Fallback when the repo has no GitHub remote: save the draft PR as markdown."""
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]+", "_", branch)
    p = out_dir / f"DRAFT_PR_{safe}.md"
    p.write_text(f"# [DRAFT] {title}\n\n`{branch}` -> `{base}`\n\n{body}\n", encoding="utf-8")
    return p
