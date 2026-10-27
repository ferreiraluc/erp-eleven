import api from '@/services/api'
import { storedToken } from '@/services/sessionStorage'

export type QualityState = 'queued' | 'running' | 'completed' | 'partial' | 'failed'
export interface QualityConfig {
  enabled: boolean
  ai_enabled: boolean
  local_time: string
  timezone: 'America/Sao_Paulo'
  first_run_on: string
  version: number
  updated_at: string | null
  ai_reserved_on: string | null
}
export interface QualityCoverage {
  checked: number
  complete: boolean
  window?:
    | 'last_24_hours'
    | 'active_jobs_last_7_days'
    | 'active_devices'
    | 'current_state'
    | 'current_process'
  error?: 'run_query_budget' | 'check_unavailable'
  comparison?: 'changed_cohort_only'
}
export interface QualityRun {
  id: string
  run_day: string
  kind: 'daily' | 'manual'
  status: QualityState
  created_at: string
  started_at: string | null
  finished_at: string | null
  attempts: number
  ai_attempted: boolean
  ai_status: string | null
  provider_calls: number
  input_tokens: number
  output_tokens: number
  request_id: string | null
  requested_by: string | null
  summary: string | null
  ai_summary: string | null
  provider: 'deepseek' | 'anthropic' | null
  error_category: 'run_unavailable' | null
  counters: Record<string, number>
  coverage: Record<string, QualityCoverage>
}
export interface QualityFinding {
  key: string
  entity_type: string
  entity_id?: string
  related_id?: string
  severity: 'info' | 'warning'
}
export interface QualityRunDetail extends QualityRun {
  findings: QualityFinding[]
  findings_total: number
  findings_offset: number
  findings_limit: number
}
export interface QualityOverview {
  config: QualityConfig
  latest: QualityRunDetail | null
  runs: QualityRun[]
  total: number
  offset: number
  limit: number
  limits: Record<string, number>
}

const base = '/api/quality'
function options(token: string | null) {
  return { headers: { Authorization: token ? `Bearer ${token}` : null } }
}
export const systemQualityAPI = {
  overview: (offset = 0, token = storedToken()) =>
    api
      .get<QualityOverview>(`${base}/admin`, {
        ...options(token),
        params: { offset, limit: 10 },
      })
      .then((response) => response.data),
  detail: (id: string, offset = 0, token = storedToken()) =>
    api
      .get<QualityRunDetail>(`${base}/admin/runs/${encodeURIComponent(id)}`, {
        ...options(token),
        params: { findings_offset: offset, findings_limit: 30 },
      })
      .then((response) => response.data),
  configure: (
    value: Pick<QualityConfig, 'enabled' | 'ai_enabled' | 'local_time'> & {
      expected_version: number
    },
    token = storedToken(),
  ) =>
    api
      .put<QualityConfig>(`${base}/config`, value, options(token))
      .then((response) => response.data),
  scan: (requestId: string, token = storedToken()) =>
    api
      .post<QualityRun>(`${base}/scan`, { request_id: requestId }, options(token))
      .then((response) => response.data),
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
/** Paths are owned by the UI; diagnostics data can never supply navigation URLs. */
export function qualityFindingPath(finding: QualityFinding): string | null {
  if (finding.entity_type === 'pdv_sale')
    return finding.entity_id && uuid.test(finding.entity_id)
      ? `/vendas-pdv?sale_id=${encodeURIComponent(finding.entity_id)}`
      : '/vendas-pdv'
  const routes: Record<string, string> = {
    inventory: '/inventory',
    print_job: '/configuracoes',
    print_device: '/configuracoes',
    sales_bi: '/bi-vendas',
    customer: '/clientes',
    address: '/enderecos',
    assistant: '/assistente',
    freight_labels: '/enderecos?tab=freight',
    notifications: '/notificacoes',
    tracking: '/rastreamento',
  }
  return Object.hasOwn(routes, finding.entity_type) ? routes[finding.entity_type] : null
}
export function isQualityRunId(value: string | null | undefined): value is string {
  return !!value && uuid.test(value)
}
