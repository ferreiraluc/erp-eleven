import { uiNumber } from '@/i18n/uiText'
export function usd(value: number | string | null | undefined): string {
  return value !== null && value !== undefined && String(value).trim() !== '' && Number.isFinite(Number(value))
    ? `US$ ${uiNumber(value, 2)}` : 'US$ —'
}
export function saleUsd(value: number | string, rate: number | string | null | undefined): string {
  return Number.isFinite(Number(rate)) && Number(rate) > 0 ? usd(Number(value) / Number(rate)) : usd(null)
}
