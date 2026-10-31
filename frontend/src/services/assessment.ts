/**
 * Calls for the dataset-backed assessment endpoints
 * (backend/app/api/assessment.py), typed to match
 * backend/app/schemas/profile_schema.py exactly.
 */
import { api } from './api'
import type { RecommendationResponse } from './recommendations'
import type { SkinProfile, SkinProfileUpdate } from './profile'

export interface AssessmentCreateResponse extends SkinProfile {
  history_id: number
  age_group_note: string | null
}

export interface AssessmentHistoryEntry {
  id: number
  age: number | null
  age_group: string | null
  skin_type: SkinProfile['skin_type']
  skin_subtype: string | null
  is_sensitive: boolean | null
  concerns: string[] | null
  sensitivity_notes: string | null
  created_at: string
}

export interface IngredientGuidance {
  internal_type: string
  ingredients: string
  concentrations: string
  effects: string[]
  treatment_profile: string
}

export interface ConcernGuidance {
  concern: string
  /** Keyed "Yes|<subtype>" or "No|<subtype>" — see backend docstring. */
  variants: Record<string, IngredientGuidance[]>
}

export interface PersonalizedProfile {
  skin_profile_summary: string
  dataset_skin_type: string
  subtypes_considered: string[]
  sensitivity_considered: string[]
  notes: string[]
  concerns_with_guidance: ConcernGuidance[]
  concerns_without_guidance: string[]
  disclaimer: string
}

export interface AssessmentRecommendations {
  personalized_profile: PersonalizedProfile
  products: RecommendationResponse
}

export async function submitAssessment(payload: SkinProfileUpdate): Promise<AssessmentCreateResponse> {
  const { data } = await api.post<AssessmentCreateResponse>('/assessment', payload)
  return data
}

export async function updateAssessment(payload: SkinProfileUpdate): Promise<SkinProfile> {
  const { data } = await api.put<SkinProfile>('/assessment/me', payload)
  return data
}

export async function getMyAssessment(): Promise<SkinProfile | null> {
  try {
    const { data } = await api.get<SkinProfile>('/assessment/me')
    return data
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 404) return null
    throw err
  }
}

export async function getAssessmentHistory(limit = 20): Promise<AssessmentHistoryEntry[]> {
  const { data } = await api.get<AssessmentHistoryEntry[]>('/assessment/history', { params: { limit } })
  return data
}

export async function getPersonalizedProfile(): Promise<PersonalizedProfile | null> {
  try {
    const { data } = await api.get<PersonalizedProfile>('/assessment/profile')
    return data
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 404) return null
    throw err
  }
}

export async function getAssessmentRecommendations(
  pregnantOrTrying = false,
): Promise<AssessmentRecommendations | null> {
  try {
    const { data } = await api.get<AssessmentRecommendations>('/assessment/recommendations', {
      params: { pregnant_or_trying: pregnantOrTrying },
    })
    return data
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 404) return null
    throw err
  }
}
