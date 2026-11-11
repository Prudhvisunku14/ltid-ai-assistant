import { useEffect, useState } from 'react'
import { useApi } from '../services/hooks'
import { API } from '../services/api'
import type { Node, FileContent, DiffFile } from '../services/types'
import FileTree from './FileTree'; import { CodeViewer, DiffViewer } from './Code'; import { Loading, Pill } from './ui'

const FIRST: Record<string, string> = { 'prompt-a': 'index.html', 'prompt-b': 'weather_app/service.py', 'inventory': 'app/db.py', 'appointment-booking': 'app/booking.py', 'expense-system': 'app/service.py', 'support-ticket-system': 'app/main.py', 'docchange': 'monitor/differ.py', 'prompt-c-rag': 'prompt-c-rag/rag_app/answer.py' }
const NOTE: Record<string, string> = { 'prompt-a': 'Source: modified Prompt A repository (imported ZIP + agent changes)', 'prompt-b': 'Source: modified Prompt B repository (imported ZIP snapshot = upstream main a7022f3, plus agent changes)', 'inventory': 'Source: Inventory repository (local git, 5 commits; diff is against the initial skeleton commit 65e4e4c)', 'appointment-booking': 'Source: uploaded folder (no baseline snapshot, so no changes are marked)', 'expense-system': 'Source: uploaded folder (no baseline snapshot, so no changes are marked)', 'support-ticket-system': 'Source: uploaded folder (no baseline snapshot, so no changes are marked)', 'docchange': 'Source: uploaded folder (no baseline snapshot, so no changes are marked)', 'prompt-c-rag': 'Source: supplied RAG project (prompt-c-rag/, its own git repo) plus the web interface added by this integration (web_demo/); no baseline snapshot, so no changes are marked' }

export default function Explorer({ pid = 'prompt-a' }: { pid?: string }) {
  const tree = useApi<Node>(`/api/projects/${pid}/tree`)
  const diff = useApi<DiffFile[]>(`/api/projects/${pid}/diff`)
  const [sel, setSel] = useState(FIRST[pid] ?? 'README.md'); const [mode, setMode] = useState<'current' | 'original' | 'diff'>('current'); const [changed, setChanged] = useState(false)
  useEffect(() => { setSel(FIRST[pid] ?? 'README.md'); setMode('current') }, [pid])
  const file = useApi<FileContent>(`/api/projects/${pid}/file?path=${encodeURIComponent(sel)}`)
  if (!tree.data) return <Loading error={tree.error} />
  const d = diff.data?.find(x => x.path === sel); const deleted = diff.data?.filter(x => x.status === 'deleted') ?? []
  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3 text-sm items-center">
        {diff.data && <>
          <Pill s="added" /> <span>{diff.data.filter(x => x.status === 'added').length} files</span>
          <Pill s="modified" /> <span>{diff.data.filter(x => x.status === 'modified').length} files</span>
          <Pill s="deleted" /> <span>{deleted.length} files{deleted.length > 0 && <>: {deleted.map(x => x.path).join(', ')}</>}</span></>}
        <label className="inline-flex items-center gap-1.5 text-xs text-muted ml-2"><input type="checkbox" checked={changed} onChange={e => setChanged(e.target.checked)} />Changed files only</label>
        <span className="ml-auto text-xs text-muted">{NOTE[pid]}</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-4 md:h-[640px]">
        <div className="h-64 md:h-full"><FileTree root={tree.data} sel={sel} onSel={p => { setSel(p); setMode('current') }} changedOnly={changed} /></div>
        <div className="flex flex-col min-h-0 gap-2">
          <div className="flex gap-1.5">{(['current', 'original', 'diff'] as const).map(m =>
            <button key={m} onClick={() => setMode(m)} className={`btn capitalize ${mode === m ? 'btn-primary' : ''}`}>{m === 'current' ? 'Modified' : m}</button>)}</div>
          <div className="flex-1 min-h-0 overflow-auto h-[520px] md:h-auto">
            {!file.data ? <Loading error={file.error} /> :
              file.data.binary ? <div className="card p-5 text-sm text-muted">Binary file. <a className="text-brand underline" href={`${API}/api/projects/${pid}/raw?path=${encodeURIComponent(sel)}`}>Download</a></div> :
              mode === 'diff' ? (d ? <DiffViewer d={d} /> : <div className="card p-5 text-sm text-muted">No changes in this file (identical to original).</div>) :
              mode === 'original' ? (file.data.original == null ? <div className="card p-5 text-sm text-muted">This file did not exist in the original repository.</div> : <div className="h-full"><CodeViewer path={sel} language={file.data.language} content={file.data.original} pid={pid} /></div>) :
              <div className="h-full"><CodeViewer path={sel} language={file.data.language} content={file.data.content} pid={pid} /></div>}
          </div>
        </div>
      </div>
    </div>)
}
