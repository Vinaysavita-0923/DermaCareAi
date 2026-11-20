/** Typed to match app/schemas/catalog_schema.py's ReportSummary exactly. */
import { api } from './api'

export interface RoutineCompletionStat {
  routine_id: number
  routine_type: 'morning' | 'night'
  days_logged: number
  days_completed: number
  completion_rate: number
}

export interface ReportSummary {
  period_days: number
  journal_entry_count: number
  feeling_tag_counts: Record<string, number>
  routine_completion: RoutineCompletionStat[]
  disclaimer: string
}

export async function getReportSummary(days = 30): Promise<ReportSummary> {
  const { data } = await api.get<ReportSummary>('/reports/summary', { params: { days } })
  return data
}
