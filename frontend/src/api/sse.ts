import { apiBaseUrl, apiKey } from './client'
import type { TimelineItem } from './types'

export async function streamChat(message: string, onItem: (i: TimelineItem) => void): Promise<void> {
  const r = await fetch(`${apiBaseUrl()}/chat`, {
    method: 'POST',
    headers: apiKey() ? { 'X-API-Key': apiKey()!, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!r.ok || !r.body) throw new Error(await r.text())

  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const p of parts) {
      const e = p.split('\n').find((l) => l.startsWith('event: '))?.slice(7) ?? 'message'
      const d = p.split('\n').find((l) => l.startsWith('data: '))?.slice(6) ?? ''
      onItem({ ts: new Date().toISOString(), kind: e, summary: d })
    }
  }
}
