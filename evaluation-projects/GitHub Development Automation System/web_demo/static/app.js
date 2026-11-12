"use strict";
// devbot web UI. Secrets live only in the two password inputs (this tab's memory); nothing is put in storage or the URL.
const $ = (id) => document.getElementById(id);
const show = (el, on) => { el.hidden = !on; };
const mode = () => document.querySelector('input[name=mode]:checked').value;
const source = () => document.querySelector('input[name=source]:checked').value;
let cfg = null, runId = null, timer = null, logSeen = 0;

async function api(method, path, body) {
  const res = await fetch(path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined, cache: "no-store" });
  let data = {};
  try { data = await res.json(); } catch (e) { /* non-JSON error */ }
  if (!res.ok) throw new Error((data.error && data.error.message) || ("Request failed (" + res.status + ")"));
  return data;
}

function formError(msg) { const el = $("form-error"); el.textContent = msg || ""; show(el, !!msg); }

function payload() {
  const p = { mode: mode(), source: source(), request: $("request").value.trim(), model: $("model").value.trim() };
  if (mode() === "openai") p.openai_key = $("openai-key").value.trim();
  if (source() === "github") {
    p.repo_url = $("repo-url").value.trim(); p.trust_confirmed = $("trust").checked;
    const t = $("gh-token").value.trim(); if (t) p.github_token = t;
  }
  return p;
}

function syncForm() {
  show($("key-box"), mode() === "openai");
  show($("gh-box"), source() === "github");
  if (mode() === "mock" && source() === "github") { $("src-demo").checked = true; show($("gh-box"), false); }
  $("mode-badge").textContent = mode() === "openai" ? "Dry-run · GPT (your key)" : "Dry-run · offline demo";
}

function kv(dl, rows) {
  dl.textContent = "";
  rows.forEach(([k, v]) => { const dt = document.createElement("dt"); dt.textContent = k; const dd = document.createElement("dd"); dd.textContent = v; dl.append(dt, dd); });
}

async function analyze() {
  formError("");
  const p = payload();
  $("analyze-btn").disabled = true;
  try {
    const a = await api("POST", "/api/analyze", p);
    const langs = Object.entries(a.languages).map(([k, v]) => k + " (" + v + ")").join(", ") || "none";
    kv($("analysis"), [
      ["Files", String(a.file_count)], ["Languages", langs], ["Frameworks", a.frameworks.join(", ") || "none detected"],
      ["Package managers", a.package_managers.join(", ") || "none"],
      ["Dev tools", a.dev_tools.map((t) => t.tool + " (" + t.purpose + ")").join(", ") || "none"],
      ["Test command", a.test_command || "none detected"],
      ["Key files", a.key_files.slice(0, 12).map((f) => f.path + " – " + f.purpose).join("\n")],
      ["Overview", a.overview ? a.overview + "  [" + a.overview_source + "]" : (a.overview_error || "Add your OpenAI key to get a GPT explanation.")],
    ]);
    $("analysis-tree").textContent = a.tree;
    show($("analysis-card"), true);
  } catch (e) { formError(e.message); } finally { $("analyze-btn").disabled = false; }
}

async function startRun() {
  formError(""); show($("run-error"), false);
  const p = payload();
  $("run-btn").disabled = true;
  try {
    const job = await api("POST", "/api/runs", p);
    runId = job.id; logSeen = 0;
    $("log").textContent = ""; show($("result"), false); show($("approval"), false);
    show($("run-card"), true); $("run-status").textContent = "running"; $("run-status").className = "badge b-soft";
    $("run-card").scrollIntoView({ behavior: "smooth", block: "start" });
    poll();
  } catch (e) { formError(e.message); $("run-btn").disabled = false; }
}

async function poll() {
  clearTimeout(timer);
  let job;
  try { job = await api("GET", "/api/runs/" + runId + "?since=" + logSeen); }
  catch (e) { showRunError(e.message); finish(); return; }
  if (job.log.length) { $("log").textContent += job.log.join("\n") + "\n"; logSeen = job.log_total; $("log").scrollTop = $("log").scrollHeight; }
  const labels = { running: "running", awaiting_approval: "waiting for your approval", done: "finished", safety_stop: "stopped by a safety rule", error: "failed" };
  $("run-status").textContent = labels[job.status] || job.status;
  $("run-status").className = "badge " + ({ done: "b-ok", error: "b-bad", safety_stop: "b-bad", awaiting_approval: "b-warn" }[job.status] || "b-soft");
  if (job.status === "awaiting_approval") { $("plan").textContent = job.plan; show($("approval"), true); } else show($("approval"), false);
  if (job.status === "done") { renderResult(job.result); finish(); return; }
  if (job.status === "safety_stop" || job.status === "error") { showRunError(job.error); finish(); return; }
  timer = setTimeout(poll, 700);
}

function showRunError(msg) { const el = $("run-error"); el.textContent = msg; show(el, true); }
function finish() { $("run-btn").disabled = false; }

function renderResult(r) {
  const box = $("result-box");
  const good = r.status === "ok";
  box.className = good ? "okbox" : "alert";
  box.textContent = ({ ok: "Done: the change was made on a branch in the scratch copy and the tests pass. A draft pull request preview was written.",
    "tests-failing": "The tests still fail after the repair attempts, so no pull request preview was written. Review the log and diff.",
    "aborted-not-approved": "You did not approve the plan, so nothing was changed." })[r.status] || r.status;
  kv($("result-kv"), [["Status", r.status], ["Branch (scratch copy)", r.branch || "–"], ["Files changed", r.files_changed.join(", ") || "–"],
    ["Tests", r.tests_ok ? "passing" : "failing / not run"], ["Repair attempts", String(r.repairs_used)], ["Mode", r.mode], ["Note", r.note]]);
  $("pr").textContent = r.pr_preview || "(none)";
  $("diff").textContent = r.diff || "(none)";
  show($("result"), true);
}

async function decide(kind) {
  $("approve-btn").disabled = $("reject-btn").disabled = true;
  try { await api("POST", "/api/runs/" + runId + "/" + kind, {}); show($("approval"), false); poll(); }
  catch (e) { showRunError(e.message); }
  finally { $("approve-btn").disabled = $("reject-btn").disabled = false; }
}

async function boot() {
  try {
    cfg = await api("GET", "/api/config");
    $("model").value = cfg.default_model;
    $("request").value = cfg.demo_request;
    const chip = document.createElement("button");
    chip.type = "button"; chip.className = "chip"; chip.textContent = "Bulk-discount example (bookshop-api)";
    chip.addEventListener("click", () => { $("request").value = cfg.demo_request; });
    $("examples").append(chip);
    if (!cfg.git_available) { $("boot-error").textContent = "git is not installed on the server, so devbot cannot run."; show($("boot-error"), true); }
  } catch (e) { $("boot-error").textContent = "Could not load the app configuration: " + e.message; show($("boot-error"), true); }
  syncForm();
}

document.querySelectorAll("input[name=mode],input[name=source]").forEach((el) => el.addEventListener("change", syncForm));
$("clear-key").addEventListener("click", () => { $("openai-key").value = ""; $("openai-key").focus(); });
$("run-btn").addEventListener("click", startRun);
$("analyze-btn").addEventListener("click", analyze);
$("approve-btn").addEventListener("click", () => decide("approve"));
$("reject-btn").addEventListener("click", () => decide("reject"));
boot();
