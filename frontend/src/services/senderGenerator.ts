import api from './api'
import type { AddressData } from '@/components/addresses/types'

export const FOURDEVS_PAGE = 'https://www.4devs.com.br/gerador_de_pessoas'
export const BRAZIL_STATES = 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split(' ')
export type PersonSource = '4devs_web_form' | '4devs_json_import'
export interface PersonPreview {
  person: Record<string, string>
  sender_data: AddressData
  source: PersonSource
  synthetic: true
  saved: false
}
export interface GenerationOptions { sexo: 'I' | 'M' | 'F'; idade: number | null; estado: string }
const base = '/api/address-manager/sender-generator'

export async function generatePerson(options: GenerationOptions): Promise<PersonPreview> {
  return (await api.post<PersonPreview>(base + '/generate', options, { timeout: 30000 })).data
}

export async function importPerson(json: string): Promise<PersonPreview> {
  return (await api.post<PersonPreview>(base + '/import', { json_text: json })).data
}

export async function saveGeneratedSender(body: {
  request_key: string; approved: true; source: PersonSource; name: string; data: AddressData; active: boolean
}): Promise<{ id: string; reused: boolean }> {
  return (await api.post<{ id: string; reused: boolean }>(base + '/save', body)).data
}

export function generationError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'object' && detail && 'code' in detail && typeof detail.code === 'string') return detail.code
  return 'request_failed'
}
