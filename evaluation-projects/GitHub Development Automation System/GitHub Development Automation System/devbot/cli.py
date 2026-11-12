from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from . import analyzer
from .llm import MockLLM, OpenAILLM
from .pipeline import Options, run
from .safety import SafetyError


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="devbot", description="AI software maintenance automation (GPT + GitHub)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="read-only: show languages, frameworks, tools, key files")
    a.add_argument("--repo", required=True)

    r = sub.add_parser("run", help="plan, branch, edit, test, repair, draft PR (dry-run unless --live)")
    r.add_argument("--repo", required=True, help="local path or https://github.com/owner/name")
    r.add_argument("--request", required=True, help="natural-language change request")
    r.add_argument("--live", action="store_true", help="really create branch/commit/push/draft PR (default: dry-run)")
    r.add_argument("--yes", action="store_true", help="auto-approve the plan (otherwise you are asked)")
    r.add_argument("--llm", choices=["openai", "mock"], default="openai")
    r.add_argument("--mock-script", default=str(Path(__file__).resolve().parent.parent / "demo" / "demo_script.py"))
    r.add_argument("--base", help="base branch (default: repo default)")
    r.add_argument("--max-repairs", type=int, default=2)
    r.add_argument("--allow-repo", action="append", default=[], help="owner/name allowed for live mode (repeatable)")
    r.add_argument("--out-dir", default="devbot_output")
    r.add_argument("--pr-on-failure", action="store_true", help="open the draft PR even if tests still fail")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "analyze":
            rep = analyzer.analyze(Path(args.repo))
            print(json.dumps(rep.to_dict(), indent=2))
            return 0
        llm = MockLLM.from_file(args.mock_script) if args.llm == "mock" else OpenAILLM()
        res = run(Options(repo=args.repo, request=args.request, live=args.live, auto_approve=args.yes,
                          base=args.base, max_repairs=args.max_repairs, out_dir=Path(args.out_dir),
                          allow_repos=args.allow_repo, pr_on_failure=args.pr_on_failure), llm)
        print(f"\nRESULT: {res.status} | branch={res.branch} | tests_ok={res.tests_ok} | repairs={res.repairs_used}")
        return 0 if res.status == "ok" else 1
    except SafetyError as e:
        print(f"SAFETY STOP: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
