import type { NotificationContext, NotificationSaleDetail, NotificationTrackingDetail } from './notifications'

export interface NotificationPreviewSource {
  title: string
  body: string
  user_ids: string[]
  context?: NotificationContext | null
  action_path?: string | null
}
export type AuthoringProblem =
  | 'contextSaleNeeded'
  | 'contextProductNeeded'
  | 'contextVariablesMissing'
  | 'contextUnknownVariable'
  | 'contextTooLong'

/** A local preview only. The server revalidates the context and renders on save. */
export function notificationPreview(
  source: NotificationPreviewSource,
  users: { id: string; nome: string }[],
  sale: NotificationSaleDetail | null,
  moment = new Date(),
  tracking: NotificationTrackingDetail | null = null,
): { title: string; body: string; problem: AuthoringProblem | null } {
  const context = source.context
  const matches = !!context?.sale_id && sale?.id === context.sale_id
  let problem: AuthoringProblem | null = null
  if ((context?.sale_id && !matches) || (context?.target === 'sale' && !context.sale_id))
    problem = 'contextSaleNeeded'
  // An explicit product reference may be outside the sale (for example an
  // avulso under review). It never rewrites or links the historical sale item.
  if (context?.target === 'product' && !context.item_id) problem = 'contextProductNeeded'
  const formatter = (options: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat('pt-BR', {
      ...options,
      timeZone: 'America/Sao_Paulo',
    }).format(moment)
  const selected =
    source.user_ids.length === 1 ? users.find((user) => user.id === source.user_ids[0]) : null
  const values: Record<string, string> = {
    user_name: matches ? sale.seller_name || 'equipe' : selected?.nome || 'equipe',
    date: formatter({ day: '2-digit', month: '2-digit', year: 'numeric' }),
    time: formatter({ hour: '2-digit', minute: '2-digit', hour12: false }),
  }
  if (matches) values.sale_code = sale.code
  if (matches && sale.status)
    values.status =
      (
        {
          completed: 'concluída',
          cancelled: 'cancelada',
          partially_refunded: 'devolução parcial',
          refunded: 'estornada',
        } as Record<string, string>
      )[sale.status] || sale.status
  if (tracking && tracking.code === trackingCodeFromPath(source.action_path)) {
    values.tracking_code = tracking.code
    values.cliente_username = tracking.cliente_username
    if (!matches) values.status = tracking.status
  }
  function render(value: string) {
    // Match the manual renderer's one-pass brace handling. Literal JSON or
    // product details such as {P,M,L} are ordinary text, not template fields.
    const validationText = value.replace(/\{\{|\}\}/g, '')
    const knownStart = /\{(cliente_username|date|sale_code|status|time|tracking_code|user_name)(?=[^A-Za-z0-9_]|$)/g
    for (const match of validationText.matchAll(knownStart)) {
      if (validationText[match.index! + match[0].length] !== '}')
        problem ||= 'contextUnknownVariable'
    }
    return value.replace(/\{\{|\}\}|\{([^{}]*)\}/g, (token, name: string | undefined) => {
      if (token === '{{') return '{'
      if (token === '}}') return '}'
      if (!name) return token
      if (Object.hasOwn(values, name)) return values[name]!
      if (['sale_code', 'tracking_code', 'cliente_username', 'status'].includes(name))
        problem ||= 'contextVariablesMissing'
      else return token
      return '…'
    })
  }
  const title = render(source.title),
    body = render(source.body)
  if (title.length > 120 || body.length > 2000) problem ||= 'contextTooLong'
  return { title, body, problem }
}

export function trackingCodeFromPath(path: string | null | undefined) {
  if (!path?.startsWith('/rastreamento?')) return ''
  const query = new URLSearchParams(path.slice(path.indexOf('?') + 1))
  const codes = query.getAll('search')
  if (codes.length !== 1) return ''
  return codes[0].trim().replace(/[\s-]+/g, '').toUpperCase()
}

export function notificationDestination(
  context: NotificationContext | null | undefined,
  fallback = '',
) {
  if (context?.target === 'product' && context.item_id)
    return `/inventory?item_id=${encodeURIComponent(context.item_id)}`
  if (context?.sale_id) return `/vendas-pdv?sale_id=${encodeURIComponent(context.sale_id)}`
  return fallback
}
