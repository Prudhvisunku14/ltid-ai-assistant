import mimetypes, os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from ..services import gallery, prompt_a, prompt_b, prompt_d, inventory, external
from ..services.pdf import markdown_to_pdf
from ..agents import orchestrator
from ..config import PREVIEW_URL, PROMPT_B_PREVIEW_URL, INVENTORY_PREVIEW_URL

router = APIRouter(prefix="/api")

# Projects that have a recorded run. Gallery placeholders are deliberately absent so they never serve invented data.
SERVICES = {"prompt-a": prompt_a, "prompt-b": prompt_b, "inventory": inventory, **external._instances}

@router.get("/health")
def health(): return {"status": "ok"}

@router.get("/overview")
def overview(): return gallery.overview()

@router.get("/projects")
def projects(): return gallery.projects()

def _svc(pid: str):
    s = SERVICES.get(pid)
    if not s: raise HTTPException(404, "This project has no recorded run (placeholder entry).")
    return s

def _feature(pid: str, name: str):
    f = getattr(_svc(pid), name, None)
    if f is None: raise HTTPException(404, f"'{name}' is not available for this project.")
    return f

@router.get("/projects/{pid}")
def project(pid: str):
    p = next((x for x in gallery.projects() if x["id"] == pid), None)
    if not p: raise HTTPException(404, "unknown project")
    return p

@router.get("/projects/{pid}/analysis")
def analysis(pid: str): return _svc(pid).analysis()
@router.get("/projects/{pid}/timeline")
def timeline(pid: str): return _svc(pid).timeline()
@router.get("/projects/{pid}/tests")
def tests(pid: str):
    if pid == "prompt-d-explicit":
        return prompt_d.tests()
    return _svc(pid).tests()
@router.get("/projects/{pid}/git")
def git(pid: str): return _svc(pid).git()
@router.get("/projects/{pid}/summary")
def summary(pid: str): return _svc(pid).summary()
@router.get("/projects/{pid}/tree")
def tree(pid: str): return _svc(pid).tree()
@router.get("/projects/{pid}/file")
def file(pid: str, path: str): return _svc(pid).file_content(path)
@router.get("/projects/{pid}/raw")
def raw(pid: str, path: str):
    p = _svc(pid).raw_file(path)
    return FileResponse(p, filename=p.name, media_type=mimetypes.guess_type(p.name)[0] or "application/octet-stream")
@router.get("/projects/{pid}/diff")
def diff(pid: str): return _svc(pid).diffs()
@router.get("/projects/{pid}/screenshots")
def shots(pid: str): return _svc(pid).screenshots()
@router.get("/projects/{pid}/screenshot/{name}")
def shot(pid: str, name: str):
    p = _svc(pid).SHOT_DIR / f"{os.path.basename(name)}.png"
    if not p.is_file(): raise HTTPException(404, "no such screenshot")
    return FileResponse(p, media_type="image/png")
@router.get("/projects/{pid}/preview")
def project_preview(pid: str): return _feature(pid, "preview")()
@router.get("/projects/{pid}/report")
def report(pid: str): return {"markdown": _svc(pid).report_markdown()}
@router.get("/projects/{pid}/report/download")
def report_dl(pid: str):
    return Response(_svc(pid).report_markdown(), media_type="text/markdown",
                    headers={"Content-Disposition": f'attachment; filename="{pid}-evaluation-report.md"'})
@router.get("/projects/{pid}/report/download.pdf")
def report_pdf(pid: str):
    md = _svc(pid).report_markdown()
    return Response(markdown_to_pdf(md, f"{pid} evaluation report"), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{pid}-evaluation-report.pdf"'})
@router.get("/projects/{pid}/evaluation")
def evaluation(pid: str): return _feature(pid, "evaluation")()
@router.get("/projects/{pid}/evaluation/download")
def evaluation_dl(pid: str):
    return JSONResponse(_feature(pid, "evaluation")(), headers={"Content-Disposition": f'attachment; filename="{pid}-evaluation.json"'})

@router.get("/agent/status")
def agent_status(): return orchestrator.status()
@router.get("/integrations")
def integrations(): return orchestrator.integrations()
@router.get("/preview-config")
def preview(): return {"url": PREVIEW_URL, "previews": {"prompt-a": PREVIEW_URL, "prompt-b": PROMPT_B_PREVIEW_URL, "inventory": INVENTORY_PREVIEW_URL,
                                                        **{k: e.preview()["url"] for k, e in external._instances.items()}}}
