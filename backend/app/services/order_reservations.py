"""Transactional reservations: physical stock stays put until a single PDV sale.

Lock order: request key -> customer identity lock -> order -> sorted products -> customer -> printer.
No provider payments or printer I/O; callers commit all effects together.
"""
import hashlib
import json
import uuid
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import defer

from ..config import settings
from ..models.pedido import Pedido, PedidoStatus
from ..models.pedido_reserva import PedidoItem, PedidoPayment, PedidoOperation
from ..models.pdv import PdvSale
from ..models.inventory import Item
from ..models.usuario import UsuarioRole
from ..schemas.pdv import PdvCustomerSelection, PdvPaymentCreate, PdvSaleCreate, PdvSaleItemCreate
from .access_policy import own_sales, is_owner
from . import pdv_customers
from .pdv_payments import validate_payment
from .pdv_usd import current_rate
from .user_audit import bind_actor, record
from .business_time import stored_instant

MONEY_LIMIT = Decimal('9999999999999.99')
PAYMENT_FIELDS = ('method', 'currency', 'amount_original', 'exchange_rate', 'amount_gs',
                  'card_fee_gs', 'card_fee_percent', 'cambista_id', 'reference')


def permitted(user):
    if not user.ativo or user.role not in (UsuarioRole.ADMIN, UsuarioRole.GERENTE, UsuarioRole.VENDEDOR):
        raise HTTPException(403, 'Esta conta não pode operar pedidos com reserva.')


def authorized_order(db, order_id, user, *, lock=False):
    permitted(user)
    query = db.query(Pedido).filter(Pedido.id == order_id, Pedido.commerce_status.isnot(None))
    if own_sales(user):
        query = query.filter(Pedido.vendedor_id == user.id)
    if lock:
        query = query.with_for_update().populate_existing()
    order = query.first()
    if not order:
        raise HTTPException(404, 'Pedido reservado não encontrado para esta conta.')
    return order


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def _date(db, value):
    return stored_instant(value, db).isoformat() if value else None


def detail(db, order, user=None):
    if user is not None:
        order = authorized_order(db, order, user, lock=True)
    paid = _money(order.paid_gs)
    product_rows = db.query(Item.id, Item.available_loja, Item.available_deposito,
                            Item.updated_at, Item.image_data.isnot(None).label('has_image')).filter(
        Item.id.in_({line.item_id for line in order.reserved_items})).all() if order.reserved_items else []
    product_info = {row.id: row for row in product_rows}
    return {
        'id': str(order.id), 'numero_pedido': order.numero_pedido,
        'commerce_status': order.commerce_status, 'commerce_version': order.commerce_version,
        'pdv_cliente_id': str(order.pdv_cliente_id),
        'cliente_id': str(order.cliente_id) if order.cliente_id else None,
        'cliente_nome': order.cliente_nome, 'vendedor_id': str(order.vendedor_id),
        'vendedor_nome': order.vendedor.nome if order.vendedor else None,
        'reserved_at': _date(db, order.reserved_at), 'created_at': _date(db, order.created_at),
        'usd_rate_gs': str(order.usd_rate_gs), 'subtotal_gs': str(order.subtotal_gs),
        'desconto_gs': str(order.desconto_gs), 'total_gs': str(order.total_gs),
        'paid_gs': str(paid), 'balance_gs': str(max(Decimal(0), _money(order.total_gs) - paid)),
        'change_gs': str(max(Decimal(0), sum((p.amount_gs for p in order.reservation_payments if not p.reversed_at), Decimal(0)) - _money(order.total_gs))) if order.commerce_status == 'completed' else '0.00',
        'sale_id': str(order.sale_id) if order.sale_id else None, 'notas': order.commerce_notes,
        'items': [dict(id=str(line.id), item_id=str(line.item_id), item_name=line.item_name,
                       item_sku=line.item_sku, item_size=line.item_size, item_color=line.item_color,
                       item_category=line.item_category, location=line.location, quantity=line.quantity,
                       unit_price_gs=str(line.unit_price_gs), total_gs=str(line.total_gs),
                       available_loja=product_info[line.item_id].available_loja if line.item_id in product_info else None,
                       available_deposito=product_info[line.item_id].available_deposito if line.item_id in product_info else None,
                       has_image=bool(product_info[line.item_id].has_image) if line.item_id in product_info else False,
                       updated_at=_date(db, product_info[line.item_id].updated_at) if line.item_id in product_info else None)
                  for line in order.reserved_items],
        'payments': [dict(id=str(payment.id), **{key: str(getattr(payment, key)) if key in (
            'amount_original', 'exchange_rate', 'amount_gs', 'card_fee_gs', 'card_fee_percent')
            else str(getattr(payment, key)) if key == 'cambista_id' and getattr(payment, key)
            else getattr(payment, key) for key in PAYMENT_FIELDS}, created_at=_date(db, payment.created_at),
            created_by=str(payment.created_by), reversed_at=_date(db, payment.reversed_at),
            reversal_reason=payment.reversal_reason)
            for payment in order.reservation_payments],
    }


def _fingerprint(operation, order_id, body):
    data = {'operation': operation, 'order_id': str(order_id or ''),
            'body': body.model_dump(mode='json', exclude={'request_id'})}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _request(db, user, operation, order_id, body):
    permitted(user)
    if not body.confirm:
        raise HTTPException(422, 'Confirme a operação antes de continuar.')
    # A lost HTTP response is retried with the same key. Serialize absent rows,
    # too; SELECT FOR UPDATE alone cannot protect first-time inserts.
    if db.bind.dialect.name == 'postgresql':
        key = int.from_bytes(hashlib.sha256(b'order-request:' + body.request_id.bytes).digest()[:8], 'big', signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})
    fingerprint = _fingerprint(operation, order_id, body)
    previous = db.get(PedidoOperation, body.request_id)
    if previous and (previous.actor_id != user.id or previous.operation != operation or previous.fingerprint != fingerprint):
        raise HTTPException(409, 'Esta confirmação já foi utilizada em outra operação. Confira os dados.')
    from .address_book import lock_addresses
    lock_addresses(db)
    return previous, fingerprint


def _writable(order, version):
    if order.commerce_status != 'reserved':
        raise HTTPException(409, 'Este pedido já foi concluído ou cancelado. Seu histórico foi preservado.')
    if version is None or version != order.commerce_version:
        raise HTTPException(409, 'O pedido mudou em outro aparelho. Atualize e confira antes de confirmar.')


def _record(db, order, user, body, operation, fingerprint, before):
    db.flush()
    after = detail(db, order)
    if hasattr(body, 'reason'):
        after['reason'] = body.reason
    db.add(PedidoOperation(id=body.request_id, pedido_id=order.id, actor_id=user.id,
                          operation=operation, fingerprint=fingerprint, before=before, after=after))
    bind_actor(db, user)
    record(db, f'order_{operation}', 'pedidos', entity='pedidos', entity_id=str(order.id),
           changes={'order_id': str(order.id), 'version': order.commerce_version,
                    'status': order.commerce_status, 'total_gs': str(order.total_gs),
                    'paid_gs': str(order.paid_gs), 'items': sum(line.quantity for line in order.reserved_items)})
    db.flush()
    return after


def _quantities(lines):
    quantities = defaultdict(int)
    for line in lines:
        quantities[(line.item_id, line.location)] += line.quantity
    return quantities


def _change_reservations(db, old_lines, new_lines):
    old, new = _quantities(old_lines), _quantities(new_lines)
    ids = {item_id for item_id, _ in set(old) | set(new)}
    rows = db.query(Item).options(defer(Item.image_data)).filter(Item.id.in_(ids)).order_by(Item.id).populate_existing().with_for_update().all() if ids else []
    products = {item.id: item for item in rows}
    if len(products) != len(ids):
        raise HTTPException(409, 'Um produto do pedido não existe. Confira os itens antes de continuar.')
    for item in rows:
        if any((item.id, location) in new for location in ('loja', 'deposito')) and (not item.is_active or item.deleted_at):
            raise HTTPException(409, f'O produto "{item.name}" está inativo ou excluído.')
        balances = (item.current_stock, item.stock_loja, item.stock_deposito)
        if any(value is None or value < 0 for value in balances) or item.current_stock != item.stock_loja + item.stock_deposito:
            raise HTTPException(409, f'Confira os saldos de "{item.name}" antes de alterar a reserva.')
        for location in ('loja', 'deposito'):
            previous = old.get((item.id, location), 0)
            requested = new.get((item.id, location), 0)
            reserved = getattr(item, f'reserved_{location}') or 0
            physical = getattr(item, f'stock_{location}')
            if reserved < previous or reserved > physical:
                raise HTTPException(409, 'As reservas do produto precisam de conferência. Nenhuma alteração foi aplicada.')
            updated = reserved - previous + requested
            if updated > physical:
                raise HTTPException(409, f'Saldo disponível insuficiente em {location} para "{item.name}": {physical - reserved + previous}. Há peças reservadas para outros pedidos.')
            setattr(item, f'reserved_{location}', updated)
    db.flush()
    return products


def _priced_lines(body):
    if len({(line.item_id, line.location) for line in body.items}) != len(body.items):
        raise HTTPException(422, 'Consolide a quantidade do mesmo produto/local em uma única linha.')
    subtotal = sum((_money(line.unit_price_gs * line.quantity) for line in body.items), Decimal(0))
    total = subtotal - body.desconto_gs
    if total < 0 or subtotal > MONEY_LIMIT or total / body.usd_rate_gs > Decimal('99999999.99'):
        raise HTTPException(422, 'Confira o desconto e os limites do valor do pedido.')
    return subtotal, total


def _assign_lines(order, body, products):
    order.reserved_items = [PedidoItem(
        item_id=line.item_id, position=position, item_name=products[line.item_id].name,
        item_sku=products[line.item_id].inventory_code or products[line.item_id].sku_internal,
        item_size=products[line.item_id].size, item_color=products[line.item_id].color,
        item_category=products[line.item_id].category,
        quantity=line.quantity, location=line.location, unit_price_gs=line.unit_price_gs,
        total_gs=_money(line.unit_price_gs * line.quantity),
    ) for position, line in enumerate(body.items)]


def create(db, body, user):
    previous, fingerprint = _request(db, user, 'reserve', None, body)
    if previous:
        return detail(db, authorized_order(db, previous.pedido_id, user))
    subtotal, total = _priced_lines(body)
    rate = current_rate(db, body.usd_rate_gs)
    products = _change_reservations(db, [], body.items)
    customer = pdv_customers.select(db, PdvCustomerSelection(source='pdv', id=body.pdv_cliente_id), user)
    # Unique order identity also serves as its durable scan/lookup key.
    order_id = uuid.uuid4()
    order = Pedido(id=order_id, numero_pedido=f'PED-{settings.now().year}-{order_id.hex[:10].upper()}',
        descricao=' · '.join(f'{line.quantity} × {products[line.item_id].name}' for line in body.items),
        valor_total=_money(total / rate), moeda='U$', status=PedidoStatus.PROCESSANDO,
        cliente_id=customer.cadastro_cliente_id, cliente_nome=customer.nome,
        cliente_telefone=customer.telefone, cliente_email=customer.email,
        created_by=user.id, vendedor_id=user.id, pdv_cliente_id=customer.id,
        commerce_status='reserved', commerce_version=1, reserved_at=settings.now(),
        usd_rate_gs=rate, subtotal_gs=subtotal, desconto_gs=body.desconto_gs,
        total_gs=total, paid_gs=Decimal(0), commerce_notes=body.notas)
    _assign_lines(order, body, products)
    db.add(order)
    return _record(db, order, user, body, 'reserve', fingerprint, None)


def update(db, order_id, body, user):
    previous, fingerprint = _request(db, user, 'edit', order_id, body)
    order = authorized_order(db, order_id, user, lock=True)
    if previous:
        return detail(db, order)
    _writable(order, body.expected_version)
    before = detail(db, order)
    subtotal, total = _priced_lines(body)
    if Decimal(body.usd_rate_gs) != order.usd_rate_gs:
        raise HTTPException(409, 'O pedido conserva seu câmbio original. Atualize a tela para manter a cotação da reserva.')
    if total < order.paid_gs:
        raise HTTPException(409, 'O novo total é menor que o valor recebido. Registre a devolução do pagamento antes de reduzir o pedido.')
    if order.paid_gs > 0 and body.pdv_cliente_id != order.pdv_cliente_id:
        raise HTTPException(409, 'Pedido com pagamentos não pode trocar de cliente.')
    products = _change_reservations(db, order.reserved_items, body.items)
    customer = pdv_customers.select(db, PdvCustomerSelection(source='pdv', id=body.pdv_cliente_id), user)
    if customer.cadastro_cliente_id != order.cliente_id:
        from .customer_links import validate_order_customer
        validate_order_customer(db, order, customer.cadastro_cliente_id)
    order.pdv_cliente_id, order.cliente_id, order.cliente_nome = customer.id, customer.cadastro_cliente_id, customer.nome
    order.cliente_telefone, order.cliente_email = customer.telefone, customer.email
    _assign_lines(order, body, products)
    order.subtotal_gs, order.desconto_gs, order.total_gs = subtotal, body.desconto_gs, total
    order.valor_total = _money(total / order.usd_rate_gs)
    order.descricao = ' · '.join(f'{line.quantity} × {products[line.item_id].name}' for line in body.items)
    order.commerce_notes = body.notas
    order.commerce_version += 1
    return _record(db, order, user, body, 'edit', fingerprint, before)


def _payment(db, payment):
    values = validate_payment(payment.model_dump())
    if values['method'] == 'fiado' or values['amount_gs'] <= 0:
        raise HTTPException(422, 'Informe um pagamento recebido positivo. Fiado não quita uma reserva.')
    if values.get('reference') and len(values['reference']) > 200:
        raise HTTPException(422, 'A referência do pagamento deve ter até 200 caracteres.')
    if values.get('cambista_id'):
        from ..models.cambista import Cambista
        if not db.get(Cambista, values['cambista_id']):
            raise HTTPException(422, 'Cambista não encontrado.')
    return values


def add_payment(db, order_id, body, user):
    previous, fingerprint = _request(db, user, 'payment', order_id, body)
    order = authorized_order(db, order_id, user, lock=True)
    if previous:
        return detail(db, order)
    _writable(order, body.expected_version)
    before = detail(db, order)
    values = _payment(db, body.payment)
    if order.paid_gs + values['amount_gs'] > order.total_gs:
        raise HTTPException(422, 'O pagamento ultrapassa o saldo do pedido. Registre somente o valor recebido para esta reserva.')
    if len(order.reservation_payments) >= 200:
        raise HTTPException(422, 'Limite de 200 lançamentos por pedido atingido. Confira o histórico.')
    order.reservation_payments.append(PedidoPayment(created_by=user.id, **values))
    order.paid_gs += values['amount_gs']
    order.commerce_version += 1
    return _record(db, order, user, body, 'payment', fingerprint, before)


def reverse_payment(db, order_id, payment_id, body, user):
    if not is_owner(user):
        raise HTTPException(403, 'Somente Lucas pode registrar a devolução de um pagamento.')
    previous, fingerprint = _request(db, user, f'refund:{payment_id}', order_id, body)
    order = authorized_order(db, order_id, user, lock=True)
    if previous:
        return detail(db, order)
    _writable(order, body.expected_version)
    payment = next((p for p in order.reservation_payments if p.id == payment_id), None)
    if not payment or payment.reversed_at:
        raise HTTPException(409, 'Pagamento não encontrado ou já devolvido. Confira o histórico.')
    before = detail(db, order)
    payment.reversed_at, payment.reversed_by, payment.reversal_reason = settings.now(), user.id, body.reason
    order.paid_gs -= payment.amount_gs
    order.commerce_version += 1
    return _record(db, order, user, body, f'refund:{payment_id}', fingerprint, before)


def cancel(db, order_id, body, user):
    previous, fingerprint = _request(db, user, 'cancel', order_id, body)
    order = authorized_order(db, order_id, user, lock=True)
    if previous:
        return detail(db, order)
    _writable(order, body.expected_version)
    if order.paid_gs > 0:
        raise HTTPException(409, 'Este pedido tem pagamentos recebidos. Lucas deve conferir a devolução fora do ERP e registrá-la antes do cancelamento.')
    before = detail(db, order)
    _change_reservations(db, order.reserved_items, [])
    order.commerce_status, order.status = 'cancelled', PedidoStatus.CANCELADO
    order.commerce_version += 1
    return _record(db, order, user, body, 'cancel', fingerprint, before)


def checkout(db, order_id, body, user):
    previous, fingerprint = _request(db, user, 'checkout', order_id, body)
    order = authorized_order(db, order_id, user, lock=True)
    if previous:
        if not order.sale_id:
            raise HTTPException(409, 'A conclusão do pedido precisa de conferência.')
        return db.get(PdvSale, order.sale_id)
    _writable(order, body.expected_version)
    before = detail(db, order)
    payments = [_payment(db, payment) for payment in body.payments]
    deposits = [p for p in order.reservation_payments if not p.reversed_at]
    if sum((p.amount_gs for p in deposits), Decimal(0)) != order.paid_gs:
        raise HTTPException(409, 'O histórico dos pagamentos precisa de conferência antes de concluir.')
    # A reservation is never discharged as fiado. Whole stored deposits are
    # credited exactly once and retain their original currency/rate/date.
    combined = [{key: getattr(p, key) for key in PAYMENT_FIELDS} for p in deposits] + payments
    from ..api.endpoints.pdv import create_sale_record
    sale_body = PdvSaleCreate(
        vendedor_id=order.vendedor_id, cliente_id=order.pdv_cliente_id, cliente_nome=order.cliente_nome,
        usd_rate_gs=order.usd_rate_gs, desconto_gs=order.desconto_gs, print_receipt=body.print_receipt,
        notas=order.commerce_notes,
        items=[PdvSaleItemCreate(item_id=i.item_id, item_name=i.item_name, item_sku=i.item_sku,
            item_size=i.item_size, item_color=i.item_color, item_category=i.item_category,
            quantity=i.quantity, unit_price_gs=i.unit_price_gs, location=i.location) for i in order.reserved_items],
        payments=[PdvPaymentCreate(**values) for values in combined],
    )
    _change_reservations(db, order.reserved_items, [])
    sale = create_sale_record(db, sale_body, user, frozen_usd_rate=order.usd_rate_gs)
    # create_sale_record inserts in combined order; identify rows explicitly by
    # SQLAlchemy's pending identity data rather than relying on unordered SELECT.
    sale_payments = list(sale.payments)
    unmatched = list(sale_payments)
    for deposit in deposits:
        matching = next((p for p in unmatched if all(getattr(p, key) == getattr(deposit, key) for key in PAYMENT_FIELDS)), None)
        if matching is None:
            raise HTTPException(409, 'Não foi possível conciliar o pagamento do pedido. Nenhuma venda foi concluída.')
        unmatched.remove(matching)
        matching.created_at = deposit.created_at
        deposit.sale_payment_id = matching.id
    # The order's ledger remains complete after checkout. Cash overpayment is
    # represented by the actual amount and explicit change, not hidden deposits.
    for values in payments:
        matching = next((p for p in unmatched if all(getattr(p, key) == values.get(key) for key in PAYMENT_FIELDS)), None)
        if matching is None:
            raise HTTPException(409, 'Não foi possível registrar o pagamento final. Nenhuma venda foi concluída.')
        unmatched.remove(matching)
        order.reservation_payments.append(PedidoPayment(created_by=user.id, sale_payment_id=matching.id,
                                                        created_at=matching.created_at, **values))
    order.sale_id, order.commerce_status = sale.id, 'completed'
    order.paid_gs = order.total_gs
    order.commerce_version += 1
    _record(db, order, user, body, 'checkout', fingerprint, before)
    return sale
