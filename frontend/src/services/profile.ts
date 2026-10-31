/**
 * Profile API calls, typed to match app/schemas/profile_schema.py
 * exactly — including the closed vocabulary of allowed concern tags,
 * verified against the backend source rather than guessed.
 */
import { api } from './api'

export type SkinType = 'dry' | 'oily' | 'combination' | 'balanced' | 'unsure'

export const SKIN_TYPES: { value: SkinType; label: string }[] = [
  { value: 'dry', label: 'Dry' },
  { value: 'oily', label: 'Oily' },
  { value: 'combination', label: 'Combination' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'unsure', label: "I'm not sure" },
]

// Must match ALLOWED_CONCERNS in backend/app/schemas/profile_schema.py
// exactly — the backend rejects anything outside this list. The first
// 7 are the original free-text-style tags; the rest come from the
// dermacare_skin_assessment_dataset_binary.csv Concern column (see
// CONCERN_LABEL_TO_TAG in app/knowledge_base/skin_assessment_dataset.py)
// and are the ones the assessment wizard's concern step actually uses,
// since only these have real ingredient-guidance data behind them.
export const ALLOWED_CONCERNS = [
  'acne',
  'dryness',
  'redness',
  'texture',
  'oiliness',
  'sensitivity',
  'dullness',
  'dark_circles',
  'dark_spots',
  'hyperpigmentation',
  'open_pores',
  'sun_tan',
  'whiteheads_blackheads',
  'wrinkles',
] as const

// Dataset-backed concerns only (what the assessment wizard shows), tag
// -> the human label the dataset itself uses. Must match
// CONCERN_LABEL_TO_TAG in app/knowledge_base/skin_assessment_dataset.py.
export const DATASET_CONCERNS: { tag: string; label: string }[] = [
  { tag: 'acne', label: 'Acne' },
  { tag: 'dark_circles', label: 'Dark Circles' },
  { tag: 'dark_spots', label: 'Dark Spots' },
  { tag: 'dullness', label: 'Dullness' },
  { tag: 'hyperpigmentation', label: 'Hyperpigmentation' },
  { tag: 'open_pores', label: 'Open Pores' },
  { tag: 'redness', label: 'Redness' },
  { tag: 'sun_tan', label: 'Sun Tan' },
  { tag: 'whiteheads_blackheads', label: 'Whiteheads / Blackheads' },
  { tag: 'wrinkles', label: 'Wrinkles' },
]

// Must match SUBTYPES_BY_DATASET_TYPE in
// app/knowledge_base/skin_assessment_dataset.py — real categories from
// the dataset, not invented labels. "unsure" has no subtypes.
export const SUBTYPES_BY_SKIN_TYPE: Record<SkinType, string[]> = {
  dry: ['Dry to Normal', 'Extreme Dry'],
  oily: ['Oily to Normal', 'Extreme Oily'],
  combination: ['T-Zone Dry Cheeks Oily', 'T-Zone Oily Cheeks Dry'],
  balanced: ['Normal to Dry', 'Normal to Oily'],
  unsure: [],
}

export interface SkinProfile {
  id: number
  user_id: number
  skin_type: SkinType
  skin_subtype: string | null
  age: number | null
  age_group: string | null
  is_sensitive: boolean | null
  concerns: string[] | null
  sensitivity_notes: string | null
  avoid_ingredients: string[] | null
  created_at: string
  updated_at: string
}

export interface SkinProfileUpdate {
  full_name?: string
  age?: number
  skin_type?: SkinType
  skin_subtype?: string
  is_sensitive?: boolean | null
  concerns?: string[]
  sensitivity_notes?: string | null
  avoid_ingredients?: string[]
}

/** Returns the profile, or null if the user hasn't created one yet
 * (the backend returns 404 for that case — not an error to surface). */
export async function getMyProfile(): Promise<SkinProfile | null> {
  try {
    const { data } = await api.get<SkinProfile>('/profile')
    return data
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 404) return null
    throw err
  }
}

export async function saveMyProfile(update: SkinProfileUpdate): Promise<SkinProfile> {
  const { data } = await api.put<SkinProfile>('/profile', update)
  return data
}
