"""Owner-authored references and presentation repair, without operational writes."""
import re
from datetime import timezone
from urllib.parse import parse_qs, urlsplit
import uuid
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, cast, func, literal, String, or_
from sqlalchemy.orm import aliased

from ..models.notification import Notification, NotificationRecipient, NotificationRevision
from ..models.pdv import PdvSale
from ..models.inventory import Item
from ..models.usuario import Usuario
from ..models.rastreamento import Rastreamento
from ..models.pedido import Pedido
from ..models.cliente import Cliente
from ..schemas.notification import MANUAL_TOKEN, NotificationContext, NotificationFields, TEMPLATE_VARIABLES
from .access_policy import is_owner, own_sales
from .pdv_ticket_identity import ticket_code
from .user_sessions import aware
from .tracking_codes import normalize_tracking_code

BRT = ZoneInfo('America/Sao_Paulo')
KNOWN_VARIABLE = re.compile(r'\{(' + '|'.join(sorted(TEMPLATE_VARIABLES)) + r')\}')
TRACKING_LABELS = {'PENDENTE': 'Pendente', 'EM_TRANSITO': 'Em trânsito', 'ENTREGUE': 'Entregue',
                   'ERRO': 'Precisa de conferência', 'NAO_ENCONTRADO': 'Não encontrado no provedor'}


def tracking_code_from_path(path):
    parts = urlsplit(path or '')
    values = parse_qs(parts.query, keep_blank_values=True).get('search', [])
    if parts.path == '/rastreamento' and len(values) == 1:
        return normalize_tracking_code(values[0]) or None
    return None


def tracking_metadata_query(db):
    """Read only explicit package/order/customer references, never documents."""
    order_client = aliased(Cliente)
    return db.query(Rastreamento.id, Rastreamento.codigo_rastreio, Rastreamento.destinatario, Rastreamento.status,
                    Pedido.cliente_nome.label('order_name'), Cliente.nome.label('client_name'),
                    order_client.nome.label('order_client_name'))\
        .outerjoin(Pedido, Pedido.id == Rastreamento.pedido_id)\
        .outerjoin(Cliente, Cliente.id == Rastreamento.cliente_id)\
        .outerjoin(order_client, order_client.id == Pedido.cliente_id)


def find_tracking_metadata(db, code):
    normalized = normalize_tracking_code(code or '')
    return tracking_metadata_query(db).filter(Rastreamento.codigo_rastreio == normalized, Rastreamento.ativo.is_(True)).first() if normalized else None


def tracking_recipient_name(db, row):
    # The shipping snapshot wins over later changes to the linked directory.
    if (row.destinatario or '').strip():
        return row.destinatario.strip()
    if isinstance(row, Rastreamento):
        row = tracking_metadata_query(db).filter(Rastreamento.id == row.id).first()
    for field in ('order_name', 'client_name', 'order_client_name'):
        value = getattr(row, field, None)
        if value and value.strip():
            return value.strip()
    return 'destinatário não informado'


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def path_context(path):
    if not path:
        return None
    parts = urlsplit(path)
    params = parse_qs(parts.query, keep_blank_values=True)
    if parts.path == '/vendas-pdv' and len(params.get('sale_id', [])) == 1:
        identity = _uuid(params['sale_id'][0])
        return {'sale_id': str(identity), 'target': 'sale'} if identity else None
    if parts.path == '/inventory' and len(params.get('item_id', [])) == 1:
        identity = _uuid(params['item_id'][0])
        return {'item_id': str(identity), 'target': 'product'} if identity else None
    return None


def context_value(context, action_path=None):
    raw = context.model_dump(mode='json', exclude_none=True) if isinstance(context, NotificationContext) else context
    return NotificationContext(**raw).model_dump(mode='json', exclude_none=True) if raw else path_context(action_path)


def notice_context(notice, snapshot=None):
    snapshot = snapshot or {}
    context = snapshot.get('context')
    if isinstance(context, dict):
        return context
    from_path = path_context(notice.action_path)
    if notice.entity_type == 'pdv_sale' and _uuid(notice.entity_id):
        return {'sale_id': str(_uuid(notice.entity_id)), **(from_path or {'target': 'sale'})}
    if notice.entity_type == 'inventory_item' and _uuid(notice.entity_id):
        return {'item_id': str(_uuid(notice.entity_id)), 'target': 'product'}
    return from_path


def authoring_value(body, context=None):
    values = body.model_dump(mode='json', exclude={'request_id', 'expected_version', 'context'})
    values['user_ids'] = sorted(set(str(identity) for identity in body.user_ids))
    values['scheduled_at'] = aware(body.scheduled_at).astimezone(timezone.utc).isoformat() if body.scheduled_at else None
    values['context'] = context_value(body.context if context is None else context, body.action_path)
    return values


def matches_request(snapshot, authored):
    original = snapshot.get('authoring')
    if isinstance(original, dict):
        return original == authored
    # Retry of a pre-context request remains idempotent; it must not adopt a new reference.
    return not authored['context'] and all(snapshot.get(key) == value for key, value in authored.items() if key != 'context')


def inbox_sale_visibility(db, user):
    if not own_sales(user):
        return True
    sale_id_text = func.lower(func.replace(cast(PdvSale.id, String), '-', ''))
    allowed_ids = db.query(sale_id_text).filter(PdvSale.vendedor_id == user.id, PdvSale.deleted_at.is_(None))
    entity_sale = func.coalesce(Notification.entity_type == 'pdv_sale', False)
    entity_allowed = func.lower(func.replace(Notification.entity_id, '-', '')).in_(allowed_ids)
    # Before explicit contexts existed, the only reference could be an internal
    # sale URL. Guard those legacy rows in SQL too, before counts/pagination.
    # Ambiguous/encoded legacy query parameters fail closed. Current generated
    # links have one canonical sale_id; substring matching could accept another
    # seller's sale plus a second parameter pointing to an owned sale.
    legacy_sale = Notification.action_path.startswith('/vendas-pdv?', autoescape=True)
    normalized_path = func.lower(func.replace(Notification.action_path, '-', ''))
    legacy_allowed = db.query(PdvSale.id).filter(PdvSale.vendedor_id == user.id, PdvSale.deleted_at.is_(None),
        normalized_path == literal('/vendaspdv?sale_id=') + sale_id_text).exists()
    return and_(or_(~entity_sale, entity_allowed), or_(~func.coalesce(legacy_sale, False), legacy_allowed))


def notification_allowed(db, user, notice):
    if notice.action_path:
        path = urlsplit(notice.action_path)
        if path.path == '/vendas-pdv' and path.query:
            linked = path_context(notice.action_path)
            if not linked or not linked.get('sale_id'):
                return False
            canonical = '/vendaspdv?sale_id=' + uuid.UUID(linked['sale_id']).hex
            if own_sales(user) and notice.action_path.lower().replace('-', '') != canonical:
                return False
    context = notice_context(notice)
    if not context or not context.get('sale_id'):
        return True
    row = db.query(PdvSale.vendedor_id, PdvSale.deleted_at).filter(PdvSale.id == _uuid(context['sale_id'])).first()
    return bool(row and (is_owner(user) or row.deleted_at is None) and
                (not own_sales(user) or row.vendedor_id == user.id))


def sale_metadata(db, sale_id, *, required=True):
    row = db.query(PdvSale.id, PdvSale.vendedor_id, PdvSale.created_at, PdvSale.status,
                   Usuario.nome.label('seller_name')).outerjoin(Usuario, Usuario.id == PdvSale.vendedor_id)\
        .filter(PdvSale.id == sale_id, PdvSale.deleted_at.is_(None)).first()
    if required and row is None:
        raise HTTPException(404, 'Venda não encontrada ou removida da listagem.')
    return row


def validate_sale_audience(sale, users):
    if any(own_sales(user) and user.id != sale.vendedor_id for user in users):
        raise HTTPException(400, 'Uma venda pessoal pode ser notificada somente ao seu vendedor e aos usuários autorizados a consultar o geral.')


def prepare_manual(db, body, users, moment, *, context=None):
    authored = authoring_value(body, context)
    linked = authored['context']
    sale = sale_metadata(db, _uuid(linked['sale_id'])) if linked and linked.get('sale_id') else None
    if sale:
        validate_sale_audience(sale, users)
    product = None
    if linked and linked.get('item_id'):
        product = db.query(Item.id).filter(Item.id == _uuid(linked['item_id']), Item.deleted_at.is_(None), Item.is_active.is_(True)).first()
        if not product:
            raise HTTPException(404, 'Produto de referência não encontrado ou inativo.')
        # Explicit reference, not evidence that the product belongs to the sale.
    fields = {match[1] for value in (body.title, body.body) for match in MANUAL_TOKEN.finditer(value) if match[1] in TEMPLATE_VARIABLES}
    tracking_code = tracking_code_from_path(body.action_path) if not linked else None
    tracking = find_tracking_metadata(db, tracking_code)
    if 'sale_code' in fields and sale is None:
        raise HTTPException(400, 'Selecione uma venda real para preencher {sale_code}.')
    if fields.intersection({'tracking_code', 'cliente_username'}) and tracking is None:
        raise HTTPException(400, 'Escolha o atalho Rastreio e informe um código de rastreio cadastrado para preencher {tracking_code}/{cliente_username}.')
    if 'status' in fields and sale is None and tracking is None:
        raise HTTPException(400, 'Este modelo precisa de uma venda ou de um rastreio cadastrado para preencher {status}.')
    local = moment.astimezone(BRT)
    values = {'user_name': sale.seller_name if sale and sale.seller_name else users[0].nome if len(users) == 1 else 'equipe',
              'cliente_username': tracking_recipient_name(db, tracking) if tracking else 'destinatário não informado',
              'sale_code': ticket_code(sale.id) if sale else '', 'tracking_code': tracking.codigo_rastreio if tracking else '',
              'status': {'completed': 'concluída', 'cancelled': 'cancelada', 'partially_refunded': 'devolução parcial',
                         'refunded': 'estornada'}.get(sale.status, sale.status) if sale else TRACKING_LABELS.get(getattr(tracking.status, 'value', tracking.status), '') if tracking else '',
              'date': local.strftime('%d/%m/%Y'), 'time': local.strftime('%H:%M')}
    payload = body.model_dump(exclude={'request_id', 'expected_version', 'context'})
    def render(value):
        return MANUAL_TOKEN.sub(lambda match: '{' if match[0] == '{{' else '}' if match[0] == '}}'
                                else values.get(match[1], match[0]), value).strip()
    payload.update(title=render(body.title), body=render(body.body))
    if not payload['title'] or not payload['body']:
        raise HTTPException(400, 'O modelo resultou em uma mensagem vazia. Complete o título e o texto.')
    if len(payload['title']) > 120 or len(payload['body']) > 2000:
        raise HTTPException(400, 'A mensagem preenchida ultrapassa o limite de título ou texto. Encurte o modelo.')
    if linked:
        payload['action_path'] = ('/inventory?item_id=' + linked['item_id'] if linked['target'] == 'product'
                                  else '/vendas-pdv?sale_id=' + linked['sale_id'])
    NotificationFields(**{key: value for key, value in payload.items() if key not in {'user_ids', 'scheduled_at'}})
    payload.update(entity_type='pdv_sale' if sale else 'inventory_item' if product else 'tracking' if tracking else None,
                   entity_id=str(sale.id) if sale else str(product.id) if product else str(tracking.id) if tracking else None)
    return payload, {'authoring': authored, 'context': linked}


def current_snapshots(db, notices):
    if not notices:
        return {}
    conditions = [and_(NotificationRevision.notification_id == notice.id, NotificationRevision.version == notice.version) for notice in notices]
    return {row.notification_id: row.snapshot for row in db.query(NotificationRevision).filter(or_(*conditions)).all()}


def presented_fields(db, notices, names=None):
    """Resolve broken legacy placeholders only for display, never rewrite history."""
    legacy = [notice for notice in notices if KNOWN_VARIABLE.search(notice.title) or KNOWN_VARIABLE.search(notice.body)]
    output = {notice.id: {'title': notice.title, 'body': notice.body} for notice in notices}
    snapshots = current_snapshots(db, legacy)
    # New manual revisions already store rendered text. A deliberately escaped
    # {{sale_code}} must stay literal, including after editing or cancellation.
    legacy = [notice for notice in legacy if not isinstance(snapshots.get(notice.id, {}).get('authoring'), dict)]
    if not legacy:
        return output
    if names is None:
        names = {}
        for notice_id, name in db.query(NotificationRecipient.notification_id, Usuario.nome).join(Usuario, Usuario.id == NotificationRecipient.user_id)\
                .filter(NotificationRecipient.notification_id.in_([notice.id for notice in legacy]), NotificationRecipient.removed_at.is_(None)).all():
            names.setdefault(notice_id, []).append(name)
    source = {notice.id: notice_context(notice) for notice in legacy}
    sale_ids = {_uuid(value['sale_id']) for value in source.values() if value and value.get('sale_id')}
    sales = {row.id: row for row in db.query(PdvSale.id, PdvSale.vendedor_id, PdvSale.status, Usuario.nome.label('seller_name'))
             .outerjoin(Usuario, Usuario.id == PdvSale.vendedor_id).filter(PdvSale.id.in_(sale_ids), PdvSale.deleted_at.is_(None)).all()} if sale_ids else {}
    tracking_ids = {_uuid(notice.entity_id) for notice in legacy if notice.entity_type == 'tracking' and _uuid(notice.entity_id)}
    tracking_codes = {code for notice in legacy if (code := tracking_code_from_path(notice.action_path))}
    tracking_rows = tracking_metadata_query(db).filter(or_(Rastreamento.id.in_(tracking_ids), Rastreamento.codigo_rastreio.in_(tracking_codes))).all() if tracking_ids or tracking_codes else []
    tracking_by_id = {row.id: row for row in tracking_rows}
    tracking_by_code = {row.codigo_rastreio: row for row in tracking_rows}
    for notice in legacy:
        context = source[notice.id]
        sale = sales.get(_uuid(context['sale_id'])) if context and context.get('sale_id') else None
        tracking = tracking_by_id.get(_uuid(notice.entity_id)) if notice.entity_type == 'tracking' else tracking_by_code.get(tracking_code_from_path(notice.action_path))
        recipients = names.get(notice.id, [])
        local = aware(notice.created_at).astimezone(BRT)
        values = {'user_name': sale.seller_name if sale and sale.seller_name else recipients[0] if len(recipients) == 1 else 'equipe',
                  'sale_code': ticket_code(sale.id) if sale else 'venda não vinculada',
                  'cliente_username': tracking_recipient_name(db, tracking) if tracking else 'destinatário não informado',
                  'tracking_code': tracking.codigo_rastreio if tracking else 'rastreio não vinculado',
                  'status': sale.status if sale else TRACKING_LABELS.get(getattr(tracking.status, 'value', tracking.status), '') if tracking else 'situação não vinculada',
                  'date': local.strftime('%d/%m/%Y'), 'time': local.strftime('%H:%M')}
        output[notice.id] = {field: KNOWN_VARIABLE.sub(lambda match: values[match[1]], getattr(notice, field))
                             for field in ('title', 'body')}
    return output
