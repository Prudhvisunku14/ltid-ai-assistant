"""Step 8: run the project's own test command (no shell, with timeout)."""
from __future__ import annotations
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    ran: bool
    ok: bool
    command: str
    output: str


def run_tests(root: Path, command: list[str], timeout: int = 300) -> TestResult:
    if not command:
        return TestResult(False, True, "", "No test command detected; skipped.")
    try:
        r = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return TestResult(False, False, " ".join(command), f"Test tool not installed: {command[0]}")
    except subprocess.TimeoutExpired:
        return TestResult(True, False, " ".join(command), f"Timed out after {timeout}s")
    return TestResult(True, r.returncode == 0, " ".join(command), (r.stdout + r.stderr).strip())
