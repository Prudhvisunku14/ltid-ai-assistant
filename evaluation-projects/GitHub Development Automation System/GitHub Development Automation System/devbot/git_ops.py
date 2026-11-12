"""Thin, safety-checked wrapper around the git CLI (free/open-source)."""
from __future__ import annotations
import base64
import re
import subprocess
from pathlib import Path
from typing import Optional

from .safety import check_git_args, validate_branch_name


class GitError(RuntimeError):
    pass


def parse_github_slug(url: str) -> Optional[str]:
    m = re.search(r"github\.com[:/]+([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", url or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _auth_flags(token: Optional[str]) -> list[str]:
    if not token:
        return []
    b = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {b}"]


def clone(url: str, dest: Path, token: Optional[str] = None) -> None:
    args = ["clone", url, str(dest)]
    check_git_args(args)
    r = subprocess.run(["git", *_auth_flags(token), *args], capture_output=True, text=True)
    if r.returncode:
        raise GitError(r.stderr.strip().replace(token or "\0", "***"))


class Git:
    def __init__(self, root: Path):
        self.root = Path(root)

    def run(self, *args: str, check: bool = True, token: Optional[str] = None) -> str:
        args = list(args)
        check_git_args(args)
        ident = ["-c", "user.name=devbot", "-c", "user.email=devbot@users.noreply.github.com"]
        r = subprocess.run(["git", "-C", str(self.root), *ident, *_auth_flags(token), *args],
                           capture_output=True, text=True)
        if check and r.returncode:
            err = (r.stderr or r.stdout).strip()
            raise GitError(f"git {' '.join(args)} failed: {err}".replace(token or "\0", "***"))
        return r.stdout.strip()

    def is_repo(self) -> bool:
        return self.run("rev-parse", "--is-inside-work-tree", check=False) == "true"

    def current_branch(self) -> str:
        return self.run("rev-parse", "--abbrev-ref", "HEAD")

    def is_clean(self) -> bool:
        return self.run("status", "--porcelain") == ""

    def remote_url(self) -> Optional[str]:
        out = self.run("remote", "get-url", "origin", check=False)
        return out or None

    def default_branch(self) -> str:
        ref = self.run("symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
        if ref:
            return ref.split("/", 1)[-1]
        return self.current_branch()

    def create_branch(self, name: str) -> None:
        validate_branch_name(name)
        self.run("checkout", "-b", name)

    def commit_all(self, message: str) -> str:
        self.run("add", "-A")
        self.run("commit", "-m", message)
        return self.run("rev-parse", "HEAD")

    def diff_stat(self, base: str) -> str:
        return self.run("diff", "--stat", f"{base}...HEAD")

    def diff(self, base: str) -> str:
        return self.run("diff", f"{base}...HEAD")

    def push_branch(self, branch: str, token: Optional[str]) -> None:
        validate_branch_name(branch)
        self.run("push", "--set-upstream", "origin", branch, token=token)
