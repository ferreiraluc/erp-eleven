import api from './api'

export interface Metric { total_usd: number | null; available_months: number; source_months: number; partial: boolean }
export interface MonthResult {
  year: number; month: number; total_usd: number | null; partial: boolean; source_id: string; filename: string;
  source_cell: string | null; synced_at: string | null; stale: boolean; warnings: string[];
  difference_usd?: number | null; difference_percent?: number | null; previous_year?: number | null
}
export interface WeekResult { year: number; month: number; index: number; label: string; total_usd: number; partial: boolean; source_id: string }
export interface Overview {
  access?: {scope: 'all' | 'own'; seller: string | null};
  years: number[]; sellers: string[]; latest: { year: number | null; month: number | null }; selected: Metric;
  months: MonthResult[]; annual: (Metric & { year: number })[];
  ranking: { name: string; total_usd: number; available_months: number; source_months: number }[];
  weeks: WeekResult[]; currencies: { currency: string; value: number | null; available_months: number; source_months: number }[];
  comparison_month: number; comparison: MonthResult[]; coverage: { months: number; files: number; warnings: number }
}
export interface SourceStatus {
  configured: boolean; enabled: boolean; running: boolean; requested_at: string | null; started_at: string | null;
  finished_at: string | null; next_sync_at: string | null; error: string | null;
  sources: { id: string; filename: string; kind: string; year: number | null; month: number | null;
    synced_at: string | null; checked_at: string | null; error: string | null; selected: boolean; has_data: boolean; warnings: string[] }[]
}
export interface SourceConfig { current_url: string; archive_url: string; archive_root: string; current_year: number | null; current_month: number | null; enabled: boolean }
const base = '/api/sales-bi'
export const salesBi = {
  overview: (params: {year?: number; month?: number; seller?: string}) => api.get<Overview>(base + '/overview', { params }).then(r => r.data),
  status: () => api.get<SourceStatus>(base + '/sources').then(r => r.data),
  config: () => api.get<SourceConfig | null>(base + '/config').then(r => r.data),
  save: (config: SourceConfig) => api.put(base + '/config', config),
  sync: () => api.post(base + '/sync'),
}
