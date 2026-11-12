"""Step 7-8: generate code edits, apply them safely, and repair after failed tests."""
from __future__ import annotations
from pathlib import Path

from . import prompts
from .llm import LLM
from .safety import validate_edit_path, validate_edit_set


def _current(root: Path, paths: list[str]) -> dict[str, str]:
    out = {}
    for p in paths:
        f = validate_edit_path(root, p)
        out[p] = f.read_text(encoding="utf-8") if f.exists() else "(new file)"
    return out


def generate_edits(llm: LLM, root: Path, request: str, plan_text: str, context: dict[str, str]) -> list[dict]:
    user = f"APPROVED REQUEST: {request}\nAPPROVED PLAN:\n{plan_text}\n\n" + prompts.files_block(context)
    edits = llm.complete_json("edit", prompts.EDIT, user).get("files", [])
    validate_edit_set(root, edits)
    return edits


def generate_repair(llm: LLM, root: Path, request: str, test_output: str, touched: list[str]) -> tuple[str, list[dict]]:
    user = (f"REQUEST: {request}\nFAILING TEST OUTPUT:\n{test_output[-6000:]}\n\n"
            + prompts.files_block(_current(root, touched)))
    data = llm.complete_json("repair", prompts.REPAIR, user)
    edits = data.get("files", [])
    validate_edit_set(root, edits)
    return data.get("diagnosis", ""), edits


def apply_edits(root: Path, edits: list[dict]) -> list[str]:
    validate_edit_set(root, edits)
    written = []
    for e in edits:
        f = validate_edit_path(root, e["path"])
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(e["content"], encoding="utf-8")
        written.append(e["path"])
    return written
