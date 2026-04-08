import { useState } from 'react'
import { postChatAsync, getRun } from '../api/client'
import { streamChat } from '../api/sse'
import type { DebugMode, TimelineItem, RunRead } from '../api/types'

export function ChatDebugPanel({ mode, onRun }: { mode: DebugMode; onRun: (r: RunRead) => void }) {
  const [message, setMessage] = useState('deep debug ping')
  const [timeline, setTimeline] = useState<TimelineItem[]>([])

  async function run() {
    setTimeline([])
    const push = (i: TimelineItem) => setTimeline((prev) => [i, ...prev])
    if (mode === 'sse' || mode === 'both') {
      streamChat(message, push).catch((e) => push({ ts: new Date().toISOString(), kind: 'error', summary: String(e) }))
    }
    if (mode === 'polling' || mode === 'both') {
      const queued = await postChatAsync(message)
      push({ ts: new Date().toISOString(), kind: 'queued', summary: queued.run_id })
      for (let i = 0; i < 180; i += 1) {
        const run: RunRead = await getRun(queued.run_id)
        onRun(run)
        if (run.status === 'completed' || run.status === 'failed') {
          push({ ts: new Date().toISOString(), kind: 'run_status', summary: run.status })
          break
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
    }
  }

  return (
    <div className="panel">
      <h3>Chat Debug</h3>
      <div className="row"><input style={{ flex: 1 }} value={message} onChange={(e) => setMessage(e.target.value)} /><button onClick={run}>Send</button></div>
      <div className="timeline">{timeline.map((t, i) => <div key={i}><span className="small">{t.ts}</span> <b>{t.kind}</b> {t.summary}</div>)}</div>
    </div>
  )
}
