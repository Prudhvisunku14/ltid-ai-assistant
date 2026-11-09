import { useProjectParam, PROJECT_NAMES } from '../services/hooks'

/** Switch between the evaluation projects without leaving the current page (Source, Tests, Reports, GitHub, Agent). */
export default function ProjectSwitcher({ includePromptC = false, includePromptD = false }: { includePromptC?: boolean; includePromptD?: boolean }) {
  const [pid, set] = useProjectParam()
  const projects = Object.entries(PROJECT_NAMES).filter(([id]) =>
    (includePromptC || id !== 'prompt-c-rag') && (includePromptD || id !== 'prompt-d-explicit'))
  return <div role="tablist" aria-label="Evaluation project" className="inline-flex rounded-lg border border-line bg-white p-0.5 mb-4 flex-wrap">
    {projects.map(([id, name]) => <button key={id} role="tab" aria-selected={pid === id} onClick={() => set(id)}
      className={`px-3 py-1.5 text-sm rounded-md ${pid === id ? 'bg-soft text-brand font-medium' : 'text-muted hover:text-ink'}`}>{name}</button>)}</div>
}
