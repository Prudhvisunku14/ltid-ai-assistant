import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { get } from './api'
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null); const [error, setError] = useState<string | null>(null)
  useEffect(() => { if (!path) return; let off = false; setData(null); setError(null)
    get<T>(path).then(d => !off && setData(d)).catch(e => !off && setError(String(e.message ?? e))); return () => { off = true } }, [path])
  return { data, error, loading: !data && !error }
}
/** Which evaluation project the shared pages (Source, Tests, Reports, GitHub, Agent) show. Defaults to Prompt A. */
export function useProjectParam(): [string, (id: string) => void] {
  const [sp, setSp] = useSearchParams()
  const requested = sp.get('project')
  const id = requested && requested in PROJECT_NAMES ? requested : 'prompt-a'
  return [id, (p: string) => { const n = new URLSearchParams(sp); n.set('project', p); setSp(n) }]
}
export const PROJECT_NAMES: Record<string, string> = { 'prompt-a': 'Prompt A — Website Development', 'prompt-b': 'Prompt B — Weather Forecasting Demo', 'prompt-c-rag': 'LTID AI Competition – RAG', 'prompt-d-explicit': 'Prompt D — DevPilot Explainability', 'inventory': 'Inventory Management System', 'appointment-booking': 'Appointment Booking System', 'expense-system': 'Expense Management & Approval System', 'support-ticket-system': 'AI-Supported Support Ticket System', 'docchange': 'Document Change Monitoring System' }
