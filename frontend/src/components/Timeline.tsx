import { CheckCircle2, CircleDashed, AlertCircle, XCircle } from 'lucide-react'
import type { Step } from '../services/types'
import { Pill, fmt } from './ui'
const icon = { completed: <CheckCircle2 className="text-ok" size={20} />, partial: <AlertCircle className="text-warn" size={20} />, pending: <CircleDashed className="text-muted" size={20} />, blocked: <XCircle className="text-err" size={20} /> }
export default function Timeline({ steps }: { steps: Step[] }) {
  return <ol className="relative">{steps.map((s, i) => (
    <li key={s.n} className="flex gap-4 pb-5 last:pb-0">
      <div className="flex flex-col items-center"><div className="bg-white">{icon[s.status]}</div>{i < steps.length - 1 && <div className="w-px flex-1 bg-line mt-1" />}</div>
      <div className="flex-1 min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="font-medium text-sm">{s.n}. {s.title}</span><Pill s={s.status} /><span className="text-xs text-muted">{fmt(s.timestamp)}</span></div>
        <p className="text-sm text-muted mt-1">{s.description}</p>
        {s.output && <pre className="mt-2 text-xs font-mono bg-slate-50 border border-line rounded-lg p-2 whitespace-pre-wrap break-words">{s.output}</pre>}
        <p className="text-xs text-muted mt-1">Evidence: {s.evidence}</p></div></li>))}</ol>
}
