import { useEffect, useState } from 'react'
import { RefreshCw, ExternalLink, Maximize2, Minimize2, Monitor, Smartphone } from 'lucide-react'
import { useApi } from '../services/hooks'
import { API, abs } from '../services/api'
import { Card, Loading } from './ui'

interface Shot { name: string; label: string; viewport: string }
interface PreviewCfg { url: string; title: string; start_hint: string }
/** Embeds the project's REAL running application (iframe). Shared by every evaluation project. */
export default function LivePreview({ pid = 'prompt-a' }: { pid?: string }) {
  const cfg = useApi<PreviewCfg>(`/api/projects/${pid}/preview`); const shots = useApi<Shot[]>(`/api/projects/${pid}/screenshots`)
  const [key, setKey] = useState(0); const [full, setFull] = useState(false); const [w, setW] = useState<'desktop' | 'mobile'>('desktop'); const [up, setUp] = useState<boolean | null>(null)
  const url = cfg.data?.url
  useEffect(() => { if (!url) return; setUp(null)
    fetch(url, { mode: 'no-cors' }).then(() => setUp(true)).catch(() => setUp(false)) }, [url, key])
  useEffect(() => { if (!full) return; const h = (e: KeyboardEvent) => e.key === 'Escape' && setFull(false); window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h) }, [full])
  if (!cfg.data || !url) return <Loading error={cfg.error} />
  return (<div>
    <div className={full ? 'fixed inset-0 z-50 bg-white flex flex-col' : ''}>
      <div className="flex items-center gap-2 p-2 border border-line rounded-t-xl bg-slate-50 flex-wrap">
        <code className="flex-1 min-w-[10rem] text-xs bg-white border border-line rounded-md px-2 py-1 truncate" aria-label="Local preview URL">{url}</code>
        <span className={`text-[11px] px-2 py-0.5 rounded-full ${up === null ? 'bg-slate-100 text-muted' : up ? 'bg-green-50 text-ok' : 'bg-red-50 text-err'}`}>{up === null ? 'checking…' : up ? 'running' : 'not reachable'}</span>
        <button className="btn" onClick={() => setW('desktop')} aria-pressed={w === 'desktop'} aria-label="Desktop width"><Monitor size={14} /></button>
        <button className="btn" onClick={() => setW('mobile')} aria-pressed={w === 'mobile'} aria-label="Mobile width"><Smartphone size={14} /></button>
        <button className="btn" onClick={() => setKey(k => k + 1)}><RefreshCw size={14} />Refresh</button>
        <a className="btn" href={url} target="_blank" rel="noreferrer"><ExternalLink size={14} />New tab</a>
        <button className="btn" onClick={() => setFull(!full)}>{full ? <Minimize2 size={14} /> : <Maximize2 size={14} />}{full ? 'Exit' : 'Full screen'}</button>
      </div>
      {up === false ? <Card className="rounded-t-none p-8 text-center"><p className="font-medium">Preview server is not reachable at {url}</p>
        <p className="text-sm text-muted mt-2">The {cfg.data.title} runs as a separate process. Start it with <code className="bg-slate-100 px-1 rounded break-all">{cfg.data.start_hint}</code>, then press Refresh.</p></Card> :
        <div className={`border border-t-0 border-line rounded-b-xl bg-slate-100 flex justify-center overflow-auto ${full ? 'flex-1' : 'h-[720px]'}`}>
          <iframe key={key} title={`${cfg.data.title}`} src={url} sandbox={pid === 'prompt-a' ? undefined : 'allow-scripts allow-same-origin allow-forms allow-popups'} className="bg-white h-full border-0" style={{ width: w === 'mobile' ? 375 : '100%' }} /></div>}
    </div>
    {shots.data && shots.data.length > 0 && <>
      <h3 className="font-semibold mt-6 mb-2 text-sm">Recorded verification screenshots <span className="text-xs text-muted font-normal">(real Playwright captures from the test run — the live preview above is the running application)</span></h3>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">{shots.data.map(s => (
        <a key={s.name} href={`${API}/api/projects/${pid}/screenshot/${s.name}`} target="_blank" rel="noreferrer" className="card p-2 block hover:shadow-md">
          <div className="h-40 overflow-hidden rounded bg-slate-50"><img src={abs(`/api/projects/${pid}/screenshot/${s.name}`)} alt={s.label} className="w-full object-top object-cover" /></div><p className="text-xs mt-1.5">{s.label}</p></a>))}</div></>}
  </div>)
}
