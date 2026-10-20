import api from './api'

export interface ReceiptPrinter { id: string; name: string; paper_width_mm: number; paper_height_mm: number; auto_receipts: boolean; last_seen_at: string | null; driver?: 'windows' | 'escpos_tcp'; last_test?: ReceiptJob | null }
export interface ReceiptJob { id: string; status: string; diagnostic_message: string | null }
export interface ReceiptState { printer: ReceiptPrinter | null; job: ReceiptJob | null }
export interface ReceiptPreview {
  title: string; location: string; email: string; code: string; sale_id: string; date: string
  status: string; status_changed: boolean; copy: boolean; subtotal: string; discount: string | null; total: string
  refunded: string | null; change: string | null; seller: string; customer: string; footer: string[]; barcode: string
  items: Array<{ name: string; meta: string; calculation: string; total: string; discount: string | null; returned: string | null }>
  payments: Array<{ label: string; amount: string; equivalent: string | null }>
}
export const pdvReceipts = {
  preview: (id: string): Promise<ReceiptPreview> => api.get(`/api/pdv/sales/${id}/receipt/preview`).then(r => r.data),
  pdf: (id: string): Promise<ArrayBuffer> => api.get(`/api/pdv/sales/${id}/receipt/pdf`, { responseType: 'arraybuffer' }).then(r => r.data),
  credential: (deviceId?: string): Promise<{token:string}> => api.post('/api/printing/receipt-device/credential', null, {params:{confirm:true, device_id:deviceId}}).then(r=>r.data),
  destinations: (): Promise<{devices:ReceiptPrinter[]; mac_package_url:string; mac_agent_version:string}> => api.get('/api/printing/receipt-devices').then(r=>r.data),
  prepareMac: (): Promise<{device:ReceiptPrinter; token:string|null}> => api.post('/api/printing/receipt-device/macos').then(r=>r.data),
  testPrinter: (id:string, requestKey:string): Promise<{job:ReceiptJob}> => api.post(`/api/printing/receipt-devices/${id}/test`, {request_key:requestKey, confirm:true}).then(r=>r.data),
  activatePrinter: (id:string, testJobId?:string): Promise<{device:ReceiptPrinter}> => api.post(`/api/printing/receipt-devices/${id}/activate`, {confirm:true, test_job_id:testJobId}).then(r=>r.data),
  pausePrinter: (id:string): Promise<{paused:boolean}> => api.post(`/api/printing/receipt-devices/${id}/pause`, {confirm:true}).then(r=>r.data),
  printer: (): Promise<{ device: ReceiptPrinter | null }> => api.get('/api/printing/receipt-device').then(r => r.data),
  configure: (body: { name: string; paper_width_mm: number; paper_height_mm: number; auto_receipts: boolean }): Promise<{ device: ReceiptPrinter; token: string | null }> => api.put('/api/printing/receipt-device', body).then(r => r.data),
  state: (id: string): Promise<ReceiptState> => api.get(`/api/pdv/sales/${id}/receipt`).then(r => r.data),
  print: (id: string, copyKey?: string): Promise<ReceiptState> => api.post(`/api/pdv/sales/${id}/receipt`, null, { params: copyKey ? { copy_key: copyKey, confirm_copy: true } : {} }).then(r => r.data),
  package: (): Promise<Blob> => api.get('/api/printing/agent-package', { params: { profile: 'tickets' }, responseType: 'blob' }).then(r => r.data),
}
