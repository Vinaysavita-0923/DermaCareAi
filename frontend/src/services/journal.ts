/**
 * Journal API calls, typed to match
 * backend/app/schemas/journal_schema.py exactly — including the closed
 * vocabulary of feeling tags, which the backend rejects anything
 * outside of.
 */
import { api } from './api'

// Must match ALLOWED_FEELING_TAGS in backend/app/schemas/journal_schema.py
export const ALLOWED_FEELING_TAGS = [
  'calm',
  'irritated',
  'dry',
  'oily',
  'breakout',
  'improving',
  'itchy',
  'normal',
] as const

export interface JournalEntry {
  id: number
  user_id: number
  entry_date: string // YYYY-MM-DD
  notes: string | null
  skin_feeling_tags: string[] | null
  created_at: string
}

export interface JournalEntryCreate {
  entry_date: string
  notes?: string
  skin_feeling_tags?: string[]
}

export interface JournalEntryUpdate {
  notes?: string
  skin_feeling_tags?: string[]
}

export async function listJournalEntries(limit = 50, offset = 0): Promise<JournalEntry[]> {
  const { data } = await api.get<JournalEntry[]>('/journal', { params: { limit, offset } })
  return data
}

export async function createJournalEntry(entry: JournalEntryCreate): Promise<JournalEntry> {
  const { data } = await api.post<JournalEntry>('/journal', entry)
  return data
}

export async function updateJournalEntry(
  id: number,
  update: JournalEntryUpdate,
): Promise<JournalEntry> {
  const { data } = await api.put<JournalEntry>(`/journal/${id}`, update)
  return data
}

export async function deleteJournalEntry(id: number): Promise<void> {
  await api.delete(`/journal/${id}`)
}
