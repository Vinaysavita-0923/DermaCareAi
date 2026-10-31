/** Typed to match backend/app/schemas/catalog_schema.py exactly. */
import { api } from './api'

export interface Ingredient {
  id: number
  name: string
  description: string | null
  precautions: string | null
  source: string | null
}

export interface Product {
  id: number
  name: string
  brand: string | null
  category: string | null
  description: string | null
  is_sample_data: boolean
  source: string | null
  rating: number | null
}

export interface ProductDetail extends Product {
  ingredients: Ingredient[]
  ingredients_text: string | null
  ingredients_list: string | null
  ingredient_count: number | null
  suitable_dry: boolean | null
  suitable_normal: boolean | null
  suitable_oily: boolean | null
  suitable_combination: boolean | null
  suitable_sensitive: boolean | null
}

export interface ProductCategory {
  category: string
  count: number
}

export async function searchProducts(
  q?: string,
  category?: string,
  limit?: number,
  offset?: number,
): Promise<Product[]> {
  const { data } = await api.get<Product[]>('/products', { params: { q, category, limit, offset } })
  return data
}

export async function getProduct(id: number): Promise<ProductDetail> {
  const { data } = await api.get<ProductDetail>(`/products/${id}`)
  return data
}

export async function getProductCategories(): Promise<ProductCategory[]> {
  const { data } = await api.get<ProductCategory[]>('/products/categories')
  return data
}

export async function countProducts(q?: string, category?: string): Promise<number> {
  const { data } = await api.get<{ count: number }>('/products/count', { params: { q, category } })
  return data.count
}
