import { useEffect, useMemo, useState } from 'react'
import { getMetricsText } from './api/client'
import { computeOutboxStats, computePathTable, parsePrometheus } from './api/metrics'
import type { DebugMode, RunRead } from './api/types'
import { ChatDebugPanel } from './components/ChatDebugPanel'
import { OutboxMetricsPanel } from './components/OutboxMetricsPanel'
import { PathMetricsPanel } from './components/PathMetricsPanel'
import { RawMetricsPanel } from './components/RawMetricsPanel'
import { RunInspectorPanel } from './components/RunInspectorPanel'

export function App() {
  const [mode, setMode] = useState<DebugMode>('both')
  const [metricsText, setMetricsText] = useState('')
  const [run, setRun] = useState<RunRead | null>(null)

  useEffect(() => {
    let active = true
    const tick = async () => { if (!active) return; setMetricsText(await getMetricsText().catch(() => '')); setTimeout(tick, 1000) }
    tick()
    return () => { active = false }
  }, [])

  const samples = useMemo(() => parsePrometheus(metricsText), [metricsText])
  const outbox = useMemo(() => computeOutboxStats(samples), [samples])
  const pathRows = useMemo(() => computePathTable(samples), [samples])

  return (
    <div className="container">
      <div className="panel row"><b>Deep Debug Mode</b><select value={mode} onChange={(e) => setMode(e.target.value as DebugMode)}><option value="sse">SSE</option><option value="polling">Polling</option><option value="both">Both</option></select></div>
      <ChatDebugPanel mode={mode} onRun={setRun} />
      <RunInspectorPanel run={run} />
      <OutboxMetricsPanel stats={outbox} />
      <PathMetricsPanel rows={pathRows} />
      <RawMetricsPanel text={metricsText} />
    </div>
  )
}
