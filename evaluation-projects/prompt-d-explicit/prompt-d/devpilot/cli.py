import argparse, datetime as dt, json, shutil, sys, tempfile
from pathlib import Path
from . import tools, forecast, rag, website, change, demo
from .llm import OpenAILLM, ScriptedLLM

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def save(name, text):
    OUT.mkdir(exist_ok=True); (OUT / name).write_text(text); print(text); print()


def cmd_tools(a):
    rows = tools.assess(); save("D1_tools.md", tools.render(rows))
    (OUT / "D1_tools.json").write_text(json.dumps(rows, indent=2))


def cmd_website(a):
    r = website.run_website(a.spec, a.repo, OUT / "site_work"); save("D2_website.md", website.render(r))
    print(f"Working copy with branch + PR_DRAFT.md: {r['work_dir']}")


def cmd_weather(a):
    csv = ROOT / "data" / "weather_synthetic.csv"
    if not csv.exists(): forecast.make_synthetic(csv)
    _, vals = forecast.load_series(csv); res = forecast.evaluate(vals)
    fc = forecast.forecast_next(vals, res["_method"])
    save("D3_forecast.md", forecast.render(res, fc, forecast.demo_errors(tempfile.mkdtemp())))


def cmd_rag(a):
    as_of = dt.date.fromisoformat(a.as_of) if a.as_of else dt.date.today()
    c = rag.Corpus(ROOT / "data" / "policies", as_of)
    qs = a.question or ["What is the current expense claim deadline?", "Who approved our acquisition of Company Z?"]
    save("D4_rag.md", "# D4 Document-grounded RAG\n\n" + "\n\n".join(rag.render(q, rag.answer(c, q)) for q in qs))


def cmd_change(a):
    if a.demo:
        work = Path(tempfile.mkdtemp()) / "change_demo"; shutil.copytree(ROOT / "examples" / "change_demo", work)
        llm, req = ScriptedLLM(demo.scripted_replies()), demo.REQUEST
        print("[OFFLINE DEMO: scripted replies stand in for the LLM; proves the loop, not model quality]")
    else:
        if not a.request: sys.exit("--request is required (or use --demo)")
        work, llm, req = Path(a.project), OpenAILLM(), a.request
    r = change.run_change(work, req, llm, evidence_root=OUT / "evidence")
    save("D5_change.md", change.render(r)); print("Evidence:", r["evidence_dir"])
    if hasattr(llm, "usage"): print("Measured OpenAI usage:", llm.usage)


def cmd_all(a):
    a.spec, a.repo, a.as_of, a.question, a.demo = (ROOT / "data/drive_mock/website_spec.docx", ROOT / "workspace/site_repo", None, None, True)
    for f in (cmd_tools, cmd_website, cmd_weather, cmd_rag, cmd_change): f(a)


def main(argv=None):
    p = argparse.ArgumentParser(prog="devpilot"); s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("tools").set_defaults(f=cmd_tools)
    w = s.add_parser("website"); w.add_argument("--spec", default=str(ROOT / "data/drive_mock/website_spec.docx"))
    w.add_argument("--repo", default=str(ROOT / "workspace/site_repo")); w.set_defaults(f=cmd_website)
    s.add_parser("weather").set_defaults(f=cmd_weather)
    r = s.add_parser("rag"); r.add_argument("--question", action="append"); r.add_argument("--as-of"); r.set_defaults(f=cmd_rag)
    c = s.add_parser("change"); c.add_argument("--project"); c.add_argument("--request"); c.add_argument("--demo", action="store_true"); c.set_defaults(f=cmd_change)
    s.add_parser("all").set_defaults(f=cmd_all)
    a = p.parse_args(argv); a.f(a)


if __name__ == "__main__":
    main()
