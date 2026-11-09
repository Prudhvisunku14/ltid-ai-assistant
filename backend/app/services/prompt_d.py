"""Reads the recorded Prompt D DevPilot unittest output without running project code."""
import re
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import HTTPException
from ..config import PROMPT_D

TEST_RESULTS = PROMPT_D / "docs" / "test_results.txt"
CASE = re.compile(r"^(?P<name>test_\S+) \((?P<class>[^)]+)\) \.\.\. (?P<status>ok|FAIL|ERROR)$")
SUITE_TITLES = {
    "change": "D5 — Safe change-request loop",
    "forecast": "D3 — Weather forecasting",
    "rag": "D4 — Document-grounded RAG",
    "tools": "D1 — Tool assessment",
    "website": "D2 — Website workflow",
}


def tests() -> dict:
    if not TEST_RESULTS.is_file():
        raise HTTPException(404, "Prompt D test evidence not found.")

    text = TEST_RESULTS.read_text(encoding="utf-8")
    suites = defaultdict(list)
    for line in text.splitlines():
        match = CASE.match(line.strip())
        if not match:
            continue
        module = match["class"].split(".")[-3].removeprefix("test_")
        suites[module].append({
            "name": match["name"],
            "class": match["class"],
            "status": "passed" if match["status"] == "ok" else "failed",
        })

    total_match = re.search(r"^Ran (\d+) tests? in ", text, re.MULTILINE)
    cases = [case for group in suites.values() for case in group]
    if not total_match or not cases or len(cases) != int(total_match.group(1)):
        raise HTTPException(500, "Prompt D recorded test evidence is incomplete or has an unrecognized format.")

    failed = sum(case["status"] == "failed" for case in cases)
    passed_run = re.search(r"^OK$", text, re.MULTILINE) is not None
    ran_at = datetime.fromtimestamp(TEST_RESULTS.stat().st_mtime, timezone.utc).isoformat()
    return {
        "generated_at": ran_at,
        "suites": [
            {
                "id": module,
                "title": SUITE_TITLES.get(module, f"Prompt D — {module}"),
                "command": "python -m unittest discover -s tests -t . -v",
                "ran_at": ran_at,
                "exit_code": 1 if failed or not passed_run else 0,
                "cases": module_cases,
                "output_tail": [],
            }
            for module, module_cases in sorted(suites.items())
        ],
        "totals": {"passed": len(cases) - failed, "failed": failed},
    }


def test_status() -> str:
    result = tests()["totals"]
    return f"{result['passed']} passed, {result['failed']} failed"


def summary() -> dict:
    result = tests()["totals"]
    return {
        "tests_passed": result["passed"],
        "tests_failed": result["failed"],
        "draft_pr_created": False,
    }
