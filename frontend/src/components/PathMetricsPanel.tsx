export function PathMetricsPanel({ rows }: { rows: Array<{ method: string; path: string; status: string; count: number }> }) {
  return <div className="panel"><h3>Request Paths</h3>{rows.map((r, i) => <div key={i}>{r.method} {r.path} {r.status} {'->'} {r.count}</div>)}</div>
}
