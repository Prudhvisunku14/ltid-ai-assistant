import { Fragment, ReactNode } from 'react'
import { Download, FileText } from 'lucide-react'
import { useApi } from '../services/hooks'
import { API } from '../services/api'
import { Loading, Card } from './ui'
const inline = (s: string): ReactNode[] => s.split(/(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_)/g).map((p, i) => p.startsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : p.startsWith('`') ? <code key={i} className="bg-slate-100 px-1 rounded text-[12px]">{p.slice(1, -1)}</code> : p.startsWith('_') && p.length > 2 ? <em key={i}>{p.slice(1, -1)}</em> : p)
const isSep = (l: string) => /^\|[\s:|-]+\|?$/.test(l.trim()) && l.includes('---')   // the |---|---| line under a table header
const cells = (l: string) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim())

export default function Report({ pid = 'prompt-a' }: { pid?: string }) {
  const r = useApi<{ markdown: string }>(`/api/projects/${pid}/report`)
  if (!r.data) return <Loading error={r.error} />
  const lines = r.data.markdown.split('\n'); const out: ReactNode[] = []
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i]
    if (l.startsWith('```')) { const buf: string[] = []; i++; while (i < lines.length && !lines[i].startsWith('```')) buf.push(lines[i++]); out.push(<pre key={i} className="text-xs font-mono bg-slate-50 border border-line rounded-lg p-3 my-2 overflow-x-auto">{buf.join('\n')}</pre>); continue }
    if (l.startsWith('|')) {                       // pipe table (header, separator, rows)
      const rows: string[][] = []; const start = i
      while (i < lines.length && lines[i].startsWith('|')) { if (!isSep(lines[i])) rows.push(cells(lines[i])); i++ }
      i--; const [head, ...body] = rows
      out.push(<div key={`t${start}`} className="overflow-x-auto my-3"><table className="w-full text-[13px] border border-line"><thead className="bg-slate-50 text-left text-muted"><tr>{head.map((h, k) => <th key={k} className="p-2 font-medium border-b border-line">{inline(h)}</th>)}</tr></thead>
        <tbody>{body.map((row, k) => <tr key={k} className="border-t border-line align-top">{row.map((c, j) => <td key={j} className="p-2 break-words">{inline(c)}</td>)}</tr>)}</tbody></table></div>); continue }
    out.push(
      l.startsWith('# ') ? <h1 key={i} className="text-2xl font-semibold mb-2">{l.slice(2)}</h1> :
      l.startsWith('### ') ? <h3 key={i} className="text-sm font-semibold mt-4 mb-1">{l.slice(4)}</h3> :
      l.startsWith('## ') ? <h2 key={i} className="text-base font-semibold mt-6 mb-2 pb-1 border-b border-line">{l.slice(3)}</h2> :
      /^\s*- /.test(l) ? <li key={i} className={`text-sm list-disc ml-5 py-0.5 ${l.startsWith('  ') ? 'ml-10' : ''}`}>{inline(l.replace(/^\s*- /, ''))}</li> :
      /^\d+\. /.test(l) ? <li key={i} className="text-sm list-decimal ml-5 py-0.5">{inline(l.replace(/^\d+\. /, ''))}</li> :
      l.trim() ? <p key={i} className="text-sm my-1">{inline(l)}</p> : <Fragment key={i} />)
  }
  return (<div>
    <div className="flex justify-end gap-2 mb-3 flex-wrap"><a className="btn btn-primary" href={`${API}/api/projects/${pid}/report/download`}><Download size={14} />Download report (.md)</a>
      {pid !== 'prompt-a' && <><a className="btn" href={`${API}/api/projects/${pid}/report/download.pdf`}><FileText size={14} />Download report (.pdf)</a><a className="btn" href={`${API}/api/projects/${pid}/evaluation/download`}><Download size={14} />Evaluation JSON</a></>}</div>
    <Card className="p-6 md:p-8 max-w-5xl">{out}</Card></div>)
}
