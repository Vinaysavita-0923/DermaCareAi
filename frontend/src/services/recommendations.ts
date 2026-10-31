/** Typed to match backend/app/schemas/catalog_schema.py (recommendation shapes). */
import { api } from './api'

/** verified = full list from the official page; partial = key ingredients only;
 * unverified = nothing known; sample = generic sample product. */
export type IngredientStatus = 'verified' | 'partial' | 'unverified' | 'sample'

export interface RecommendedProduct {
  product_id: number | null
  name: string
  brand: string | null
  category: string
  usage_time: 'morning' | 'night' | 'both' | string | null
  description: string
  uses: string | null
  how_to_use: string | null
  cautions: string | null
  ingredients: string[]
  ingredient_status: IngredientStatus
  warnings: string[]
  is_sample_data: boolean
  source_url: string | null
  score: number
  match_reasons: string[]
}

export interface RecommendationResponse {
  skin_type: string
  concerns: string[]
  matches: RecommendedProduct[]
  routine: { morning: RecommendedProduct[]; evening: RecommendedProduct[] }
  notes: string[]
  disclaimer: string
}

export async function getRecommendations(pregnantOrTrying = false): Promise<RecommendationResponse> {
  const { data } = await api.get<RecommendationResponse>('/recommendations', {
    params: { pregnant_or_trying: pregnantOrTrying },
  })
  return data
}
