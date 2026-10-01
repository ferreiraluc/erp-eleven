import api from './api'

export interface EntryCurrency { currency: string; count: number; gross: number | null; net: number | null; net_available: number }
export interface SalesEntry {
  id: string; source_id: string; filename: string; sheet: string; row: number; source_cell: string;
  year: number; month: number; week_index: number | null; week_label: string | null;
  seller: string; currency: string; gross: number | null; net: number | null; payment_method: string | null;
  customer: string | null; date: string | null; time: string | null; day_group: string | null;
  synced_at: string | null; stale: boolean;
}
export interface EntriesResult {
  items: SalesEntry[]; total: number; offset: number; limit: number; sellers: string[]; currencies: string[]; dates: string[];
  summary: { count: number; currencies: EntryCurrency[]; dated_count: number; timed_count: number; undated_count: number; official_total_usd: number | null };
  daily: { date: string; count: number; currencies: EntryCurrency[] }[];
  hourly: { hour: number; count: number; currencies: EntryCurrency[] }[];
  weekdays: { day: string; count: number; currencies: EntryCurrency[] }[];
  reconciliation: { year: number; month: number; currency: string; published: number | null; observed_net: number | null; difference: number | null }[];
  coverage: { source_count: number; needs_sync: boolean; sources_without_entries: number; skipped_rows: number | null };
  access: { scope: 'all' | 'own'; seller: string | null };
}
export interface EntriesQuery { year?: number; month?: number; seller?: string; currency?: string; day?: string; search?: string; offset?: number; limit?: number }
export const salesEntries = {
  list: (params: EntriesQuery) => api.get<EntriesResult>('/api/sales-bi/entries', { params }).then(r => r.data),
}
