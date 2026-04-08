const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined

function headers(): HeadersInit {
  return API_KEY ? { 'X-API-Key': API_KEY, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

export async function postChatAsync(message: string) {
  const r = await fetch(`${BASE_URL}/chat/async`, { method: 'POST', headers: headers(), body: JSON.stringify({ message }) })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getRun(runId: string) {
  const r = await fetch(`${BASE_URL}/runs/${runId}`, { headers: API_KEY ? { 'X-API-Key': API_KEY } : {} })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getMetricsText() {
  const r = await fetch(`${BASE_URL}/metrics`)
  if (!r.ok) throw new Error(await r.text())
  return r.text()
}

export function apiBaseUrl() { return BASE_URL }
export function apiKey() { return API_KEY }
