export const API = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8001'
export async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`)
  if (!r.ok) throw new Error(`${r.status} ${(await r.json().catch(() => ({}))).detail ?? r.statusText}`)
  return r.json()
}
export const abs = (p?: string | null) => (p ? (p.startsWith('http') ? p : `${API}${p}`) : '')
