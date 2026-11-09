"""D1 - Dynamic tool assessment.
Every status below is MEASURED at run time. Catalogue text is shown separately and cited, never promoted to 'verified'.
Statuses: verified | configured_unverified | unauthorized | unavailable | mock_only
"""
import json, os, shutil, sys
from pathlib import Path
from .common import run_cmd, http_get

CATALOGUE = Path(__file__).resolve().parent.parent / "data" / "tool_catalogue.json"


def _r(status, detail, scopes=None):
    return {"status": status, "detail": detail, "observed_permissions": scopes}


def check_openai(run, get, env):
    key = env.get("OPENAI_API_KEY")
    if not key:
        return _r("unavailable", "OPENAI_API_KEY not set")
    st, hdr, body = get("https://api.openai.com/v1/models", {"Authorization": f"Bearer {key}"})
    if st == 200:
        return _r("verified", "GET /v1/models returned 200 (key accepted)")
    if st in (401, 403):
        return _r("unauthorized", f"HTTP {st}: key rejected")
    if st == 0:
        return _r("configured_unverified", f"key present but network unreachable ({body[:80]})")
    return _r("unavailable", f"HTTP {st}")


def check_github(run, get, env):
    tok = env.get("GITHUB_TOKEN")
    if tok:
        st, hdr, _ = get("https://api.github.com/user", {"Authorization": f"Bearer {tok}", "User-Agent": "devpilot"})
        scopes = hdr.get("X-OAuth-Scopes") or hdr.get("x-oauth-scopes")
        if st == 200:
            return _r("verified", "GET /user returned 200", scopes or "fine-grained token (scopes not reported)")
        if st in (401, 403):
            return _r("unauthorized", f"HTTP {st}: token rejected")
        return _r("configured_unverified", "token present but GitHub unreachable")
    rc, out, err = run(["gh", "auth", "status"])
    if rc == 0:
        return _r("verified", "gh auth status OK", out.strip()[:200])
    if rc == 127:
        return _r("unavailable", "no GITHUB_TOKEN and gh CLI not installed")
    return _r("unauthorized", "gh installed but not authenticated")


def check_gdrive(run, get, env):
    tok = env.get("GDRIVE_ACCESS_TOKEN")
    if tok:
        st, hdr, _ = get("https://www.googleapis.com/drive/v3/about?fields=user", {"Authorization": f"Bearer {tok}"})
        if st == 200:
            return _r("verified", "Drive about.get returned 200")
        if st in (401, 403):
            return _r("unauthorized", f"HTTP {st}")
        return _r("configured_unverified", "token present but Drive unreachable")
    if env.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return _r("configured_unverified", "credentials file configured; live token exchange not attempted (no SDK)")
    mock = Path(__file__).resolve().parent.parent / "data" / "drive_mock"
    if mock.exists():
        return _r("mock_only", f"no credentials; local MOCK folder {mock.name}/ will be used (clearly labelled mock)")
    return _r("unavailable", "no credentials and no mock folder")


def check_git(run, get, env):
    rc, out, _ = run(["git", "--version"])
    return _r("verified", out.strip()) if rc == 0 else _r("unavailable", "git not installed")


def check_pytest(run, get, env):
    rc, out, err = run([sys.executable, "-m", "pytest", "--version"])
    if rc == 0:
        return _r("verified", (out or err).strip())
    rc2, out2, _ = run([sys.executable, "-m", "unittest", "--help"])
    if rc2 == 0:
        return _r("verified", "pytest missing; stdlib unittest works (DevPilot falls back to it)")
    return _r("unavailable", "neither pytest nor unittest runnable")


def check_docker(run, get, env):
    if shutil.which("docker") is None:
        return _r("unavailable", "docker binary not found")
    rc, out, err = run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=10)
    if rc == 0:
        return _r("verified", f"daemon reachable, server {out.strip()}")
    return _r("unavailable", f"binary found but daemon unreachable: {err.strip()[:100]}")


CHECKS = {"openai": check_openai, "github": check_github, "gdrive": check_gdrive,
          "git": check_git, "pytest": check_pytest, "docker": check_docker}


def assess(run=run_cmd, get=http_get, env=None, catalogue=CATALOGUE):
    env = os.environ if env is None else env
    cat = json.loads(Path(catalogue).read_text())
    rows = []
    for t in cat["tools"]:
        try:
            live = CHECKS[t["check"]](run, get, env)
        except Exception as e:  # a failing probe must never be reported as success
            live = _r("unavailable", f"probe crashed: {e}")
        rows.append({**t, "live": live})
    return rows


def render(rows):
    L = ["# D1 Tool assessment", "",
         "Live status is measured now; permissions/cost columns are catalogue claims with their source.", "",
         "| Tool | Live status | Evidence | Permissions (required / observed) | Cost (catalogue, cited) |", "|---|---|---|---|---|"]
    for r in rows:
        lv = r["live"]
        obs = lv["observed_permissions"] or "not observed"
        L.append(f"| {r['name']} | **{lv['status']}** | {lv['detail']} | {r['permissions']} / {obs} | {r['cost']} ([source]({r['source']})) |")
    bad = [r["name"] for r in rows if r["live"]["status"] not in ("verified",)]
    L += ["", "Not fully verified: " + (", ".join(bad) if bad else "none"),
          "Costs: no cost is 'verified' unless a live metered call produced it; DevPilot's OpenAI client records measured token counts per run."]
    return "\n".join(L)
