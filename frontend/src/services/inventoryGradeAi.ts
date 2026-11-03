import api from './api'

export interface GradeProduct {
  id: string
  name: string
  category: string | null
  brand: string | null
  size: string | null
  color: string | null
  group_key: string | null
  is_active: boolean
  version: string
  has_image: boolean
}
export interface GradeAdvice {
  item_ids: string[]
  confidence: 'high' | 'medium' | 'low'
  evidence: string[]
  warnings: string[]
}
export interface GradeAnalysis {
  provider: 'deepseek' | 'anthropic'
  model: string
  analyzed_count: number
  photos_analyzed: number
  products: GradeProduct[]
  suggestions: GradeAdvice[]
  warnings: string[]
  advisory_only: true
}
export interface GradePreview {
  preview_token: string
  expires_at: string
  target_group_key: string
  items: GradeProduct[]
  existing_members: GradeProduct[]
  source_groups: { group_key: string; moving_count: number; remaining_count: number }[]
  warnings: string[]
}
export interface GradeApplyResult {
  target_group_key: string
  item_ids: string[]
  applied_count: number
  already_applied: boolean
}
export const inventoryGradeAi = {
  analyze: (item_ids: string[], include_photos: boolean, signal?: AbortSignal) =>
    api
      .post<GradeAnalysis>(
        '/api/inventory/grades/ai-analysis',
        { item_ids, include_photos },
        { signal, timeout: 90_000 },
      )
      .then((r) => r.data),
  preview: (
    body: {
      item_ids: string[]
      target_group_key?: string
      new_group_name?: string
      expected_versions: Record<string, string>
    },
    signal?: AbortSignal,
  ) =>
    api
      .post<GradePreview>('/api/inventory/grades/preview', body, { signal, timeout: 30_000 })
      .then((r) => r.data),
  apply: (preview_token: string) =>
    api
      .post<GradeApplyResult>(
        '/api/inventory/grades/commit',
        { preview_token, confirmed: true },
        { timeout: 30_000 },
      )
      .then((r) => r.data),
}
const pendingKey = (userId: string) => 'eleven:grade-confirmation:' + userId
export function saveGradePreview(userId: string, preview: GradePreview) {
  if (!userId) throw new Error('missing-user')
  sessionStorage.setItem(pendingKey(userId), JSON.stringify({ user_id: userId, preview }))
}
export function clearGradePreview(userId: string) {
  sessionStorage.removeItem(pendingKey(userId))
}
export function restoreGradePreview(userId: string): GradePreview | null {
  const raw = sessionStorage.getItem(pendingKey(userId))
  if (!raw) return null
  if (raw.length > 1_000_000) throw new Error('invalid-recovery')
  const saved = JSON.parse(raw),
    p = saved?.preview as GradePreview
  const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i
  if (
    saved.user_id !== userId ||
    !p ||
    typeof p.preview_token !== 'string' ||
    p.preview_token.length < 20 ||
    p.preview_token.length > 150000 ||
    typeof p.target_group_key !== 'string' ||
    !p.target_group_key ||
    p.target_group_key.length > 100 ||
    !Number.isFinite(Date.parse(p.expires_at)) ||
    !Array.isArray(p.items) ||
    p.items.length < 2 ||
    p.items.length > 24 ||
    !Array.isArray(p.existing_members) ||
    p.existing_members.length > 500 ||
    !Array.isArray(p.source_groups) ||
    p.source_groups.length > 24 ||
    !Array.isArray(p.warnings) ||
    p.warnings.some((w) => typeof w !== 'string') ||
    [...p.items, ...p.existing_members].some(
      (row) =>
        !row ||
        !uuid.test(row.id) ||
        typeof row.name !== 'string' ||
        typeof row.version !== 'string' ||
        !/^[a-f0-9]{64}$/.test(row.version),
    ) ||
    new Set(p.items.map((row) => row.id)).size !== p.items.length ||
    p.source_groups.some(
      (row) =>
        !row ||
        typeof row.group_key !== 'string' ||
        !Number.isSafeInteger(row.moving_count) ||
        !Number.isSafeInteger(row.remaining_count),
    )
  )
    throw new Error('invalid-recovery')
  return p
}
export function gradeError(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

/** Suggest a family name without discarding model numbers or unrelated suffixes. */
export function gradeFamilyName(product: Pick<GradeProduct, 'name' | 'size' | 'color'>): string {
  let name = product.name.trim().replace(/\s+/g, ' ')
  for (let pass = 0; pass < 2; pass++) {
    for (const value of [product.size, product.color]) {
      const suffix = value?.trim() ? ' ' + value.trim().replace(/\s+/g, ' ') : ''
      if (
        suffix &&
        name.length > suffix.length &&
        name.toLocaleLowerCase().endsWith(suffix.toLocaleLowerCase())
      )
        name = name.slice(0, -suffix.length).trimEnd()
    }
  }
  return name.slice(0, 100)
}
