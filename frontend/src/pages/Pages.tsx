import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { ExternalLink, Code2, FileText, FlaskConical, LayoutDashboard, FolderTree, Database } from 'lucide-react'
import { useApi, useProjectParam, PROJECT_NAMES } from '../services/hooks'
import { abs } from '../services/api'
import type { Overview, Project, Tests, Step } from '../services/types'
import { Card, H, Loading, Pill, KindBadge, fmt } from '../components/ui'
import Explorer from '../components/Explorer'; import LivePreview from '../components/LivePreview'; import Report from '../components/Report'; import Evaluation from '../components/Evaluation'; import ProjectSwitcher from '../components/ProjectSwitcher'
import { RequirementsTab, RepoTab, ToolsTab, PlanTab, TestsTab, GitTab, TimelineTab, DataMethodTab } from '../components/Tabs'
import { DiffViewer } from '../components/Code'
import type { DiffFile } from '../services/types'

const REAL = ['prompt-a', 'prompt-b', 'inventory', 'appointment-booking', 'expense-system', 'support-ticket-system', 'docchange']      // projects with a full recorded evaluation workspace

function Stat({ label, value, note, tone = '' }: { label: string; value: number | string; note?: string; tone?: string }) {
  return <Card className="p-4"><div className="text-xs text-muted">{label}</div><div className={`text-2xl font-semibold mt-1 ${tone}`}>{value}</div>{note && <div className="text-[11px] text-muted mt-1">{note}</div>}</Card> }

const StatusChip = ({ label, value }: { label: string; value: string }) => {
  const good = /passing|built|0 failed/.test(value) && !/[1-9]\d* failed/.test(value); const bad = /failing|[1-9]\d* failed/.test(value)
  return <span className={`text-[11px] px-2 py-0.5 rounded-full border ${bad ? 'bg-red-50 text-err border-red-200' : good ? 'bg-green-50 text-ok border-green-200' : 'bg-slate-100 text-muted border-slate-200'}`}><span className="opacity-70">{label}:</span> {value}</span> }

export function ProjectCard({ p }: { p: Project }) {
  const real = REAL.includes(p.id)
  const hasTests = Boolean(p.test_status)
  return <Card className="overflow-hidden flex flex-col">
    <div className="h-40 bg-slate-100 overflow-hidden flex items-center justify-center">{p.thumbnail ? <img src={abs(p.thumbnail)} alt={`${p.name} preview`} className="w-full h-full object-cover object-top" /> : <span className="text-xs text-muted">{p.status === 'pending' ? 'No preview — not yet run' : p.status === 'demo' ? 'No preview — placeholder' : 'No live preview configured'}</span>}</div>
    <div className="p-4 flex flex-col flex-1"><div className="flex items-center gap-2 flex-wrap mb-1"><Pill s={p.status} /><KindBadge kind={p.data_kind} />{p.synthetic && <span className="text-[11px] font-medium px-2 py-0.5 rounded-full border bg-amber-50 text-warn border-amber-200 inline-flex items-center gap-1"><Database size={11} />Synthetic dataset</span>}</div>
      <Link to={`/projects/${p.id}`} className="font-semibold hover:text-brand">{p.name}</Link>
      {(p.client || p.category) && <div className="text-xs text-muted mt-0.5">{[p.client && `Client: ${p.client}`, p.category].filter(Boolean).join(' · ')}</div>}
      <p className="text-sm text-muted mt-1 flex-1">{p.description}</p>
      <div className="flex flex-wrap gap-1.5 mt-3">{p.stack.map(s => <span key={s} className="text-[11px] bg-slate-100 px-2 py-0.5 rounded">{s}</span>)}</div>
      {hasTests && <div className="flex flex-wrap gap-1.5 mt-2">{p.build_status && <StatusChip label="Build" value={p.build_status} />}{p.test_status && <StatusChip label="Tests" value={p.test_status} />}</div>}
      {p.import_note && <div className="text-[11px] text-warn mt-2">{p.import_note}</div>}
      {p.repo && <div className="text-[11px] text-muted mt-1 break-all">Repository: {p.repo}</div>}
      <div className="text-xs text-muted mt-2">Last updated: {fmt(p.last_updated)}</div>
      <div className="flex gap-2 mt-3 flex-wrap">
        {real ? <>
          <Link className="btn" to={`/projects/${p.id}`}><LayoutDashboard size={13} />Open Workspace</Link>
          {p.preview_url ? <Link className="btn btn-primary" to={`/projects/${p.id}?tab=live-preview`}><ExternalLink size={13} />{p.launch_label ?? 'Open Application'}</Link> : null}
          <Link className="btn" to={`/source?project=${p.id}`}><Code2 size={13} />View Source Code</Link>
          {hasTests && <Link className="btn" to={`/tests?project=${p.id}`}><FlaskConical size={13} />View Test Results</Link>}
          <Link className="btn" to={`/reports?project=${p.id}`}><FileText size={13} />View Evaluation Report</Link></> :
          <>{p.preview_url ? <Link className="btn btn-primary" to={`/projects/${p.id}?tab=live-preview`}><ExternalLink size={13} />{p.launch_label ?? 'Open Application'}</Link> : null}
          <Link className="btn" to={`/projects/${p.id}`}>{hasTests ? 'Open Overview' : 'Details'}</Link>
          {hasTests && <Link className="btn" to={`/tests?project=${p.id}`}><FlaskConical size={13} />View Test Results</Link>}</>}</div></div></Card> }

function PromptDOverview({ project }: { project: Project }) {
      const stages = [
        { id: 'D1', name: 'Live tool assessment', detail: 'Measures configured and reachable tools; distinguishes verified, unavailable, unauthorized, and mock-only access.', command: 'python -m devpilot tools' },
        { id: 'D2', name: 'Website workflow', detail: 'Reads a DOCX spec, plans and checks site edits, then prepares a local branch and draft PR when GitHub access permits.', command: 'python -m devpilot website' },
        { id: 'D3', name: 'Weather forecasting', detail: 'Demonstrates synthetic forecasts, chronological evaluation, and input-error handling.', command: 'python -m devpilot weather' },
        { id: 'D4', name: 'Document-grounded RAG', detail: 'Answers from authorized, in-force policy documents with verified citations; abstains when evidence is missing.', command: 'python -m devpilot rag' },
        { id: 'D5', name: 'Safe change requests', detail: 'Analyzes, plans, edits, tests, and repairs in a confined project copy; rollback is tested. Live changes require an OpenAI API key.', command: 'python -m devpilot change --demo' },
      ]
      return <div className="mt-5 space-y-5">
        <div className="flex flex-wrap gap-1.5">{project.stack.map(s => <span key={s} className="text-[11px] bg-slate-100 px-2 py-0.5 rounded">{s}</span>)}</div>
        <p className="text-sm text-muted">{project.import_note}</p>
        <div><H title="DevPilot stages" sub="Five independently invokable workflows. The dashboard documents them; it does not trigger tool probes, file edits, or remote actions." />
          <div className="grid md:grid-cols-2 gap-3">{stages.map(s => <Card key={s.id} className="p-4">
            <div className="flex items-center gap-2"><span className="rounded bg-soft text-brand px-2 py-0.5 text-xs font-semibold">{s.id}</span><h3 className="font-medium text-sm">{s.name}</h3></div>
            <p className="text-sm text-muted mt-2">{s.detail}</p><code className="block text-xs bg-slate-50 rounded p-2 mt-3 break-all">{s.command}</code>
          </Card>)}</div>
        </div>
        <Card className="p-4"><H title="Test evidence" sub="The local unittest suite was run and its output is available in the test results view." />
          <div className="flex flex-wrap gap-2"><Link className="btn btn-primary" to="/tests?project=prompt-d-explicit"><FlaskConical size={13} />View 23 recorded tests</Link>
            <span className="text-xs text-muted self-center">Live OpenAI, Drive, and GitHub access depends on local credentials; mock and offline behavior is explicitly labelled.</span></div>
        </Card>
      </div>
}

const SHORT: Record<string, string> = { 'prompt-a': 'Prompt A', 'prompt-b': 'Prompt B', 'inventory': 'Inventory', 'appointment-booking': 'Appointments', 'expense-system': 'Expenses', 'support-ticket-system': 'Support tickets', 'prompt-c-rag': 'Prompt C', 'prompt-d-explicit': 'Prompt D' }
/** One row of the live-applications card: checks the app's address from the browser and offers a launch link. */
function LiveAppRow({ p }: { p: Project }) {
  const [up, setUp] = useState<boolean | null>(null)
  useEffect(() => { if (!p.preview_url) return; setUp(null)
    fetch(p.preview_url, { mode: 'no-cors' }).then(() => setUp(true)).catch(() => setUp(false)) }, [p.preview_url])
  return <div className="flex flex-wrap items-center gap-3 justify-between py-2.5 border-t border-line first:border-0">
    <div className="min-w-0"><div className="text-sm font-medium">{SHORT[p.id] ?? p.name}</div>
      <div className="text-xs text-muted break-all">{up === null ? 'Checking…' : up ? <>Running at <code>{p.preview_url}</code></> : <>Not reachable at <code>{p.preview_url}</code>. Start it as described in the workspace's Live Preview tab.</>}</div></div>
    <div className="flex gap-2 items-center shrink-0"><span className={`text-[11px] px-2 py-0.5 rounded-full ${up === null ? 'bg-slate-100 text-muted' : up ? 'bg-green-50 text-ok' : 'bg-red-50 text-err'}`}>{up === null ? 'checking' : up ? 'running' : 'stopped'}</span>
      {up && <a className="btn btn-primary" href={p.preview_url ?? '#'} target="_blank" rel="noreferrer"><ExternalLink size={13} />{p.launch_label ?? 'Launch'}</a>}</div>
  </div>
}

export function Overview() {
  const o = useApi<Overview>('/api/overview'); const ps = useApi<Project[]>('/api/projects')
  if (!o.data) return <Loading error={o.error} />
  const d = o.data
  const live = (ps.data ?? []).filter(p => p.preview_url && p.status === 'built')
  return <div className="space-y-6">
    <div className="text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2">{d.data_note}</div>
    <Card className="p-4"><H title="Live applications" sub="Each project's running app, checked from this page. Start a stopped app with the command shown in its workspace." />
      {live.length === 0 && <p className="text-sm text-muted">No live applications are configured.</p>}
      {live.map(p => <LiveAppRow key={p.id} p={p} />)}</Card>
    <div><H title="Implemented projects & status" right={<Link to="/gallery" className="btn">Open Project Gallery</Link>} />
      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">{ps.data?.filter(p => p.status === 'built').map(p => <ProjectCard key={p.id} p={p} />)}</div></div></div> }

export function Gallery() {
  const ps = useApi<Project[]>('/api/projects'); const [sp] = useSearchParams(); const q = (sp.get('q') ?? '').toLowerCase()
  if (!ps.data) return <Loading error={ps.error} />
  const list = ps.data.filter(p => !q || (p.name + p.description + p.stack.join(' ') + (p.category ?? '') + (p.client ?? '')).toLowerCase().includes(q))
  return <div><H title="Project Gallery" sub="Prompts A and B have full evaluation workspaces; Prompts C and D include project overviews and recorded test evidence. Other entries are clearly labelled placeholders." />
    {!list.length && <p className="text-sm text-muted">No projects match “{q}”.</p>}
    <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{list.map(p => <ProjectCard key={p.id} p={p} />)}</div></div> }

const TABS_A = ['Overview', 'Requirements', 'Repository Analysis', 'Tool Selection', 'Implementation Plan', 'Code Changes', 'Live Preview', 'Tests', 'GitHub / Pull Request', 'Final Report'] as const
const TABS_B = ['Overview', 'Requirements', 'Repository Analysis', 'Tool Selection', 'Data & Method', 'Implementation Plan', 'Code Changes', 'Live Preview', 'Tests', 'Evaluation', 'GitHub / Pull Request', 'Final Report'] as const
const slug = (t: string) => t.toLowerCase().replace(/[^a-z]+/g, '-').replace(/-$/, '')
export function Workspace() {
  const { id = '' } = useParams(); const [sp, setSp] = useSearchParams(); const nav = useNavigate()
  const p = useApi<Project>(`/api/projects/${id}`); const rawTab = sp.get('tab') ?? 'overview'; const tab = rawTab === 'preview' ? 'live-preview' : rawTab
  const real = REAL.includes(id)
  const diff = useApi<DiffFile[]>(real ? `/api/projects/${id}/diff` : null); const sum = useApi<Record<string, number | boolean>>(real ? `/api/projects/${id}/summary` : null)
  if (!p.data) return <Loading error={p.error} />
  const pr = p.data
  if (!real) return <div><button className="btn mb-4" onClick={() => nav('/gallery')}>← Gallery</button><Card className="p-8"><div className="flex gap-2 mb-2"><Pill s={pr.status} /><KindBadge kind={pr.data_kind} /></div><h2 className="text-lg font-semibold">{pr.name}</h2><p className="text-sm text-muted mt-2">{pr.description}</p>
    {id === 'prompt-c-rag' ? <><div className="flex gap-1.5 mt-3 flex-wrap">{pr.stack.map(s => <span key={s} className="text-[11px] bg-slate-100 px-2 py-0.5 rounded">{s}</span>)}</div><p className="text-sm mt-4">{pr.import_note}</p><Link className="btn mt-4" to={`/tests?project=${id}`}><FlaskConical size={13} />View recorded test results</Link></> :
      id === 'prompt-d-explicit' ? <PromptDOverview project={pr} /> :
      <p className="text-sm mt-4">This project has no recorded agent run, tests, or source yet, so no workspace data is shown rather than inventing any.</p>}</Card></div>
  const TABS = id === 'prompt-b' ? TABS_B : TABS_A; const B = id === 'prompt-b'
  return <div>
    <div className="flex items-start justify-between mb-3 gap-3 flex-wrap"><div><Link to="/gallery" className="text-xs text-muted hover:text-brand">← Project Gallery</Link><h2 className="text-xl font-semibold">{pr.name}</h2>{pr.client && <div className="text-xs text-muted">Client: {pr.client} · {pr.category}</div>}</div><div className="flex gap-2 flex-wrap"><Pill s={pr.status} /><KindBadge kind={pr.data_kind} />{pr.synthetic && <span className="text-[11px] font-medium px-2 py-0.5 rounded-full border bg-amber-50 text-warn border-amber-200">Synthetic dataset</span>}</div></div>
    <div className="flex gap-2 mb-4 flex-wrap"><span className="text-xs text-muted self-center">Switch project:</span>{REAL.filter(x => x !== id).map(x => <Link key={x} className="btn" to={`/projects/${x}`}>{PROJECT_NAMES[x]}</Link>)}</div>
    {pr.import_note && <div className="text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2 mb-4"><strong>Repository status:</strong> {pr.import_note}.</div>}
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-line mb-5">{TABS.map(t => <button key={t} role="tab" aria-selected={tab === slug(t)} onClick={() => setSp({ tab: slug(t) })}
      className={`px-3 py-2 text-sm whitespace-nowrap border-b-2 -mb-px ${tab === slug(t) ? 'border-brand text-brand font-medium' : 'border-transparent text-muted hover:text-ink'}`}>{t}</button>)}</div>
    {tab === 'overview' && <div className="space-y-4"><Card className="p-5"><p className="text-sm">{pr.description}</p><div className="flex gap-1.5 mt-3 flex-wrap">{pr.stack.map(s => <span key={s} className="text-[11px] bg-slate-100 px-2 py-0.5 rounded">{s}</span>)}</div>
        {B && <div className="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"><strong>Educational demonstration using synthetic observations – not a real weather forecast.</strong></div>}
        {B && <div className="flex gap-2 mt-3 flex-wrap"><Link className="btn btn-primary" to={`/projects/${id}?tab=live-preview`}><ExternalLink size={13} />Launch Weather Demo</Link><Link className="btn" to={`/projects/${id}?tab=evaluation`}><FlaskConical size={13} />Weather Evaluation</Link><Link className="btn" to={`/source?project=${id}`}><FolderTree size={13} />Source Explorer</Link></div>}</Card>
      {sum.data && <div className="grid grid-cols-2 md:grid-cols-5 gap-3"><Stat label="Tests passed" value={sum.data.tests_passed as number} tone="text-ok" /><Stat label="Files added" value={sum.data.files_added as number} /><Stat label="Files modified" value={sum.data.files_modified as number} />
        {B && <Stat label="Held-out MAE (°C)" value={(sum.data.overall_mae as number).toFixed(3)} note={`${sum.data.heldout_forecasts} forecasts, synthetic data`} />}
        <Stat label="Pushed to GitHub" value={sum.data.pushed ? 'Yes' : 'No'} tone="text-warn" note="Draft PR pending" /></div>}
      <TimelineTab pid={id} /></div>}
    {tab === 'requirements' && <RequirementsTab pid={id} />}{tab === 'repository-analysis' && <RepoTab pid={id} />}{tab === 'tool-selection' && <ToolsTab pid={id} />}{tab === 'data-method' && B && <DataMethodTab pid={id} />}{tab === 'implementation-plan' && <PlanTab pid={id} />}
    {tab === 'code-changes' && <div><H title="Code changes" sub="Unified diff of original → modified" />{diff.data?.map(d => <DiffViewer key={d.path} d={d} />)}</div>}
    {tab === 'live-preview' ? <LivePreview pid={id} /> : null}{tab === 'tests' && <TestsTab pid={id} />}{tab === 'evaluation' && B && <Evaluation pid={id} />}{tab === 'github-pull-request' && <GitTab pid={id} />}{tab === 'final-report' && <Report pid={id} />}</div> }

export const AgentWorkspace = () => { const [pid] = useProjectParam(); const i = useApi<{ id: string; name: string; role: string; configured: boolean; env: string }[]>('/api/integrations'); const s = useApi<{ message: string; mode: string }>('/api/agent/status')
  return <div className="space-y-6"><ProjectSwitcher /><TimelineTab pid={pid} />
    <div><H title="Agent integrations" sub={s.data?.message} />
      <div className="grid md:grid-cols-4 gap-3">{i.data?.map(x => <Card key={x.id} className="p-4"><div className="font-medium text-sm">{x.name}</div><div className="text-xs text-muted mb-2">{x.role}</div><Pill s={x.configured ? 'completed' : 'pending'} /><div className="text-[11px] text-muted mt-2 font-mono">{x.env}</div></Card>)}</div>
      <p className="text-xs text-muted mt-3">Integration layer is a structure only: the Prompt A and Prompt B evidence was produced in a Claude Code session, not by these providers. No paid API is needed to browse the dashboard.</p></div></div> }
export const SourcePage = () => { const [pid] = useProjectParam(); return <div><ProjectSwitcher /><H title="Source Explorer" sub={`${PROJECT_NAMES[pid]} — original/modified/diff views of the real repository.`} /><Explorer pid={pid} /></div> }
export const TestsPage = () => { const [pid] = useProjectParam(); return <div><ProjectSwitcher includePromptC includePromptD /><TestsTab pid={pid} /></div> }
export const ReportsPage = () => { const [pid] = useProjectParam(); const [view, setView] = useState<'evaluation' | 'report'>('evaluation')
  return <div><ProjectSwitcher /><H title="Evaluation Reports" sub={PROJECT_NAMES[pid]} />
    {pid === 'prompt-b' && <div role="tablist" className="inline-flex rounded-lg border border-line bg-white p-0.5 mb-4">{([['evaluation', 'Weather Evaluation dashboard'], ['report', 'Final report']] as const).map(([k, l]) => <button key={k} role="tab" aria-selected={view === k} onClick={() => setView(k)} className={`px-3 py-1.5 text-sm rounded-md ${view === k ? 'bg-soft text-brand font-medium' : 'text-muted hover:text-ink'}`}>{l}</button>)}</div>}
    {pid === 'prompt-b' && view === 'evaluation' ? <Evaluation pid={pid} /> : <Report pid={pid} />}</div> }
export const GithubPage = () => { const [pid] = useProjectParam(); return <div><ProjectSwitcher /><GitTab pid={pid} /></div> }
export const SettingsPage = () => { const i = useApi<{ id: string; name: string; configured: boolean; env: string }[]>('/api/integrations'); const c = useApi<{ url: string; previews: Record<string, string> }>('/api/preview-config')
  return <div><H title="Settings" sub="Secrets are read from environment variables on the backend only and are never sent to the browser." />
    <Card className="divide-y divide-line">{i.data?.map(x => <div key={x.id} className="flex justify-between p-3 text-sm"><span>{x.name} <code className="text-xs text-muted ml-1">{x.env}</code></span><Pill s={x.configured ? 'completed' : 'pending'} /></div>)}
      <div className="flex justify-between p-3 text-sm"><span>Prompt A preview URL <code className="text-xs text-muted ml-1">PROMPT_A_PREVIEW_URL</code></span><code className="text-xs">{c.data?.previews?.['prompt-a'] ?? c.data?.url}</code></div>
      {Object.entries(c.data?.previews ?? {}).filter(([k]) => k !== 'prompt-a').map(([k, v]) => <div key={k} className="flex justify-between gap-3 p-3 text-sm"><span>{k} preview URL</span><code className="text-xs break-all">{v}</code></div>)}</Card></div> }
