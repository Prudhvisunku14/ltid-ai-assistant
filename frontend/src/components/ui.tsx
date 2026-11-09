import { ReactNode } from 'react'
import type { Kind } from '../services/types'
const kindStyle: Record<Kind, string> = { real: 'bg-green-50 text-ok border-green-200', imported: 'bg-soft text-brand border-indigo-200', mock: 'bg-amber-50 text-warn border-amber-200', pending: 'bg-slate-100 text-muted border-slate-200' }
const kindLabel: Record<Kind, string> = { real: 'Real execution data', imported: 'Imported source', mock: 'Demonstration data', pending: 'Pending' }
export const KindBadge = ({ kind }: { kind: Kind }) => <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${kindStyle[kind]}`}>{kindLabel[kind]}</span>
const st: Record<string, string> = { completed: 'bg-green-50 text-ok', passed: 'bg-green-50 text-ok', built: 'bg-green-50 text-ok', added: 'bg-green-50 text-ok', partial: 'bg-amber-50 text-warn', modified: 'bg-amber-50 text-warn', demo: 'bg-amber-50 text-warn', pending: 'bg-slate-100 text-muted', blocked: 'bg-red-50 text-err', failed: 'bg-red-50 text-err', deleted: 'bg-red-50 text-err', not_pushed: 'bg-slate-100 text-muted', not_created: 'bg-slate-100 text-muted' }
export const Pill = ({ s }: { s: string }) => <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${st[s] ?? 'bg-slate-100 text-muted'}`}>{s.replace('_', ' ')}</span>
export const Card = ({ children, className = '' }: { children: ReactNode; className?: string }) => <div className={`card ${className}`}>{children}</div>
export const H = ({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) => (
  <div className="flex items-start justify-between mb-4 gap-4"><div><h2 className="text-lg font-semibold">{title}</h2>{sub && <p className="text-sm text-muted mt-0.5">{sub}</p>}</div>{right}</div>)
export const Loading = ({ error }: { error?: string | null }) => error
  ? <Card className="p-5 text-sm text-err">Could not load data: {error}. Is the backend running? (see README)</Card>
  : <div className="text-sm text-muted p-4">Loading…</div>
export const fmt = (iso?: string | null) => iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—'
