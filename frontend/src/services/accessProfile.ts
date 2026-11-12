// Closed navigation set: a new operational route is never implicitly available
// to catalog-only accounts. The backend enforces the corresponding API policy.
const resellerPaths = new Set(['/dashboard', '/inventory', '/exchange-rates', '/conta', '/notificacoes'])

export function resellerCanVisit(path: string): boolean {
  return resellerPaths.has(path.replace(/\/+$/, '') || '/')
}
