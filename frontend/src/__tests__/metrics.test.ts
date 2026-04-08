import { describe, expect, it } from 'vitest'
import { computeOutboxStats, parsePrometheus } from '../api/metrics'

describe('metrics parser', () => {
  it('computes outbox stats', () => {
    const text = `app_outbox_events_processed_total{event_type="run_created"} 2\napp_outbox_events_dead_total{event_type="run_created"} 1\napp_outbox_pipeline_seconds_sum{event_type="run_created"} 8\napp_outbox_pipeline_seconds_count{event_type="run_created"} 4\napp_outbox_pipeline_seconds_bucket{event_type="run_created",le="1"} 1\napp_outbox_pipeline_seconds_bucket{event_type="run_created",le="2"} 4\n`
    const stats = computeOutboxStats(parsePrometheus(text))
    expect(stats.processed).toBe(2)
    expect(stats.dead).toBe(1)
    expect(stats.avg).toBe(2)
    expect(stats.p95).toBe(2)
  })
})
