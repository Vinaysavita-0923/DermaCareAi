/** Typed to match backend/app/schemas/acne_schema.py exactly. */
import { api } from './api'

export interface AcneAnalysisResult {
  model_status: 'ok' | 'model_not_configured' | string
  predicted_class: string | null
  raw_score: number | null
  is_diagnosis: boolean
  note: string
}

export async function analyzeAcneImage(file: File): Promise<AcneAnalysisResult> {
  const form = new FormData()
  form.append('image', file) // field name must match the backend's `image` param
  const { data } = await api.post<AcneAnalysisResult>('/acne/analyze', form)
  return data
}
