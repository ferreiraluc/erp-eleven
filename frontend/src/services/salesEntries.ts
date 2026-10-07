import api from './api'

export interface EntryCurrency { currency: string; count: number; gross: number | null; net: number | null; net_available: number }
export interface SalesEntry {
  id: string; source_id: string; filename: string; sheet: string; row: number; source_cell: string;
  year: number; month: number; week_index: number | null; week_label: string | null;
  seller: string; currency: string; gross: number | null; net: number | null; payment_method: string | null;
  payment_type: string;
  customer: string | null; date: string | null; time: string | null; day_group: string | null;
  date_source?: 'recorded' | 'week_day' | 'week_period' | 'unresolved';
  period_start?: string | null; period_end?: string | null;
  week_start?: string | null; week_end?: string | null;
  synced_at: string | null; stale: boolean;
}
export interface EntriesResult {
  items: SalesEntry[]; total: number; offset: number; limit: number; sellers: string[]; currencies: string[]; dates: string[];
  payment_methods: { value: string; label: string }[];
  weeks?: { start: string; end: string; settlement_date: string }[];
  payments: { payment_type: string; label: string; count: number; currencies: EntryCurrency[] }[];
  summary: { count: number; currencies: EntryCurrency[]; dated_count: number; timed_count: number; undated_count: number; official_total_usd: number | null };
  daily: { date: string; count: number; currencies: EntryCurrency[] }[];
  hourly: { hour: number; count: number; currencies: EntryCurrency[] }[];
  weekdays: { day: string; count: number; currencies: EntryCurrency[] }[];
  reconciliation: { year: number; month: number; currency: string; published: number | null; observed_net: number | null; difference: number | null }[];
  coverage: { source_count: number; needs_sync: boolean; sources_without_entries: number; skipped_rows: number | null; undated_excluded: number;
    period_excluded?: number; inferred_dates?: number; period_included?: number;
    issues?: { filename: string; sheet: string; skipped_rows: number }[] };
  access: { scope: 'all' | 'own'; seller: string | null };
}
export interface EntriesQuery { year?: number; month?: number; seller?: string; currency?: string; day?: string; date_from?: string; date_to?: string; payment_method?: string; search?: string; offset?: number; limit?: number }
export const salesEntries = {
  list: (params: EntriesQuery) => api.get<EntriesResult>('/api/sales-bi/entries', { params }).then(r => r.data),
}
