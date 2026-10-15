import { describe, expect, it, vi } from 'vitest'
import { jsPDF } from 'jspdf'
import { receiptPdfFile } from './receiptPdf'

describe('receipt PDF bytes for mobile sharing', () => {
  it('preserves all bytes of a real PDF with a safe name and explicit MIME', async () => {
    const pdf = new jsPDF(); pdf.text('ELEVEN - prueba', 10, 10)
    const buffer = pdf.output('arraybuffer')
    const file = receiptPdfFile(buffer, '../ABC123?file=1')
    expect(file.name).toBe('eleven-ticket-ABC123file1.pdf')
    expect(file.type).toBe('application/pdf')
    expect(file.size).toBe(buffer.byteLength)
    expect(new Uint8Array(await file.arrayBuffer())).toEqual(new Uint8Array(buffer))
  })

  it.each(['', '<html>login</html>', '{"detail":"Unauthorized"}', '%PDF-1.4 truncated'])('rejects an invalid or incomplete response: %s', data => {
    expect(() => receiptPdfFile(new TextEncoder().encode(data).buffer as ArrayBuffer, 'ABC')).toThrow('INVALID_RECEIPT_PDF')
  })
})

vi.mock('@/services/api', () => ({ default: { get: vi.fn() } }))
import api from '@/services/api'
import { pdvReceipts } from '@/services/pdvReceipts'
it('requests materialized binary data from the authenticated receipt endpoint', async () => {
  const buffer = new jsPDF().output('arraybuffer')
  vi.mocked(api.get).mockResolvedValueOnce({ data: buffer })
  expect(await pdvReceipts.pdf('test-sale')).toBe(buffer)
  expect(api.get).toHaveBeenCalledWith('/api/pdv/sales/test-sale/receipt/pdf', { responseType: 'arraybuffer' })
})

import { receiptSharePolicy } from './receiptPdf'
it('distinguishes a denied sharing policy from an unrecognized policy name', () => {
  Object.defineProperty(document, 'featurePolicy', { configurable: true, value: { features: () => ['web-share'], allowsFeature: () => false } })
  expect(receiptSharePolicy()).toEqual({ allowed: false, supported: true })
  Object.defineProperty(document, 'featurePolicy', { configurable: true, value: { features: () => ['camera'], allowsFeature: () => false } })
  expect(receiptSharePolicy()).toEqual({ allowed: 'unknown', supported: false })
  Object.defineProperty(document, 'featurePolicy', { configurable: true, value: { features: () => ['web-share'], allowsFeature: () => true } })
  expect(receiptSharePolicy()).toEqual({ allowed: true, supported: true })
  Object.defineProperty(document, 'featurePolicy', { configurable: true, value: undefined })
})
