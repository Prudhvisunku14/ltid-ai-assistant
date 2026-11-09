import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Images, Bot, FolderTree, FlaskConical, FileText, GitPullRequest, Settings, Search, Bell, Menu } from 'lucide-react'
import { useState } from 'react'
import { useApi } from '../services/hooks'
const nav = [['/', 'Overview', LayoutDashboard], ['/gallery', 'Project Gallery', Images], ['/agent', 'Agent Workspace', Bot], ['/source', 'Source Explorer', FolderTree], ['/tests', 'Test Results', FlaskConical], ['/reports', 'Evaluation Reports', FileText], ['/github', 'GitHub Activity', GitPullRequest], ['/settings', 'Settings', Settings]] as const
const titles: Record<string, string> = { '/': 'Overview', '/gallery': 'Project Gallery', '/agent': 'Agent Workspace', '/source': 'Source Explorer', '/tests': 'Test Results', '/reports': 'Evaluation Reports', '/github': 'GitHub Activity', '/settings': 'Settings' }
export default function AppLayout() {
  const loc = useLocation(); const go = useNavigate(); const [open, setOpen] = useState(false); const [q, setQ] = useState('')
  const agent = useApi<{ state: string; message: string }>('/api/agent/status')
  const title = titles[loc.pathname] ?? (loc.pathname.startsWith('/projects') ? 'Project Workspace' : 'LTID Assistant')
  return (<div className="min-h-screen flex">
    <aside className={`${open ? 'flex' : 'hidden'} lg:flex fixed lg:sticky top-0 h-screen z-40 w-60 shrink-0 flex-col bg-white border-r border-line p-4`}>
      <div className="flex items-center gap-2 px-2 mb-6"><div className="w-8 h-8 rounded-lg bg-brand text-white font-bold flex items-center justify-center text-sm">LT</div><div><div className="font-semibold leading-tight">LTID Assistant</div><div className="text-[11px] text-muted">AI software engineering</div></div></div>
      <nav className="space-y-0.5" aria-label="Main">{nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)}
        className={({ isActive }) => `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm ${isActive ? 'bg-soft text-brand font-medium' : 'text-muted hover:bg-slate-50 hover:text-ink'}`}><Icon size={17} />{label}</NavLink>)}</nav>
      <div className="mt-auto text-[11px] text-muted px-2">v1.0.0 · evidence viewer mode</div></aside>
    <div className="flex-1 min-w-0 flex flex-col">
      <header className="h-14 bg-white border-b border-line flex items-center gap-3 px-4 sticky top-0 z-30">
        <button className="lg:hidden btn" onClick={() => setOpen(!open)} aria-label="Toggle navigation"><Menu size={16} /></button>
        <h1 className="font-semibold">{title}</h1>
        <form className="ml-auto relative hidden sm:block" onSubmit={e => { e.preventDefault(); go(`/gallery?q=${encodeURIComponent(q)}`) }}>
          <Search size={15} className="absolute left-2.5 top-2.5 text-muted" /><input value={q} onChange={e => setQ(e.target.value)} aria-label="Search projects" placeholder="Search projects…" className="pl-8 pr-3 py-1.5 text-sm border border-line rounded-lg w-56 outline-none focus:border-brand" /></form>
        <span title={agent.data?.message} className="flex items-center gap-1.5 text-xs border border-line rounded-full px-2.5 py-1"><span className={`w-2 h-2 rounded-full ${agent.data ? 'bg-slate-400' : 'bg-err'}`} />Agent: {agent.data?.state ?? 'offline'}</span>
        <button className="btn" aria-label="Notifications" title="No notifications"><Bell size={15} /></button>
        <div className="w-8 h-8 rounded-full bg-soft text-brand text-xs font-semibold flex items-center justify-center" title="Evaluator">EV</div></header>
      <main className="p-6 max-w-[1400px] w-full mx-auto"><Outlet /></main></div></div>)
}
