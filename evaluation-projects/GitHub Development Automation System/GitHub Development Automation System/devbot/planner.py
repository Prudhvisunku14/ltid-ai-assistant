"""Step 4-5: explain the repo with GPT, and turn a natural-language request into a plan."""
from __future__ import annotations
import json
from dataclasses import dataclass, field

from . import prompts
from .analyzer import RepoReport
from .llm import LLM

# Honest licence/cost notes shown with the plan (prefer free / open source).
TOOL_NOTES = {
    "git": "free, GPL-2.0", "python": "free, PSF licence", "unittest": "free, stdlib", "pytest": "free, MIT",
    "ruff": "free, MIT", "black": "free, MIT", "flake8": "free, MIT", "mypy": "free, MIT", "eslint": "free, MIT",
    "jest": "free, MIT", "npm": "free, Artistic-2.0", "github rest api": "free for repositories you own/are granted",
    "openai": "PAID API (only non-free component; replaceable via OPENAI_BASE_URL)",
}


@dataclass
class Plan:
    summary: str
    steps: list[str]
    files_to_change: list[str]
    tools_required: list[dict]
    risks: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        tools = []
        for t in d.get("tools_required", []):
            note = next((TOOL_NOTES[k] for k in sorted(TOOL_NOTES, key=len, reverse=True) if k in t.get("tool", "").lower()), "")
            tools.append({**t, "licence_note": note})
        return cls(d.get("summary", ""), list(d.get("steps", [])), list(d.get("files_to_change", [])),
                   tools, list(d.get("risks", [])))

    def render(self) -> str:
        out = [f"Summary: {self.summary}", "Steps:"]
        out += [f"  {i}. {s}" for i, s in enumerate(self.steps, 1)]
        out.append("Files to change: " + ", ".join(self.files_to_change))
        out.append("Tools required:")
        for t in self.tools_required:
            out.append(f"  - {t.get('tool')}: {t.get('why', '')} [{t.get('licence_note') or 'n/a'}]")
        if self.risks:
            out.append("Risks: " + "; ".join(self.risks))
        return "\n".join(out)


def explain_repo(llm: LLM, report: RepoReport, sources: dict[str, str]) -> str:
    user = json.dumps({"languages": report.languages, "frameworks": report.frameworks,
                       "heuristic_key_files": report.key_files[:25], "tools": report.dev_tools}) \
        + "\n" + prompts.files_block(dict(list(sources.items())[:8]))
    data = llm.complete_json("explain", prompts.EXPLAIN, user)
    return data.get("overview", "")


def make_plan(llm: LLM, request: str, report: RepoReport, sources: dict[str, str]) -> Plan:
    user = (f"REQUEST: {request}\nLANGUAGES: {report.languages}\nFRAMEWORKS: {report.frameworks}\n"
            f"TEST COMMAND: {' '.join(report.test_command)}\nTREE:\n{report.tree}\n\n" + prompts.files_block(sources))
    return Plan.from_dict(llm.complete_json("plan", prompts.PLAN, user))
