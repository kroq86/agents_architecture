export function OutboxMetricsPanel({ stats }: { stats: { processed: number; dead: number; avg: number; p95: number } }) {
  return (
    <div className="panel">
      <h3>Outbox Metrics</h3>
      <div>processed_total: {stats.processed}</div>
      <div>dead_total: {stats.dead}</div>
      <div>avg_sla_seconds: {stats.avg.toFixed(3)}</div>
      <div>p95_sla_seconds: {stats.p95.toFixed(3)}</div>
    </div>
  )
}
