import api from './api'

export interface ReceiptPrinter { id: string; name: string; paper_width_mm: number; paper_height_mm: number; auto_receipts: boolean; last_seen_at: string | null }
export interface ReceiptJob { id: string; status: string; diagnostic_message: string | null }
export interface ReceiptState { printer: ReceiptPrinter | null; job: ReceiptJob | null }
export const pdvReceipts = {
  credential: (): Promise<{token:string}> => api.post('/api/printing/receipt-device/credential', null, {params:{confirm:true}}).then(r=>r.data),
  printer: (): Promise<{ device: ReceiptPrinter | null }> => api.get('/api/printing/receipt-device').then(r => r.data),
  configure: (body: { name: string; paper_width_mm: number; paper_height_mm: number; auto_receipts: boolean }): Promise<{ device: ReceiptPrinter; token: string | null }> => api.put('/api/printing/receipt-device', body).then(r => r.data),
  state: (id: string): Promise<ReceiptState> => api.get(`/api/pdv/sales/${id}/receipt`).then(r => r.data),
  print: (id: string, copyKey?: string): Promise<ReceiptState> => api.post(`/api/pdv/sales/${id}/receipt`, null, { params: copyKey ? { copy_key: copyKey, confirm_copy: true } : {} }).then(r => r.data),
  package: (): Promise<Blob> => api.get('/api/printing/agent-package', { params: { profile: 'tickets' }, responseType: 'blob' }).then(r => r.data),
}
