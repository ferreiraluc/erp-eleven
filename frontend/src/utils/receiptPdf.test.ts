import { describe, expect, it, vi } from 'vitest'
import { jsPDF } from 'jspdf'
import { receiptPdfFile } from './receiptPdf'

describe('receipt PDF bytes for downloading', () => {
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
