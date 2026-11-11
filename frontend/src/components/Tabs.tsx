import { useApi } from '../services/hooks'
import type { Analysis, Git, Tests, Step, PlanItem } from '../services/types'
import { Card, H, Loading, Pill, fmt, KindBadge } from './ui'
import Timeline from './Timeline'
import { GitBranch, GitCommit, ExternalLink, ArrowRight } from 'lucide-react'

const A = 'prompt-a'
const SynthBanner = () => <div className="text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2 mb-4"><strong>Educational demonstration using synthetic observations – not a real weather forecast.</strong> The supplied dataset is synthetic.</div>

export function RequirementsTab({ pid = A }: { pid?: string }) { const a = useApi<Analysis>(`/api/projects/${pid}/analysis`); if (!a.data) return <Loading error={a.error} />
  return <div><H title="Original requirements" sub={a.data.requirements_source.access} right={<KindBadge kind="imported" />} />
    <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted"><tr><th className="p-3 w-28">Area</th><th className="p-3">Requirement</th><th className="p-3">Status in starter</th><th className="p-3">Result</th></tr></thead>
      <tbody>{a.data.requirements.map(r => <tr key={r.id} className="border-t border-line align-top"><td className="p-3 font-medium">{r.area}</td><td className="p-3">{r.text}</td><td className="p-3 text-muted">{r.original}</td><td className="p-3">{r.result}</td></tr>)}</tbody></table></Card></div> }

export function RepoTab({ pid = A }: { pid?: string }) { const a = useApi<Analysis>(`/api/projects/${pid}/analysis`); if (!a.data) return <Loading error={a.error} />; const r = a.data.repository
  const rows: [string, string][] = [['Repository', r.slug], ['Import method', r.import_method], ['Frontend framework', r.framework], ['Backend', r.backend], ['Routes', r.routes], ['Base branch', `${r.base_branch} — ${r.base_branch_note}`]]
  return <div><H title="Repository analysis" right={<KindBadge kind="real" />} />
    {r.import_status === 'zip_snapshot' && <div className="text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2 mb-3"><strong>Imported ZIP snapshot.</strong> This repository was not cloned through an authenticated GitHub connection.</div>}
    <Card className="divide-y divide-line">{rows.map(([k, v]) => <div key={k} className="flex gap-4 p-3 text-sm flex-wrap"><div className="w-44 text-muted shrink-0">{k}</div><div className="flex-1 min-w-0 break-words">{v}</div></div>)}
      <div className="p-3 text-sm"><div className="text-muted mb-1">Original files</div><div className="flex flex-wrap gap-2">{r.original_files.map((f: string) => <code key={f} className="bg-slate-100 px-2 py-0.5 rounded text-xs">{f}</code>)}</div></div></Card>
    {a.data.existing_issues && <div className="mt-5"><H title="Existing implementation: issues found by running it" sub="Each row was observed by executing the original code, not assumed." />
      <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted"><tr><th className="p-3 w-12">ID</th><th className="p-3 w-28">Area</th><th className="p-3">Finding</th><th className="p-3">Observed</th></tr></thead>
        <tbody>{a.data.existing_issues.map(e => <tr key={e.id} className="border-t border-line align-top"><td className="p-3 font-mono text-xs">{e.id}</td><td className="p-3">{e.area}</td><td className="p-3">{e.finding}</td><td className="p-3 text-muted font-mono text-xs break-words">{e.observed}</td></tr>)}</tbody></table></Card></div>}</div> }

export function ToolsTab({ pid = A }: { pid?: string }) { const a = useApi<Analysis>(`/api/projects/${pid}/analysis`); if (!a.data) return <Loading error={a.error} />
  const env = a.data.environment
  return <div><H title="Tool selection" sub="Alternatives considered and why each was chosen or rejected. Only tools marked Selected were used." />
    <div className="grid md:grid-cols-2 gap-3">{a.data.tools.map(t => <Card key={t.name} className="p-4"><div className="flex justify-between gap-2 mb-1"><span className="font-medium text-sm">{t.name}</span>
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${t.decision.startsWith('Selected') ? 'bg-green-50 text-ok' : 'bg-slate-100 text-muted'}`}>{t.decision}</span></div><p className="text-sm text-muted">{t.reason}</p></Card>)}</div>
    {env && <Card className="p-4 mt-4"><div className="font-medium text-sm mb-2">Detected on the build machine</div><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1 text-sm">{Object.entries(env).map(([k, v]) => <div key={k} className="flex justify-between gap-3 border-b border-line py-1"><span className="text-muted">{k}</span><span className={v ? 'font-mono text-xs' : 'text-muted text-xs'}>{v ?? 'not installed'}</span></div>)}</div></Card>}</div> }

export function PlanTab({ pid = A }: { pid?: string }) { const a = useApi<Analysis>(`/api/projects/${pid}/analysis`); if (!a.data) return <Loading error={a.error} />
  const plan = a.data.plan
  if (plan.length && typeof plan[0] !== 'string') {
    return <div><H title="Implementation plan" sub="Task, files affected, selected tools, status and verification evidence." />
      <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted"><tr><th className="p-3 w-10">#</th><th className="p-3">Task</th><th className="p-3">Files affected</th><th className="p-3">Tools</th><th className="p-3">Status</th><th className="p-3">Verification evidence</th></tr></thead>
        <tbody>{(plan as PlanItem[]).map(p => <tr key={p.n} className="border-t border-line align-top"><td className="p-3 text-muted">{p.n}</td><td className="p-3 font-medium">{p.task}</td><td className="p-3 font-mono text-xs break-words">{p.files}</td><td className="p-3 text-muted">{p.tools}</td><td className="p-3"><Pill s={p.status} /></td><td className="p-3 text-muted">{p.evidence || '—'}</td></tr>)}</tbody></table></Card></div>
  }
  return <div><H title="Implementation plan" /><Card className="p-5"><ol className="space-y-3">{(plan as string[]).map((p, i) => <li key={i} className="flex gap-3 text-sm"><span className="w-6 h-6 rounded-full bg-soft text-brand text-xs font-semibold flex items-center justify-center shrink-0">{i + 1}</span>{p}</li>)}</ol></Card></div> }

/** Prompt B only: available data (B), forecasting method (C) and architecture (D). */
export function DataMethodTab({ pid }: { pid: string }) { const a = useApi<Analysis>(`/api/projects/${pid}/analysis`); const e = useApi<{ evaluation: { cities: any[] } }>(`/api/projects/${pid}/evaluation`)
  if (!a.data) return <Loading error={a.error} />; const d = a.data.dataset, m = a.data.method, arch = a.data.architecture
  if (!d || !m || !arch) return <Card className="p-5 text-sm text-muted">No dataset/method analysis recorded for this project.</Card>
  const cmp = e.data?.evaluation.cities[0]
  return <div className="space-y-6"><SynthBanner />
    <div><H title="Available data" sub="Profiled from the supplied CSV by scripts/run_evidence.py" right={<KindBadge kind="real" />} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">{[['Dataset file', d.file], ['Observations', d.observations], ['Cities', d.cities.length], ['Date range', `${d.date_range[0]} → ${d.date_range[1]}`], ['Missing values', d.missing_values], ['Malformed observations', d.malformed_observations], ['Duplicate observations', d.duplicate_observations], ['Synthetic dataset', d.synthetic ? 'Yes' : 'No']].map(([k, v]) =>
        <Card key={String(k)} className="p-3"><div className="text-xs text-muted">{k}</div><div className="font-semibold text-sm mt-0.5 break-words">{String(v)}</div></Card>)}</div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted"><tr><th className="p-3">City</th><th className="p-3">Obs.</th><th className="p-3">Dates</th><th className="p-3">Missing days</th><th className="p-3">°C range</th></tr></thead>
          <tbody>{d.cities.map(c => <tr key={c.city} className="border-t border-line"><td className="p-3 font-medium">{c.city}</td><td className="p-3">{c.observations}</td><td className="p-3 text-xs">{c.first_date} → {c.last_date}</td><td className="p-3">{c.missing_calendar_days}</td><td className="p-3">{c.temp_min_c} – {c.temp_max_c}</td></tr>)}</tbody></table></Card>
        <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted"><tr><th className="p-3">Column</th><th className="p-3">Type</th><th className="p-3">Missing</th><th className="p-3">Example</th></tr></thead>
          <tbody>{d.columns.map(c => <tr key={c.column} className="border-t border-line"><td className="p-3 font-mono text-xs">{c.column}</td><td className="p-3">{c.type}</td><td className="p-3">{c.missing}</td><td className="p-3 font-mono text-xs">{c.example}</td></tr>)}</tbody></table></Card></div>
      <p className="text-xs text-muted mt-2">{d.synthetic_evidence} Temperature column: {d.temperature_columns.join(', ')}. Context columns (loaded, not used by the method): {d.context_columns.join(', ')}.</p></div>
    <div><H title="Forecasting method" sub={m.name} />
      <Card className="p-5 text-sm space-y-2"><p><strong>Why selected:</strong> {m.why}</p><p><strong>How it predicts:</strong> {m.how}</p><p><strong>Limitations:</strong> {m.limitations}</p><p><strong>Why not a machine-learning model:</strong> {m.why_not_ml}</p>
        <p className="text-xs text-muted">The method is described as a transparent statistical baseline. It makes no claim to produce real-world weather forecasts.</p></Card>
      {cmp && <Card className="overflow-x-auto mt-3"><div className="p-3 text-sm font-medium border-b border-line">Candidate methods — {cmp.city} <span className="text-xs text-muted font-normal">(selected using the training period only; held-out MAE shown for transparency)</span></div>
        <table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted"><tr><th className="p-3">Method</th><th className="p-3">Cycle</th><th className="p-3">Training backtest MAE °C</th><th className="p-3">Held-out MAE °C</th></tr></thead>
          <tbody>{cmp.comparison.map((c: any) => <tr key={c.method} className={`border-t border-line ${c.selected ? 'bg-soft' : ''}`}><td className="p-3">{c.label} {c.selected && <span className="ml-1 text-[11px] bg-green-50 text-ok px-2 py-0.5 rounded-full">selected</span>}</td><td className="p-3">{c.period ?? '—'}</td><td className="p-3">{c.train_backtest_mae.toFixed(3)}</td><td className="p-3">{c.heldout_mae?.toFixed(3)}</td></tr>)}</tbody></table></Card>}</div>
    <div><H title="Architecture" sub="Each stage is a real module; data flows left to right." />
      <div className="flex flex-wrap items-stretch gap-2">{arch.map((s, i) => <div key={s.step} className="flex items-center gap-2"><Card className="p-3 w-44 h-full"><div className="text-[11px] text-brand font-semibold">{i + 1}</div><div className="text-sm font-medium leading-tight">{s.step}</div><code className="text-[11px] text-muted break-words">{s.module}</code><div className="text-[11px] text-muted mt-1">{s.detail}</div></Card>{i < arch.length - 1 && <ArrowRight size={16} className="text-muted shrink-0 hidden sm:block" />}</div>)}</div></div></div> }

export function TestsTab({ pid = A }: { pid?: string }) { const t = useApi<Tests>(`/api/projects/${pid}/tests`); if (!t.data) return <Loading error={t.error} />
  const script = pid === 'prompt-d-explicit' ? 'docs/test_results.txt (recorded unittest output)' : pid === A ? 'scripts/run_evidence.py' : pid === 'prompt-b' ? 'scripts/run_evidence.py (Prompt B)' : pid === 'inventory' ? 'inventory/tests (python -m unittest + browser_e2e)' : 'evaluation-projects/scripts/collect_external.py'
  return <div><H title="Test results" sub={`Recorded ${fmt(t.data.generated_at)} by ${script}`} right={<KindBadge kind={'real'} />} />
    <div className="grid grid-cols-3 gap-3 mb-4"><Card className="p-4"><div className="text-xs text-muted">Passed</div><div className="text-2xl font-semibold text-ok">{t.data.totals.passed}</div></Card>
      <Card className="p-4"><div className="text-xs text-muted">Failed</div><div className={`text-2xl font-semibold ${t.data.totals.failed ? 'text-err' : ''}`}>{t.data.totals.failed}</div></Card>
      <Card className="p-4"><div className="text-xs text-muted">Suites</div><div className="text-2xl font-semibold">{t.data.suites.length}</div></Card></div>
    {t.data.build && <Card className="p-3 mb-4 text-sm flex items-center gap-3 flex-wrap"><span className="text-muted">Build check</span><Pill s={t.data.build.status} /><code className="text-xs text-muted break-words">{t.data.build.command}</code></Card>}
    {t.data.suites.map(s => <Card key={s.id} className="mb-4 overflow-hidden"><div className="p-4 border-b border-line flex justify-between items-start gap-3"><div className="min-w-0"><div className="font-medium text-sm">{s.title}</div><code className="text-xs text-muted break-words">{s.command}</code></div><div className="text-right text-xs text-muted shrink-0">exit code {s.exit_code}<br />{fmt(s.ran_at)}</div></div>
      <ul>{s.cases.map(c => <li key={c.class + c.name} className="flex items-center justify-between gap-3 px-4 py-2 text-sm border-b border-line last:border-0"><span className="min-w-0 break-words"><span className="font-mono text-[13px]">{c.name}</span><span className="text-xs text-muted ml-2">{c.class}</span></span><Pill s={c.status} /></li>)}</ul></Card>)}</div> }

export function GitTab({ pid = A }: { pid?: string }) { const g = useApi<Git>(`/api/projects/${pid}/git`); if (!g.data) return <Loading error={g.error} />; const d = g.data
  const pushed = d.push.status === 'pushed'
  return <div><H title="GitHub / Pull Request" sub="Only real state is shown. Nothing here is fabricated." />
    {!pushed && <div className="text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2 mb-3"><strong>Remote publication pending.</strong> The branch exists locally only; no push or Draft PR has been made.</div>}
    <Card className="p-5 mb-4 text-sm space-y-2">
      <div className="flex gap-3 flex-wrap"><span className="w-40 text-muted">Repository</span><a className="text-brand inline-flex items-center gap-1 break-all" href={d.repository_url} target="_blank" rel="noreferrer">{d.repository_url}<ExternalLink size={12} /></a></div>
      {d.import_kind && <div className="flex gap-3 flex-wrap"><span className="w-40 text-muted">Import</span><span className="flex-1 min-w-0">{d.import_kind}</span></div>}
      <div className="flex gap-3 flex-wrap"><span className="w-40 text-muted">Base branch</span><code>{d.base_branch}</code><span className={`text-xs ${d.base_branch_verified ? 'text-ok' : 'text-warn'}`}>{d.base_branch_verified ? 'verified (git ls-remote)' : 'inferred, not verified'}</span></div>
      <div className="flex gap-3 flex-wrap"><span className="w-40 text-muted">Development branch</span><code className="inline-flex items-center gap-1 break-all"><GitBranch size={13} />{d.dev_branch}</code><span className="text-xs text-muted">{pushed ? 'on remote' : 'local only'}</span></div>
      <div className="flex gap-3 items-center flex-wrap"><span className="w-40 text-muted">Push status</span><Pill s={d.push.status} /><span className="text-muted flex-1 min-w-0">{d.push.reason}</span></div>
      {d.push.attempted_at && <div className="flex gap-3 flex-wrap"><span className="w-40 text-muted">Push attempted</span><span>{fmt(d.push.attempted_at)}</span></div>}
      <div className="flex gap-3 items-center flex-wrap"><span className="w-40 text-muted">Draft PR</span><Pill s={d.draft_pr.status} /><span className="text-muted flex-1 min-w-0">{d.draft_pr.reason}</span></div>
      <div className="flex gap-3"><span className="w-40 text-muted">Pull request URL</span><span>{d.draft_pr.url ?? '— (none exists)'}</span></div></Card>
    <h3 className="font-semibold text-sm mb-2">Local commit history</h3>
    <Card className="divide-y divide-line">{[...d.commits, d.baseline_commit].map(c => <div key={c.hash} className="p-3 flex items-center gap-3 text-sm flex-wrap"><GitCommit size={16} className="text-muted" /><code className="text-xs bg-slate-100 px-1.5 rounded">{c.hash}</code><span className="flex-1 min-w-0">{c.subject}</span><span className="text-xs text-muted">{c.author} · {fmt(c.date)}</span></div>)}</Card>
    <Card className="p-4 mt-4 text-xs text-muted"><div className="font-medium text-ink mb-1">To publish (needs a valid token — not done automatically, never merged)</div>
      <pre className="font-mono whitespace-pre-wrap break-all">{`git remote add origin ${d.repository_url}.git   # already set when the repo was cloned\ngit push -u origin ${d.dev_branch}\ngh pr create --draft --base ${d.base_branch} --head ${d.dev_branch}`}</pre></Card></div> }

export function TimelineTab({ pid = A }: { pid?: string }) { const t = useApi<Step[]>(`/api/projects/${pid}/timeline`); if (!t.data) return <Loading error={t.error} />
  return <div><H title="Agent execution timeline" sub="Partial and blocked steps are shown honestly; pending actions are never marked completed." right={<KindBadge kind="real" />} /><Card className="p-5"><Timeline steps={t.data} /></Card></div> }
