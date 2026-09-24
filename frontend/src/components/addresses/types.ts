export interface AddressData { pais:'BR'|'PY';nome:string;telefone:string;cpf:string;endereco:string;numero:string;bairro:string;complemento:string;cidade:string;estado:string;cep:string;email:string }
export const blankAddress=(pais:'BR'|'PY'='PY'):AddressData=>({pais,nome:'',telefone:'',cpf:'',endereco:'',numero:'',bairro:'',complemento:'',cidade:'',estado:'',cep:'',email:''})
export interface SavedAddress {id:string;label:string;data:AddressData;cliente_id:string|null;pdv_cliente_id:string|null;active:boolean;version:number}
export interface Sender {id:string;name:string;lines:string[];data:AddressData|null;active:boolean;version:number}
export interface Layout {id:string;name:string;version:number;config:{font_size:number;margin:number;sender_font_size:number;sender_gap:number;bold:boolean;title:string;fields:string[]}}
export interface Job {id:string;status:string;source:string;created_at:string;user:string;recipient:string;country:string;editable:boolean;pdf_available:boolean;parent_id:string|null}
export interface Freight {id:string;state:string;environment:string;recipient:string;provider_id:string|null;price:string|null;tracking:string|null;label_url:string|null;label_status:string;pdf_available:boolean;label_error:string|null;auto_print:boolean;print_job_id:string|null;error:string|null;created_at:string;rates:{id:number;name:string;price:string;delivery_time:number}[]}
export interface Customer {id:string;kind:'pdv'|'pedidos';nome:string;telefone:string|null;cpf:string|null;endereco:string|null}
export interface Overview {addresses:number;statuses:Record<string,number>;devices:{id:string;name:string;active:boolean;last_seen_at:string|null}[]}
