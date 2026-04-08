import type { RunRead } from '../api/types'

export function RunInspectorPanel({ run }: { run: RunRead | null }) {
  return (
    <div className="panel">
      <h3>Run Inspector</h3>
      {!run ? <div className="small">No run loaded</div> : <>
        <div>Status: <b>{run.status}</b></div>
        <div>Run: <code>{run.id}</code></div>
        <div>Messages: {run.messages.length} | Tool calls: {run.tool_calls.length} | Transcript events: {run.transcript_events.length}</div>
        <pre>{JSON.stringify(run, null, 2)}</pre>
      </>}
    </div>
  )
}
