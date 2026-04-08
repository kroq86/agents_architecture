export type DebugMode = 'sse' | 'polling' | 'both'

export interface ChatAsyncAccepted {
  run_id: string
  request_id: string
  session_id: string
  trace_id: string
  status: string
}

export interface RunRead {
  id: string
  status: string
  request_id: string
  session_id: string
  trace_id: string
  task_type: string
  created_at: string
  finished_at: string | null
  messages: Array<{ id: string; role: string; content: string; created_at: string }>
  tool_calls: Array<{ id: string; tool_name: string; tool_input: Record<string, unknown>; tool_output: Record<string, unknown>; created_at: string }>
  transcript_events: Array<{ id: string; seq: number; kind: string; payload: Record<string, unknown>; created_at: string }>
}

export interface TimelineItem {
  ts: string
  kind: string
  summary: string
  status?: string
}
