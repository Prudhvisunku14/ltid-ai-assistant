import { useState } from 'react'
import { ChevronRight, ChevronDown, FileText, Folder } from 'lucide-react'
import type { Node } from '../services/types'
const dot: Record<string, string> = { added: 'bg-ok', modified: 'bg-warn' }
const hasChange = (n: Node): boolean => n.type === 'file' ? !!n.change && n.change !== 'unchanged' : n.children.some(hasChange)
function Item({ n, depth, sel, onSel, q, changedOnly }: { n: Node; depth: number; sel: string; onSel: (p: string) => void; q: string; changedOnly: boolean }) {
  const [open, setOpen] = useState(depth < 2)
  if (changedOnly && !hasChange(n)) return null
  if (n.type === 'file') {
    if (q && !n.path.toLowerCase().includes(q)) return null
    return <button onClick={() => onSel(n.path)} style={{ paddingLeft: 10 + depth * 14 }} className={`w-full flex items-center gap-1.5 py-1 text-[13px] text-left rounded ${sel === n.path ? 'bg-soft text-brand' : 'hover:bg-slate-50'}`}>
      <FileText size={14} className="text-muted shrink-0" /><span className="truncate">{n.name}</span>{n.change && dot[n.change] && <span title={n.change} className={`ml-auto mr-2 w-1.5 h-1.5 rounded-full ${dot[n.change]}`} />}</button>
  }
  const show = q || changedOnly ? true : open
  return <div>{n.name !== 'source' && <button onClick={() => setOpen(!open)} style={{ paddingLeft: 4 + depth * 14 }} className="w-full flex items-center gap-1 py-1 text-[13px] text-left hover:bg-slate-50 rounded">
    {show ? <ChevronDown size={14} /> : <ChevronRight size={14} />}<Folder size={14} className="text-brand" />{n.name}</button>}
    {show && n.children.map(c => <Item key={c.path} n={c} depth={n.name === 'source' ? 0 : depth + 1} sel={sel} onSel={onSel} q={q} changedOnly={changedOnly} />)}</div>
}
export default function FileTree({ root, sel, onSel, changedOnly = false }: { root: Node; sel: string; onSel: (p: string) => void; changedOnly?: boolean }) {
  const [q, setQ] = useState('')
  return <div className="card p-2 h-full overflow-auto"><input value={q} onChange={e => setQ(e.target.value.toLowerCase())} placeholder="Search files…" aria-label="Search files" className="w-full mb-2 px-2.5 py-1.5 text-sm border border-line rounded-lg outline-none focus:border-brand" />
    <Item n={root} depth={0} sel={sel} onSel={onSel} q={q} changedOnly={changedOnly} />
    <p className="text-[11px] text-muted px-2 pt-3"><span className="inline-block w-1.5 h-1.5 rounded-full bg-ok mr-1" />added <span className="inline-block w-1.5 h-1.5 rounded-full bg-warn mx-1 ml-3" />modified</p></div>
}
