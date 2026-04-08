import { useMemo, useState } from 'react'

export function RawMetricsPanel({ text }: { text: string }) {
  const [filter, setFilter] = useState('')
  const visible = useMemo(() => text.split('\n').filter((l) => !filter || l.includes(filter)).join('\n'), [text, filter])
  return <div className="panel"><h3>Raw /metrics</h3><input placeholder="filter" value={filter} onChange={(e) => setFilter(e.target.value)} /><pre>{visible}</pre></div>
}
