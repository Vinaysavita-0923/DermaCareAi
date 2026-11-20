/** Typed to match backend/app/schemas/catalog_schema.py (routine shapes). */
import { api } from './api'

export type RoutineType = 'morning' | 'night'

export interface RoutineItem {
  id: number
  product_id: number | null
  step_order: number
  notes: string | null
}

export interface Routine {
  id: number
  routine_type: RoutineType
  created_at: string
  items: RoutineItem[]
}

export interface RoutineItemCreate {
  product_id?: number | null
  step_order: number
  notes?: string | null
}

export interface RoutineLog {
  id: number
  routine_id: number
  log_date: string
  completed: boolean
}

export async function listRoutines(): Promise<Routine[]> {
  const { data } = await api.get<Routine[]>('/routines')
  return data
}

export async function createRoutine(
  routine_type: RoutineType,
  items: RoutineItemCreate[],
): Promise<Routine> {
  const { data } = await api.post<Routine>('/routines', { routine_type, items })
  return data
}

export async function deleteRoutine(id: number): Promise<void> {
  await api.delete(`/routines/${id}`)
}

/** Upsert: logging the same routine + date again updates the existing log. */
export async function logRoutineDay(
  id: number,
  log_date: string,
  completed: boolean,
): Promise<RoutineLog> {
  const { data } = await api.post<RoutineLog>(`/routines/${id}/log`, { log_date, completed })
  return data
}
