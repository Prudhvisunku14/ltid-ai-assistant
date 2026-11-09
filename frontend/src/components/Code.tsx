import { useMemo, useState } from 'react'
import hljs from 'highlight.js/lib/core'
import js from 'highlight.js/lib/languages/javascript'; import css from 'highlight.js/lib/languages/css'; import xml from 'highlight.js/lib/languages/xml'
import py from 'highlight.js/lib/languages/python'; import md from 'highlight.js/lib/languages/markdown'; import json from 'highlight.js/lib/languages/json'
import { Copy, Download, Check } from 'lucide-react'
import { API } from '../services/api'
import type { DiffFile } from '../services/types'
;[['javascript', js], ['css', css], ['xml', xml], ['python', py], ['markdown', md], ['json', json]].forEach(([n, l]: any) => hljs.registerLanguage(n, l))

export function CodeViewer({ path, language, content, pid = 'prompt-a' }: { path: string; language: string; content: string; pid?: string }) {
  const [copied, setCopied] = useState(false)
  const lines = useMemo(() => {
    const html = hljs.getLanguage(language) ? hljs.highlight(content, { language, ignoreIllegals: true }).value : content.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]!))
    return html.split('\n')
  }, [content, language])
  return (
    <div className="card overflow-hidden flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-line bg-slate-50">
        <div className="text-xs text-muted font-mono truncate">{path.split('/').map((p, i, a) => <span key={i}>{p}{i < a.length - 1 && <span className="mx-1">›</span>}</span>)}</div>
        <div className="flex gap-2 shrink-0">
          <button className="btn" onClick={() => { navigator.clipboard?.writeText(content); setCopied(true); setTimeout(() => setCopied(false), 1500) }}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? 'Copied' : 'Copy'}</button>
          <a className="btn" href={`${API}/api/projects/${pid}/raw?path=${encodeURIComponent(path)}`}><Download size={14} />Download</a>
        </div>
      </div>
      <div className="overflow-auto flex-1 font-mono text-[12.5px] leading-6 py-2">
        {lines.map((l, i) => (<div key={i} className="flex hover:bg-slate-50"><span className="w-12 shrink-0 text-right pr-3 text-slate-400 select-none">{i + 1}</span><code className="whitespace-pre pr-4" dangerouslySetInnerHTML={{ __html: l || ' ' }} /></div>))}
      </div>
    </div>)
}

export function DiffViewer({ d }: { d: DiffFile }) {
  const lines = d.diff.split('\n')
  return (
    <div className="card overflow-hidden mb-3">
      <div className="flex items-center justify-between px-3 py-2 border-b border-line bg-slate-50 text-sm">
        <span className="font-mono">{d.path}</span>
        <span className="text-xs"><span className="text-ok font-medium">+{d.additions}</span> <span className="text-err font-medium ml-1">−{d.deletions}</span> <span className="ml-2 text-muted capitalize">{d.status}</span></span>
      </div>
      <div className="overflow-auto max-h-[420px] font-mono text-[12px] leading-5">
        {lines.map((l, i) => { const c = l.startsWith('+') && !l.startsWith('+++') ? 'bg-green-50 text-green-900' : l.startsWith('-') && !l.startsWith('---') ? 'bg-red-50 text-red-900' : l.startsWith('@@') ? 'bg-soft text-brand' : 'text-slate-600'
          return <div key={i} className={`px-3 whitespace-pre ${c}`}>{l || ' '}</div> })}
      </div>
    </div>)
}
