import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearGradePreview, gradeError, inventoryGradeAi, restoreGradePreview, saveGradePreview, type GradePreview } from './inventoryGradeAi'

const transport = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('./api', () => ({ default: transport }))
const id = (n: number) => `10000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const preview = (): GradePreview => ({
  preview_token: 'signed-preview-token-for-this-account', expires_at: '2026-11-02T20:00:00Z', target_group_key: 'Camisa Boss',
  items: [1, 2].map(n => ({ id: id(n), name: `Camisa ${n}`, brand: 'Boss', category: 'Camisas', size: n === 1 ? 'S' : 'M', color: 'Preto', group_key: null, version: 'a'.repeat(64), is_active: true, has_image: false })),
  existing_members: [], source_groups: [], warnings: [],
})

beforeEach(() => { vi.restoreAllMocks(); transport.post.mockReset(); sessionStorage.clear() })

describe('Grade analysis transport and uncertain confirmation recovery', () => {
  it('sends explicit analysis, versioned preview and token confirmation with bounded timeouts', async () => {
    transport.post.mockResolvedValue({ data: { result: 'mock' } })
    const signal = new AbortController().signal, p = preview()
    await inventoryGradeAi.analyze(p.items.map(item => item.id), false, signal)
    expect(transport.post).toHaveBeenLastCalledWith('/api/inventory/grades/ai-analysis', { item_ids: [id(1), id(2)], include_photos: false }, { signal, timeout: 90_000 })
    const body = { item_ids: [id(1), id(2)], new_group_name: 'Camisa Boss', expected_versions: { [id(1)]: 'a'.repeat(64), [id(2)]: 'a'.repeat(64) } }
    await inventoryGradeAi.preview(body, signal)
    expect(transport.post).toHaveBeenLastCalledWith('/api/inventory/grades/preview', body, { signal, timeout: 30_000 })
    await inventoryGradeAi.apply(p.preview_token)
    expect(transport.post).toHaveBeenLastCalledWith('/api/inventory/grades/commit', { preview_token: p.preview_token, confirmed: true }, { timeout: 30_000 })
  })

  it('isolates saved confirmations by account and keeps the exact token, including after preview expiry', () => {
    const first = preview(), other = { ...preview(), preview_token: 'another-account-preview-token' }
    saveGradePreview('user-a', first); saveGradePreview('user-b', other)
    expect(restoreGradePreview('user-a')).toEqual(first)
    expect(restoreGradePreview('user-b')).toEqual(other)
    expect(restoreGradePreview('user-c')).toBeNull()
    clearGradePreview('user-a')
    expect(restoreGradePreview('user-a')).toBeNull()
    expect(restoreGradePreview('user-b')).toEqual(other)
    expect(() => saveGradePreview('', first)).toThrow('missing-user')
  })

  it.each([
    ['wrong account', (p: GradePreview) => ({ user_id: 'other', preview: p })],
    ['short token', (p: GradePreview) => ({ user_id: 'a', preview: { ...p, preview_token: 'short' } })],
    ['missing products', (p: GradePreview) => ({ user_id: 'a', preview: { ...p, items: [] } })],
    ['duplicate products', (p: GradePreview) => ({ user_id: 'a', preview: { ...p, items: [p.items[0], p.items[0]] } })],
    ['unversioned product', (p: GradePreview) => ({ user_id: 'a', preview: { ...p, items: [{ ...p.items[0], version: '' }, p.items[1]] } })],
    ['invalid expiration', (p: GradePreview) => ({ user_id: 'a', preview: { ...p, expires_at: 'not-a-date' } })],
    ['invalid source counts', (p: GradePreview) => ({ user_id: 'a', preview: { ...p, source_groups: [{ group_key: 'old', moving_count: '2', remaining_count: 0 }] } })],
  ])('rejects corrupt recovery data: %s', (_, saved) => {
    sessionStorage.setItem('eleven:grade-confirmation:a', JSON.stringify(saved(preview())))
    expect(() => restoreGradePreview('a')).toThrow('invalid-recovery')
    expect(transport.post).not.toHaveBeenCalled()
  })

  it('preserves read/write failures instead of silently starting a replacement confirmation', () => {
    vi.spyOn(sessionStorage, 'setItem').mockImplementation(() => { throw new Error('storage-blocked') })
    expect(() => saveGradePreview('a', preview())).toThrow('storage-blocked')
    vi.spyOn(sessionStorage, 'getItem').mockImplementation(() => { throw new Error('storage-blocked') })
    expect(() => restoreGradePreview('a')).toThrow('storage-blocked')
    expect(transport.post).not.toHaveBeenCalled()
  })

  it('uses a readable provider error and falls back for unstructured validation details', () => {
    expect(gradeError({ response: { data: { detail: 'Análise indisponível.' } } }, 'fallback')).toBe('Análise indisponível.')
    expect(gradeError({ response: { data: { detail: [{ msg: 'invalid' }] } } }, 'fallback')).toBe('fallback')
    expect(gradeError(new Error('offline'), 'fallback')).toBe('fallback')
  })
})
