/** Typed to match backend/app/schemas/skin_condition_schema.py exactly. */
import { api } from './api'

export interface ConditionGuess {
  label: string
  score: number // softmax score 0..1, NOT a validated probability
  serious: boolean
  concern: string | null
}

export interface SkinConditionResult {
  model_status: 'ok' | 'model_not_configured' | string
  predictions: ConditionGuess[]
  low_confidence: boolean
  any_serious: boolean
  is_diagnosis: boolean
  note: string
  not_skin?: boolean
}

export async function analyzeSkinCondition(file: File): Promise<SkinConditionResult> {
  const form = new FormData()
  form.append('image', file) // field name must match the backend's `image` param
  const { data } = await api.post<SkinConditionResult>('/skin-condition/analyze', form, {
    timeout: 60000, // model inference can take a few seconds on a cold free host
  })
  return data
}
