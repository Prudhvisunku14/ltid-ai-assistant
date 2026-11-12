"""Central safety rules. Everything that touches git or the filesystem goes through here."""
from __future__ import annotations
import re
from pathlib import Path

PROTECTED_BRANCHES = {"main", "master", "develop", "dev", "release", "production", "prod", "trunk"}

# git subcommands devbot may run. NOTE: "merge", "rebase", "reset", "cherry-pick", "tag" are absent on purpose.
ALLOWED_GIT = {
    "status", "rev-parse", "checkout", "switch", "branch", "add", "commit", "diff", "log",
    "ls-files", "init", "config", "remote", "push", "clone", "show-ref", "symbolic-ref",
}
FORBIDDEN_GIT_FLAGS = {
    "--force", "-f", "--force-with-lease", "--hard", "--delete", "-d", "-D", "--mirror", "--prune",
}
FORBIDDEN_PATH_PARTS = {".git"}
FORBIDDEN_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519", ".npmrc", ".pypirc", "credentials.json"}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
FORBIDDEN_PREFIXES = (".github/workflows/",)  # CI/CD changes (which can deploy) need a human
MAX_FILES_PER_CHANGE = 10
MAX_FILE_BYTES = 200_000


class SafetyError(Exception):
    """Raised when an action violates a safety rule. Never caught-and-ignored."""


def check_git_args(args: list[str]) -> None:
    if not args:
        raise SafetyError("empty git command")
    sub = next((a for a in args if not a.startswith("-")), None)
    if sub not in ALLOWED_GIT:
        raise SafetyError(f"git subcommand not allowed: {sub!r}")
    for a in args:
        if a in FORBIDDEN_GIT_FLAGS:
            raise SafetyError(f"git flag not allowed: {a}")
        if sub == "push" and a.startswith("+"):
            raise SafetyError("forced refspec not allowed")
    if sub == "push":
        targets = [a for a in args[1:] if not a.startswith("-")]
        for t in targets:
            name = t.split(":")[-1].replace("refs/heads/", "")
            if name in PROTECTED_BRANCHES:
                raise SafetyError(f"refusing to push to protected branch {name!r}")


def validate_branch_name(name: str) -> str:
    if name in PROTECTED_BRANCHES:
        raise SafetyError(f"refusing to use protected branch name {name!r}")
    if not re.fullmatch(r"[A-Za-z0-9._/-]{3,100}", name) or ".." in name:
        raise SafetyError(f"invalid branch name {name!r}")
    return name


def validate_edit_path(root: Path, rel: str) -> Path:
    """Return an absolute path for a model-proposed edit, or raise SafetyError."""
    if not rel or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel):
        raise SafetyError(f"absolute paths are not allowed: {rel!r}")
    p = (root / rel).resolve()
    root = root.resolve()
    if root not in p.parents:
        raise SafetyError(f"path escapes repository: {rel!r}")
    relp = p.relative_to(root).as_posix()
    if set(relp.split("/")) & FORBIDDEN_PATH_PARTS:
        raise SafetyError(f"editing .git is not allowed: {rel!r}")
    if p.name in FORBIDDEN_NAMES or p.name.endswith(FORBIDDEN_SUFFIXES):
        raise SafetyError(f"secret/credential file is off limits: {rel!r}")
    if relp.startswith(FORBIDDEN_PREFIXES):
        raise SafetyError(f"CI/CD workflow files need human edits: {rel!r}")
    return p


def validate_edit_set(root: Path, edits: list[dict]) -> None:
    if not edits:
        raise SafetyError("model returned no edits")
    if len(edits) > MAX_FILES_PER_CHANGE:
        raise SafetyError(f"too many files changed ({len(edits)} > {MAX_FILES_PER_CHANGE})")
    for e in edits:
        validate_edit_path(root, e.get("path", ""))
        content = e.get("content")
        if not isinstance(content, str):
            raise SafetyError(f"edit for {e.get('path')!r} has no content")
        if len(content.encode()) > MAX_FILE_BYTES:
            raise SafetyError(f"file too large: {e.get('path')!r}")
