import api, { type User } from './api'
export interface UserAccess { nome: string; ativo: boolean; sales_scope: 'all'|'own'; sales_seller: string|null; vendedor_id: string|null }
export interface AuditEvent { id: string; occurred_at: string; user_id: string|null; actor_name: string; source: string; action: string; module: string; entity: string|null; entity_id: string|null; request_id: string|null; route: string|null; method: string|null; status_code: number|null; changes: Record<string, unknown> }
export interface AuditResult { total: number; offset: number; limit: number; since: string; active_seconds: number; users: {id:string;name:string;active_seconds:number;last_seen_at:string|null;actions:Record<string,number>}[]; modules:{module:string;active_seconds:number}[]; events:AuditEvent[] }
export const accessAPI = {
  users: () => api.get<User[]>('/api/access/users').then(r=>r.data),
  create: (body: UserAccess & {email:string;password:string}) => api.post<User>('/api/access/users',body).then(r=>r.data),
  update: (id:string,body:UserAccess) => api.put<User>(`/api/access/users/${id}`,body).then(r=>r.data),
  reset: (id:string,password:string) => api.post(`/api/access/users/${id}/reset-password`,{password}),
  audit: (params:{days:number;user_id?:string;module?:string;action?:string;offset:number}) => api.get<AuditResult>('/api/access/audit',{params}).then(r=>r.data),
}
