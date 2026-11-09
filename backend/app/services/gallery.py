from ..config import PREVIEW_URL, PROMPT_B_PREVIEW_URL, INVENTORY_PREVIEW_URL
from . import prompt_a, prompt_b, prompt_c, prompt_d, inventory, external

def _has_evidence(ext) -> bool:
    return (ext.REPORTS / "test-results.json").exists()

def external_cards() -> list[dict]:
    """Gallery cards for the uploaded projects, read from their evidence folders. A project whose evidence is missing
    is listed as pending rather than shown with invented results."""
    cards = []
    for key, ext in external._instances.items():
        cfg = ext.cfg
        try:
            build, tests_txt, updated, stack = ext.build_status(), ext.test_status(), ext.last_updated(), ext.detect_stack()
            status = "built" if build == "passing" else "pending"
        except Exception:
            build, tests_txt, updated, stack, status = "unknown", "no results", None, ["Python"], "pending"
        shot = f"{key}-home"
        cards.append({"id": key, "name": cfg["name"], "description": cfg["description"], "stack": stack, "status": status,
                      "data_kind": "real", "last_updated": updated,
                      "thumbnail": f"/api/projects/{key}/screenshot/{shot}" if (ext.SHOT_DIR / f"{shot}.png").exists() else None,
                      "preview_url": ext.preview()["url"], "client": cfg["client"], "category": cfg["category"], "repo": None,
                      "build_status": build, "test_status": tests_txt, "synthetic": False, "launch_label": cfg["launch"],
                      "import_note": "Uploaded folder: no git history and no baseline snapshot, so code changes cannot be compared. Tests and the live app were run in this environment."})
    return cards

def _a_status() -> tuple[str, str]:
    try:
        t = prompt_a.tests()["totals"]
        return "built — static site, no build step", f"{t['passed']} passed, {t['failed']} failed"
    except Exception:
        return "unknown", "no results"

def projects() -> list[dict]:
    a_updated = None
    try: a_updated = prompt_a.git()["commits"][0]["date"]
    except Exception: pass
    a_build, a_tests = _a_status()
    b_build = prompt_b.build_status()
    try: b_stack = prompt_b.detect_stack()
    except Exception: b_stack = ["Python"]
    return [
      {"id": "prompt-a", "name": "Prompt A — Website Development", "description": "Northstar Studio marketing homepage upgraded from the supplied starter: mobile nav, data-driven portfolio, validated contact form, accessibility and tests.",
       "stack": ["HTML5", "CSS", "Vanilla JS", "Playwright"], "status": "built", "data_kind": "real", "last_updated": a_updated,
       "thumbnail": "/api/projects/prompt-a/screenshot/desktop-1280-fold", "preview_url": PREVIEW_URL,
       "client": "Northstar Studio", "category": "Web Development", "repo": "LTID-rep/ltid-ai-competition-website",
       "build_status": a_build, "test_status": a_tests, "synthetic": False, "launch_label": "Open Application"},
      {"id": "prompt-b", "name": "Prompt B — Weather Forecasting Demo",
       "description": "An educational temperature forecasting application that uses supplied synthetic weather observations to generate daily temperature predictions for selected cities over 1–3 days.",
       "stack": b_stack, "status": "built" if b_build == "passing" else "pending", "data_kind": "real", "last_updated": prompt_b.last_updated(),
       "thumbnail": "/api/projects/prompt-b/screenshot/desktop-1280-fold", "preview_url": PROMPT_B_PREVIEW_URL,
       "client": "Eastbay City Lab", "category": "Data Science / Machine Learning", "repo": "LTID-rep/ltid-ai-competition-weather",
       "build_status": b_build, "test_status": prompt_b.test_status(), "synthetic": True, "launch_label": "Launch Weather Demo",
       "import_note": "Imported ZIP snapshot (identical to upstream main a7022f3); no authenticated GitHub connection"},
      {"id": "inventory", "name": "Inventory Management System",
       "description": "Small-company inventory web app: register, edit, search and filter items, low-stock alerts, CSV import and export, persistent SQLite storage.",
       "stack": inventory.detect_stack(), "status": "built" if inventory.build_status() == "passing" else "pending", "data_kind": "real",
       "last_updated": inventory.last_updated(), "thumbnail": "/api/projects/inventory/screenshot/main-list", "preview_url": INVENTORY_PREVIEW_URL,
       "client": None, "category": "Business Application / Inventory", "repo": "local repository (no GitHub remote)",
       "build_status": inventory.build_status(), "test_status": inventory.test_status(), "synthetic": False, "launch_label": "Launch Inventory App",
       "import_note": "Local git repository with 5 commits; nothing has been pushed to GitHub. Uncommitted fix for /favicon.ico"},
      *external_cards(),
      {"id": "prompt-c-rag", "name": "Prompt C — Grounded RAG",
       "description": "A local document question-answering assistant with evidence citations, version-aware retrieval, and safe abstention when the knowledge base does not support an answer.",
       "stack": ["Python", "stdlib only", "BM25 retrieval", "unittest"], "status": "built", "data_kind": "imported", "last_updated": None,
       "thumbnail": None, "preview_url": None, "client": "Northstar Services", "category": "AI / Retrieval-Augmented Generation",
       "build_status": None, "test_status": prompt_c.test_status(), "synthetic": False,
       "import_note": "Locally available source and knowledge base. The 29 passing tests are recorded in docs/test_results.txt; no live LLM service or application preview is configured."},
      {"id": "prompt-d-explicit", "name": "Prompt D — DevPilot Explainability",
       "description": "A standard-library engineering agent demonstrating measured tool assessments, website workflows, leakage-aware forecasting, cited RAG with abstention, and guarded code changes.",
       "stack": ["Python", "Standard library", "unittest", "Optional OpenAI API"],
       "status": "built", "data_kind": "real", "last_updated": None, "thumbnail": None, "preview_url": None,
       "client": None, "category": "AI Agent / Explainability", "build_status": None,
       "test_status": prompt_d.test_status(), "synthetic": False,
       "import_note": "23 Prompt D tests were run locally and are recorded in the project docs. Live OpenAI, Google Drive, and GitHub access are not implied; its website spec uses a labelled mock DOCX by default."},
      {"id": "project-website-b", "name": "Project Website B", "description": "Second website evaluation scenario. Not yet run.", "stack": ["TBD"], "status": "pending", "data_kind": "pending", "last_updated": None, "thumbnail": None, "preview_url": None},
      {"id": "ecommerce", "name": "E-commerce Application", "description": "Storefront with cart and checkout. Placeholder entry.", "stack": ["React", "FastAPI"], "status": "demo", "data_kind": "mock", "last_updated": None, "thumbnail": None, "preview_url": None},
      {"id": "habit-tracker", "name": "Habit Tracker", "description": "Daily streak tracking app. Placeholder entry.", "stack": ["React", "SQLite"], "status": "demo", "data_kind": "mock", "last_updated": None, "thumbnail": None, "preview_url": None},
      {"id": "task-manager", "name": "Task Management Application", "description": "Kanban-style task manager. Placeholder entry.", "stack": ["Vue", "Node"], "status": "demo", "data_kind": "mock", "last_updated": None, "thumbnail": None, "preview_url": None},
      {"id": "portfolio", "name": "Portfolio Website", "description": "Personal portfolio generator. Placeholder entry.", "stack": ["HTML", "CSS"], "status": "demo", "data_kind": "mock", "last_updated": None, "thumbnail": None, "preview_url": None},
    ]

def overview() -> dict:
    ps = projects(); a = prompt_a.summary(); b = prompt_b.summary(); c = prompt_c.summary(); d = prompt_d.summary(); inv = inventory.summary()
    ext = {k: e.summary() for k, e in external._instances.items() if _has_evidence(e)}
    real = [a, b, c, d, inv, *ext.values()]
    failed = sum(1 for x in real if x["tests_failed"])
    placeholders = sum(p["status"] in ("demo", "pending") and p["data_kind"] in ("mock", "pending") for p in ps)
    prs = sum(1 for x in real if x["draft_pr_created"])
    return {"data_note": "Prompts A and B figures come from recorded runs; Prompt C has 29 and Prompt D has 23 passing recorded test cases. Prompt D live integrations and LLM-backed changes are not implied. Gallery entries marked 'demo'/'pending' are placeholders and are excluded from every count.",
            "total_projects": len(ps), "placeholder_projects": placeholders, "built_projects": sum(p["status"] == "built" for p in ps),
            "tests_passed": sum(x["tests_passed"] for x in real), "failed_builds": failed,
            "active_agent_tasks": 0, "pull_requests": prs,
            "pull_requests_note": "" if prs == len(real) else f"{prs} of {len(real)} — Draft PRs not created",
            "summary": a, "summaries": {"prompt-a": a, "prompt-b": b, "prompt-c-rag": c, "prompt-d-explicit": d, "inventory": inv, **ext}}
