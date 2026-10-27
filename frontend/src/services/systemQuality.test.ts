import { afterEach, expect, it } from 'vitest'
import type { AxiosAdapter } from 'axios'
import api from '@/services/api'
import { saveToken } from '@/services/sessionStorage'
import { systemQualityAPI, qualityFindingPath } from './systemQuality'
const adapter = api.defaults.adapter
afterEach(() => {
  api.defaults.adapter = adapter
  localStorage.clear()
  sessionStorage.clear()
})
it('captures request identity before a different user signs in', async () => {
  let authorization: unknown
  api.defaults.adapter = (async (config) => {
    authorization = config.headers.Authorization
    return { status: 200, statusText: 'OK', headers: {}, config, data: {} }
  }) as AxiosAdapter
  saveToken('owner')
  const pending = systemQualityAPI.overview()
  saveToken('other')
  await pending
  expect(authorization).toBe('Bearer owner')
})
it('constructs only known module links and rejects an injected entity type', () => {
  expect(qualityFindingPath({ key: 'x', entity_type: 'constructor', severity: 'info' })).toBeNull()
  expect(
    qualityFindingPath({
      key: 'x',
      entity_type: 'https://evil.test/',
      severity: 'info',
    }),
  ).toBeNull()
  expect(
    qualityFindingPath({
      key: 'x',
      entity_type: 'pdv_sale',
      entity_id: '//evil.test',
      severity: 'warning',
    }),
  ).toBe('/vendas-pdv')
  expect(
    qualityFindingPath({
      key: 'x',
      entity_type: 'inventory',
      entity_id: '//evil.test',
      severity: 'info',
    }),
  ).toBe('/inventory')
})
