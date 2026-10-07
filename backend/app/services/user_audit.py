"""Record committed mutations without passwords, documents, payloads or query strings."""
import uuid
from decimal import Decimal
from datetime import date, datetime
from enum import Enum
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from ..models.access import AuditEvent, now

INTERNAL = {'audit_events', 'activity_spans', 'auth_sessions', 'assistant_messages',
            'assistant_deliveries', 'assistant_knowledge', 'sales_bi_workbooks'}
SAFE_VALUES = {'status', 'state', 'ativo', 'active', 'is_active', 'role', 'sales_scope',
               'current_stock', 'stock_loja', 'stock_deposito', 'quantity', 'quantity_before',
               'quantity_after', 'total_gs', 'valor_bruto', 'valor_liquido', 'moeda',
               'sale_price', 'cost_price', 'label_status', 'tipo', 'aprovada'}
SECRET_FIELDS = {'senha_hash', 'auth_version', 'token_hash', 'token', 'webhook_secret',
                 'document_pdf', 'pdf', 'image_data', 'snapshot', 'payload', 'response', 'text',
                 'content', 'data', 'raw_data', 'lines', 'config'}
MODULES = {
    'usuarios': 'usuarios', 'users': 'usuarios', 'access': 'usuarios', 'auth': 'conta',
    'vendedores': 'vendors', 'funcionarios': 'vendors', 'folgas': 'vendors',
    'inventory_items': 'inventory', 'stock_movements': 'inventory', 'suppliers': 'inventory',
    'inventory_sessions': 'inventory', 'inventory_session_items': 'inventory',
    'label_templates': 'inventory', 'ocr': 'inventory', 'product-photo': 'inventory',
    'rastreamentos': 'rastreamento', 'pedido_anexos': 'pedidos', 'tags_status': 'pedidos', 'tags': 'pedidos',
    'saved_addresses': 'enderecos', 'print_layouts': 'enderecos', 'print_jobs': 'enderecos',
    'print_devices': 'enderecos', 'print_senders': 'enderecos', 'freight_orders': 'enderecos',
    'freight_webhooks': 'enderecos', 'address-manager': 'enderecos', 'printing': 'enderecos', 'freight': 'enderecos',
    'assistant_identities': 'assistente', 'assistant_notes': 'assistente', 'assistant_actions': 'assistente', 'assistant': 'assistente',
    'sales_bi_config': 'bi-vendas', 'sales-bi': 'bi-vendas',
    'exchange_rates': 'exchange-rates', 'money_transfers': 'vendas', 'money-transfers': 'vendas',
    'excel-import': 'vendas', 'comprovantes': 'vendas', 'cambistas': 'vendas',
    'pdv_clientes': 'pdv', 'pdv_sales': 'pdv', 'pdv_sale_items': 'pdv', 'pdv_payments': 'pdv', 'pdv_fiado_movements': 'fiado',
}


def module_name(value):
    return MODULES.get(value, value)


def actor(user, source='web', **context):
    return {'user_id': user.id, 'actor_name': user.nome, 'source': source, **context}


def bind_actor(db, user, source='web', **context):
    value = actor(user, source, **context)
    db.info['audit_actor'] = value
    return value


def record(db, action, module, **details):
    db.add(AuditEvent(**{**db.info.get('audit_actor', {}), 'action': action,
                        'module': module_name(module), 'changes': {}, **details}))


def scalar(value):
    if isinstance(value, Enum): return value.value
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, uuid.UUID): return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None: return value
    return None


@event.listens_for(Session, 'after_flush')
def audit_flush(db, context):
    if not db.info.get('audit_enabled') or not db.info.get('audit_actor'):
        return
    for action, objects in [('create', db.new), ('update', db.dirty), ('delete', db.deleted)]:
        for obj in list(objects):
            state = inspect(obj)
            table = state.mapper.local_table.name
            if table in INTERNAL:
                continue
            changes = {}
            for col in state.mapper.column_attrs:
                if col.key in SECRET_FIELDS or any(s in col.key.lower() for s in ('password','secret','token')):
                    continue
                history = state.attrs[col.key].history
                if action == 'update' and not history.has_changes():
                    continue
                if col.key in SAFE_VALUES:
                    changes[col.key] = {'before': scalar(history.deleted[0]) if history.deleted else None,
                                        'after': scalar(getattr(obj, col.key)) if action != 'delete' else None}
                else:
                    changes[col.key] = {'changed': True}
            if action == 'update' and not changes:
                continue
            db.connection().execute(AuditEvent.__table__.insert().values(
                id=uuid.uuid4(), occurred_at=now(), **db.info['audit_actor'], action=action,
                module=module_name(table), entity=table, entity_id=str(getattr(obj, 'id', ''))[:100], changes=changes))


@event.listens_for(Session, 'do_orm_execute', retval=True)
def audit_bulk(state):
    result = state.invoke_statement()
    db = state.session
    if (state.is_update or state.is_delete) and db.info.get('audit_enabled') and db.info.get('audit_actor'):
        table = getattr(getattr(state.statement, 'table', None), 'name', '')
        if table and table not in INTERNAL:
            db.connection().execute(AuditEvent.__table__.insert().values(
                id=uuid.uuid4(), occurred_at=now(), **db.info['audit_actor'],
                action='bulk_update' if state.is_update else 'bulk_delete', module=module_name(table),
                entity=table, changes={'affected_rows': max(0, getattr(result, 'rowcount', 0))}))
    return result
