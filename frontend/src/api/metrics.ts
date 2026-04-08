export type MetricSample = { name: string; labels: Record<string, string>; value: number }

export function parsePrometheus(text: string): MetricSample[] {
  const out: MetricSample[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const m = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{([^}]*)\})?\s+(-?[0-9.eE+]+)$/)
    if (!m) continue
    const labels: Record<string, string> = {}
    if (m[3]) {
      for (const kv of m[3].split(',')) {
        const mm = kv.match(/^([^=]+)="(.*)"$/)
        if (mm) labels[mm[1]] = mm[2]
      }
    }
    out.push({ name: m[1], labels, value: Number(m[4]) })
  }
  return out
}

export function outboxSla(samples: MetricSample) { return null }

export function computeOutboxStats(samples: MetricSample[]) {
  const processed = samples.filter((s) => s.name === 'app_outbox_events_processed_total').reduce((a, b) => a + b.value, 0)
  const dead = samples.filter((s) => s.name === 'app_outbox_events_dead_total').reduce((a, b) => a + b.value, 0)
  const sum = samples.filter((s) => s.name === 'app_outbox_pipeline_seconds_sum').reduce((a, b) => a + b.value, 0)
  const count = samples.filter((s) => s.name === 'app_outbox_pipeline_seconds_count').reduce((a, b) => a + b.value, 0)
  const avg = count > 0 ? sum / count : 0
  const buckets = samples.filter((s) => s.name === 'app_outbox_pipeline_seconds_bucket').sort((a, b) => Number(a.labels.le ?? Infinity) - Number(b.labels.le ?? Infinity))
  const target = count * 0.95
  let p95 = 0
  for (const b of buckets) {
    if (b.value >= target) { p95 = Number(b.labels.le === '+Inf' ? 0 : b.labels.le); break }
  }
  return { processed, dead, avg, p95 }
}

export function computePathTable(samples: MetricSample[]) {
  return samples
    .filter((s) => s.name === 'app_requests_total')
    .map((s) => ({ method: s.labels.method ?? '', path: s.labels.path ?? '', status: s.labels.status_code ?? '', count: s.value }))
    .sort((a, b) => b.count - a.count)
}
