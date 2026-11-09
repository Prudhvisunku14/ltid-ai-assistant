"""Reads the recorded test evidence for the Prompt C grounded-RAG project."""
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from ..config import PROMPT_C

TEST_RESULTS = PROMPT_C / "docs" / "test_results.txt"
CASE = re.compile(r"^(?P<name>\S+) \((?P<class>[^)]+)\) \.\.\. (?P<status>ok|FAIL|ERROR)$")


def tests() -> dict:
    if not TEST_RESULTS.is_file():
        raise HTTPException(404, "Prompt C test evidence not found.")

    text = TEST_RESULTS.read_text(encoding="utf-8")
    cases = []
    for line in text.splitlines():
        match = CASE.match(line.strip())
        if match:
            cases.append({**match.groupdict(), "status": "passed" if match["status"] == "ok" else "failed"})

    total_match = re.search(r"^Ran (\d+) tests? in ", text, re.MULTILINE)
    if not total_match or not cases:
        raise HTTPException(500, "Prompt C test evidence has an unrecognized format.")

    failed = sum(case["status"] == "failed" for case in cases)
    if len(cases) != int(total_match.group(1)):
        raise HTTPException(500, "Prompt C recorded test count does not match its test cases.")

    ran_at = datetime.fromtimestamp(TEST_RESULTS.stat().st_mtime, timezone.utc).isoformat()
    return {
        "generated_at": ran_at,
        "suites": [{
            "id": "rag-unittest",
            "title": "Prompt C — Grounded RAG",
            "command": "python -m unittest discover -s tests -v",
            "ran_at": ran_at,
            "exit_code": 1 if failed or not re.search(r"^OK$", text, re.MULTILINE) else 0,
            "cases": cases,
            "output_tail": text.splitlines()[-12:],
        }],
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
