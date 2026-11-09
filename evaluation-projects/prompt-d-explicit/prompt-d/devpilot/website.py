"""D2 - Website development from a (Drive) DOCX spec.
Reads the REAL files in the repo copy, plans per requirement, edits idempotently, checks, commits on a branch,
and prepares a DRAFT pull request. Nothing is ever merged. Unsupported requirements are reported, not faked."""
import re, shutil, sys, zipfile, datetime as dt
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
from .common import run_cmd

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
GIT = ["git", "-c", "user.name=DevPilot", "-c", "user.email=devpilot@example.invalid"]


def read_docx_requirements(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = ["".join(t.text or "" for t in p.iter(W + "t")) for p in root.iter(W + "p")]
    return [(m.group(1), m.group(2).strip()) for p in paras if (m := re.match(r"\s*(REQ-\d+):\s*(.+)", p))]


# ---------- idempotent HTML/CSS/JS edits ----------
def ensure_lang(h):
    return h if re.search(r"<html[^>]*\blang=", h) else re.sub(r"<html\b", '<html lang="en"', h, count=1)

def ensure_title(h, name):
    if re.search(r"<title>.+?</title>", h, re.S):
        return h
    m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
    t = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else name
    return h.replace("</head>", f"<title>{t}</title>\n</head>", 1)

def ensure_skip_link(h):
    if "skip-link" not in h:
        h = re.sub(r"(<body[^>]*>)", r'\1\n<a class="skip-link" href="#main">Skip to content</a>', h, count=1)
    return re.sub(r"<main(?![^>]*\bid=)", '<main id="main"', h, count=1)

def ensure_nav_link(h, href, label):
    return h if f'href="{href}"' in h else h.replace("</nav>", f' <a href="{href}">{label}</a></nav>', 1)

def ensure_toggle(h):
    if 'id="theme-toggle"' in h:
        return h
    return h.replace("</header>", '<button id="theme-toggle" type="button" aria-pressed="false">Dark mode</button></header>', 1)

CONTACT_MAIN = """<main id="main"><h2>Contact us</h2>
<form id="contact-form" novalidate>
<p><label for="name">Name</label> <input id="name" name="name" required aria-describedby="name-error"><span id="name-error" class="error" role="alert"></span></p>
<p><label for="email">Email</label> <input id="email" name="email" type="email" required aria-describedby="email-error"><span id="email-error" class="error" role="alert"></span></p>
<p><label for="message">Message</label> <textarea id="message" name="message" required aria-describedby="message-error"></textarea><span id="message-error" class="error" role="alert"></span></p>
<button type="submit">Send</button> <span id="form-status" role="status"></span>
</form></main>"""

JS_ADD = """
// --- DevPilot: dark mode + contact validation ---
function validateContact(v) {
  var e = {};
  if (!v.name || !String(v.name).trim()) e.name = "Please enter your name.";
  if (!v.email || !/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(v.email)) e.email = "Please enter a valid email address.";
  if (!v.message || !String(v.message).trim()) e.message = "Please enter a message.";
  return e;
}
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  var b = document.getElementById("theme-toggle");
  if (b) b.setAttribute("aria-pressed", String(t === "dark"));
}
document.addEventListener("DOMContentLoaded", function () {
  var saved = null;
  try { saved = localStorage.getItem("theme"); } catch (x) {}
  applyTheme(saved === "dark" ? "dark" : "light");
  var b = document.getElementById("theme-toggle");
  if (b) b.addEventListener("click", function () {
    var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("theme", next); } catch (x) {}
  });
  var f = document.getElementById("contact-form");
  if (f) f.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var vals = { name: f.name.value, email: f.email.value, message: f.message.value };
    var errs = validateContact(vals);
    ["name", "email", "message"].forEach(function (k) {
      document.getElementById(k + "-error").textContent = errs[k] || "";
      f[k].setAttribute("aria-invalid", errs[k] ? "true" : "false");
    });
    document.getElementById("form-status").textContent = Object.keys(errs).length ? "Please fix the errors above." : "Thanks! (demo form: nothing was sent)";
  });
});
if (typeof module !== "undefined") module.exports = { validateContact: validateContact };
"""
CSS_ADD = """
/* DevPilot additions */
.skip-link { position: absolute; left: -999px; } .skip-link:focus { left: 0; background: #ff0; padding: .5rem; }
.error { color: #b00020; margin-left: .5rem; }
[data-theme="dark"] body { background: #121212; color: #eee; } [data-theme="dark"] a { color: #8ab4f8; }
[data-theme="dark"] .error { color: #ff8a80; }
"""


def append_once(path, marker, text):
    s = path.read_text()
    if marker not in s:
        path.write_text(s.rstrip() + "\n" + text)


class Handlers:
    """requirement text -> handler. Returns list of files changed. Add handlers here or supply an LLM for others."""
    def __init__(self, repo):
        self.repo = Path(repo)

    def pages(self):
        return sorted(self.repo.glob("*.html"))

    def contact(self):
        changed = []
        tpl = (self.repo / "index.html").read_text()
        target = self.repo / "contact.html"
        if not target.exists():
            html = re.sub(r"<main.*?</main>", lambda m: CONTACT_MAIN, tpl, flags=re.S)
            html = re.sub(r"<h1>.*?</h1>", "<h1>Contact Acme Bakery</h1>", html, count=1, flags=re.S)
            html = re.sub(r"<title>.*?</title>\s*", "", html, flags=re.S)
            target.write_text(html); changed.append("contact.html")
        for p in self.pages():
            h = p.read_text(); n = ensure_nav_link(h, "contact.html", "Contact")
            if n != h: p.write_text(n); changed.append(p.name)
        for f, m, t in (("app.js", "function validateContact", JS_ADD), ("style.css", "DevPilot additions", CSS_ADD)):
            if m not in (self.repo / f).read_text(): changed.append(f)
            append_once(self.repo / f, m, t)
        return changed

    def dark_mode(self):
        changed = []
        for p in self.pages():
            h = p.read_text(); n = ensure_toggle(h)
            if n != h: p.write_text(n); changed.append(p.name)
        for f, m, t in (("app.js", "function validateContact", JS_ADD), ("style.css", "DevPilot additions", CSS_ADD)):
            if m not in (self.repo / f).read_text(): changed.append(f)
            append_once(self.repo / f, m, t)
        return changed

    def a11y(self):
        changed = []
        for p in self.pages():
            h = p.read_text(); n = ensure_skip_link(ensure_title(ensure_lang(h), p.stem.title()))
            if n != h: p.write_text(n); changed.append(p.name)
        append_once(self.repo / "style.css", "DevPilot additions", CSS_ADD)
        return changed


ROUTES = [(re.compile(r"contact", re.I), "contact"), (re.compile(r"dark mode|theme", re.I), "dark_mode"),
          (re.compile(r"language|title|skip", re.I), "a11y")]


def plan(reqs):
    out = []
    for rid, text in reqs:
        route = next((r for rx, r in ROUTES if rx.search(text)), None)
        out.append({"id": rid, "text": text, "handler": route})
    return out


def implement(repo, steps):
    h, results = Handlers(repo), []
    for s in steps:
        if s["handler"] is None:
            results.append({**s, "status": "UNSUPPORTED (no handler; needs LLM/human)", "changed": []}); continue
        # contact (REQ-2 shares the contact handler) must run before pages are checked for a11y
        results.append({**s, "status": "implemented", "changed": sorted(set(getattr(h, s["handler"])()))})
    # a11y must also cover pages created by other handlers (e.g. contact.html)
    h.a11y(); h.dark_mode()
    return results


# ---------- checks (static HTML + node unit test of validation; browser test optional) ----------
class _P(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags = []; self.ids = set(); self.title = ""; self._t = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); self.tags.append((tag, a))
        if "id" in a: self.ids.add(a["id"])
        if tag == "title": self._t = True
    def handle_endtag(self, tag):
        if tag == "title": self._t = False
    def handle_data(self, d):
        if self._t: self.title += d


def parse(path):
    p = _P(); p.feed(Path(path).read_text()); return p


def run_checks(repo, run=run_cmd):
    repo, res = Path(repo), []
    ok = lambda name, cond, detail="": res.append({"check": name, "passed": bool(cond), "detail": detail})
    pages = sorted(repo.glob("*.html")); titles = []
    ok("contact.html exists", (repo / "contact.html").exists())
    for p in pages:
        d = parse(p)
        html_attrs = next((a for t, a in d.tags if t == "html"), {})
        ok(f"{p.name}: lang", html_attrs.get("lang"))
        ok(f"{p.name}: title", d.title.strip()); titles.append(d.title.strip())
        ok(f"{p.name}: skip link -> #main exists", any(t == "a" and a.get("href") == "#main" for t, a in d.tags) and "main" in d.ids)
        links = [a["href"] for t, a in d.tags if t == "a" and a.get("href", "").endswith(".html")]
        ok(f"{p.name}: nav links Contact", "contact.html" in links)
        ok(f"{p.name}: all .html links resolve", all((repo / l).exists() for l in links), str(links))
        ok(f"{p.name}: theme toggle", "theme-toggle" in d.ids)
    ok("page titles unique", len(set(titles)) == len(titles), str(titles))
    if (repo / "contact.html").exists():
        d = parse(repo / "contact.html")
        for f in ("name", "email", "message"):
            ok(f"contact: required {f}", any(a.get("id") == f and "required" in a for t, a in d.tags))
            ok(f"contact: error region for {f}", f"{f}-error" in d.ids)
    js = (repo / "app.js").read_text()
    ok("app.js persists theme (localStorage)", "localStorage.setItem" in js)
    test = ("global.document={addEventListener(){}};const {validateContact:v}=require('./app.js');const a=require('assert');"
            "a.ok(Object.keys(v({name:'A',email:'a@b.co',message:'hi'})).length===0);"
            "a.ok(v({name:'',email:'a@b.co',message:'hi'}).name);a.ok(v({name:'A',email:'bad',message:'hi'}).email);"
            "a.ok(v({name:'A',email:'a@b.co',message:'  '}).message);console.log('js ok')")
    rc, out, err = run(["node", "-e", test], cwd=str(repo))
    if rc == 127:
        res.append({"check": "node unit test of validateContact", "passed": None, "detail": "SKIPPED: node not installed"})
    else:
        ok("node unit test of validateContact", rc == 0, (out + err).strip()[:200])
    bt = Path(__file__).resolve().parent.parent / "scripts" / "browser_test.py"
    rc, out, err = run([sys.executable, str(bt), str(repo)], timeout=90)
    if rc == 3:
        res.append({"check": "real-browser test", "passed": None, "detail": "SKIPPED (not a pass): " + (out + err).strip()[:120]})
    else:
        ok("real-browser test (Chromium)", rc == 0, (out + err).strip()[-200:])
    return res


def git_branch_and_pr(repo, results, checks, run=run_cmd, branch=None):
    repo = Path(repo)
    branch = branch or "devpilot/spec-" + dt.date.today().strftime("%Y%m%d")
    if not (repo / ".git").exists():
        run(["git", "init", "-q", "-b", "main"], cwd=str(repo))
    run(GIT + ["add", "-A"], cwd=str(repo))
    run(["git", "checkout", "-q", "-B", branch], cwd=str(repo))
    run(GIT + ["add", "-A"], cwd=str(repo))
    rc, out, err = run(GIT + ["commit", "-q", "-m", "Implement website spec requirements (DevPilot)"], cwd=str(repo))
    body = ["# Draft PR: implement website spec", "", "| Req | Status | Files |", "|---|---|---|"]
    body += [f"| {r['id']} | {r['status']} | {', '.join(r['changed']) or '-'} |" for r in results]
    body += ["", "## Checks"] + [f"- {'PASS' if c['passed'] else ('SKIP' if c['passed'] is None else 'FAIL')}: {c['check']} {c['detail']}" for c in checks]
    body += ["", "Not merged. Needs human review."]
    (repo / "PR_DRAFT.md").write_text("\n".join(body))
    info = {"branch": branch, "commit_rc": rc, "pr": None}
    rc_r, remotes, _ = run(["git", "remote"], cwd=str(repo))
    rc_a, _, _ = run(["gh", "auth", "status"])
    if remotes.strip() and rc_a == 0:
        rp, _, e1 = run(["git", "push", "-u", "origin", branch], cwd=str(repo), timeout=60)
        if rp == 0:
            rc_pr, out_pr, e2 = run(["gh", "pr", "create", "--draft", "--title", "Implement website spec (DevPilot)",
                                     "--body-file", "PR_DRAFT.md"], cwd=str(repo), timeout=60)
            info["pr"] = out_pr.strip() if rc_pr == 0 else f"gh pr create failed: {e2.strip()[:150]}"
        else:
            info["pr"] = f"push failed: {e1.strip()[:150]}"
    else:
        info["pr"] = ("NOT CREATED: " + ("no git remote" if not remotes.strip() else "gh not authenticated")
                      + ". Body saved to PR_DRAFT.md. Run: git push -u origin " + branch + " && gh pr create --draft --body-file PR_DRAFT.md")
    return info


def run_website(spec_path, repo_src, work_dir, run=run_cmd):
    work = Path(work_dir)
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(repo_src, work)
    run(["git", "init", "-q", "-b", "main"], cwd=str(work))
    run(GIT + ["add", "-A"], cwd=str(work)); run(GIT + ["commit", "-q", "-m", "baseline (existing site)"], cwd=str(work))
    reqs = read_docx_requirements(spec_path)
    steps = plan(reqs)
    results = implement(work, steps)
    checks = run_checks(work, run)
    pr = git_branch_and_pr(work, results, checks, run)
    return {"requirements": reqs, "plan": steps, "results": results, "checks": checks, "git": pr, "work_dir": str(work)}


def render(r):
    L = ["# D2 Website implementation", "", "Spec source: MOCK Drive DOCX unless Drive credentials are configured.", "", "## Plan / result"]
    L += [f"- {x['id']}: {x['text']} -> {x['status']} ({', '.join(x['changed']) or 'no change'})" for x in r["results"]]
    L += ["", "## Checks"] + [f"- {'PASS' if c['passed'] else ('SKIP' if c['passed'] is None else 'FAIL')}: {c['check']} {c['detail']}" for c in r["checks"]]
    L += ["", "## Git / PR", f"- branch: {r['git']['branch']}", f"- draft PR: {r['git']['pr']}"]
    return "\n".join(L)
