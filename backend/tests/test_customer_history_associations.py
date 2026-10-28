"""Historical associations require corroborated identity, not a coincident name."""
import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from test_assistant import setup
from test_address_manager import env
from app.models import Cliente, Usuario, Pedido, Rastreamento
from app.models.access import AuditEvent
from app.models.address_book import SavedAddress
from app.models.pdv import PdvCliente, PdvSale
from app.services.customer_identity import find_customer
from app.services.customer_reconciliation import (
    preview_customer_links, apply_customer_links, auto_link_pdv_customer, auto_link_tracking,
)


def seed(db, uid):
    customer = Cliente(nome='João Ávila', telefone='+595972123456', email='joao@example.test',
        endereco='Rua Central, 40, São Paulo, SP, 01001000, BR')
    db.add(customer); db.flush()
    address = SavedAddress(label='Casa', created_by=uid, data={'pais':'BR','nome':'JOAO AVILA',
        'endereco':'Rua Central','numero':'40','cidade':'São Paulo','estado':'SP','cep':'01001000'})
    order = Pedido(numero_pedido='FIXTURE-1', descricao='Snapshot intacto', valor_total=Decimal('123.45'),
        cliente_nome='João Ávila', cliente_telefone='0972123456', endereco_entrega='Outro endereço preservado')
    account = PdvCliente(nome='JOAO AVILA', email='joao@example.test', saldo_fiado_gs=Decimal('98.50'))
    db.add_all([address, order, account]); db.flush()
    parcel = Rastreamento(codigo_rastreio='BRTESTE001', pedido_id=order.id, destinatario='Texto original')
    direct = Rastreamento(codigo_rastreio='BRTESTE002', destinatario='João Ávila', destino=customer.endereco)
    unlinked = Rastreamento(codigo_rastreio='BRTESTE003', destinatario='João Ávila')
    sale = PdvSale(cliente_id=account.id, cliente_nome='Snapshot da compra', total_gs=Decimal('321.20'))
    db.add_all([parcel, direct, unlinked, sale]); db.flush()
    return customer, address, order, account, parcel, direct, unlinked, sale


def test_preview_is_read_only_and_apply_preserves_snapshots_balances_and_aliases(env):
    factory, _, uid, _ = env
    with factory() as db:
        customer, address, order, account, parcel, direct, unlinked, sale = seed(db, uid)
        alias = SavedAddress(label='Endereço antigo', created_by=uid, data={}, active=False, merged_into_id=address.id)
        db.add(alias); db.flush()
        statements = []
        def log(conn, cursor, statement, parameters, context, many):
            statements.append(statement.strip().split()[0].upper())
        event.listen(db.bind, 'before_cursor_execute', log)
        try:
            plan = preview_customer_links(db, customer)
        finally:
            event.remove(db.bind, 'before_cursor_execute', log)
        assert not {'INSERT', 'UPDATE', 'DELETE'} & set(statements)
        assert plan['counts'] == {'addresses':1, 'orders':1, 'tracking':2, 'pdv_accounts':1}
        assert not plan['limited'] and plan['scanned'] == 6
        assert set(plan['items'][0]) == {'kind','id','label','reason'}
        assert not address.cliente_id and not order.cliente_id and not account.cadastro_cliente_id
        before = (address.data.copy(), order.descricao, order.endereco_entrega, order.valor_total,
                  parcel.destinatario, account.saldo_fiado_gs, sale.cliente_nome, sale.total_gs)
        result = apply_customer_links(db, customer, plan['token'], db.get(Usuario, uid))
        assert result['linked'] == plan['counts'] and not result['already_applied']
        assert address.cliente_id == order.cliente_id == parcel.cliente_id == direct.cliente_id == customer.id
        assert account.cadastro_cliente_id == customer.id and unlinked.cliente_id is None
        assert alias.merged_into_id == address.id and alias.cliente_id is None
        assert before == (address.data, order.descricao, order.endereco_entrega, order.valor_total,
                          parcel.destinatario, account.saldo_fiado_gs, sale.cliente_nome, sale.total_gs)
        assert apply_customer_links(db, customer, plan['token'], db.get(Usuario, uid))['already_applied']
        assert db.query(AuditEvent).filter_by(action='customer_history_reconciled').count() == 1
        empty = preview_customer_links(db, customer)
        assert not any(empty['counts'].values())


def test_homonyms_need_full_address_or_contact_and_conflicts_never_choose_a_person(env):
    factory, _, uid, _ = env
    with factory() as db:
        first = Cliente(nome='Ana Corrêa', endereco='Rua Azul, 12, Centro', telefone='+5511999991234', cpf='12345678909')
        second = Cliente(nome='Ana Correa', endereco='Rua Verde, 33, Centro', telefone='+5511999994321')
        db.add_all([first, second]); db.flush()
        data = {'nome':'ANA CORREA', 'endereco_livre':'Rua Azul, 12, Centro'}
        matched, reason, _ = find_customer(db, data)
        assert matched.id == first.id and reason == 'name_address'
        assert find_customer(db, {**data, 'telefone':second.telefone})[0].id == second.id
        # Explicit contradictory documents override an otherwise matching address.
        assert find_customer(db, {**data, 'cpf':'98765432100'})[0] is None
        parcel = Rastreamento(codigo_rastreio='ANATEST1', destinatario='Ana Correa', destino=first.endereco)
        named = Rastreamento(codigo_rastreio='ANATEST2', destinatario='Ana Correa')
        db.add_all([parcel, named]); db.flush()
        plan = preview_customer_links(db, first)
        assert plan['counts']['tracking'] == 1 and plan['items'][0]['id'] == str(parcel.id)
        assert auto_link_tracking(db, parcel) and parcel.cliente_id == first.id
        assert not auto_link_tracking(db, named)


def test_stale_plan_rejects_changed_identity_and_keeps_explicit_links(env):
    factory, _, uid, _ = env
    with factory() as db:
        customer, address, order, account, parcel, direct, _, _ = seed(db, uid)
        other = Cliente(nome='Outra Pessoa'); db.add(other); db.flush()
        plan = preview_customer_links(db, customer)
        order.cliente_id = other.id; db.flush()
        with pytest.raises(HTTPException, match='409'):
            apply_customer_links(db, customer, plan['token'], db.get(Usuario, uid))
        assert address.cliente_id is None and account.cadastro_cliente_id is None
        assert direct.cliente_id is None and parcel.cliente_id is None and order.cliente_id == other.id
        fresh = preview_customer_links(db, customer)
        assert fresh['counts']['orders'] == 0 and fresh['counts']['tracking'] == 1


def test_unknown_names_short_names_city_only_and_financial_accounts_remain_separate(env):
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome='Mesmo Nome', endereco='Asunción')
        short = Cliente(nome='Ana', telefone='+5511999991234')
        account = PdvCliente(nome='Mesmo Nome', saldo_fiado_gs=Decimal('90'))
        db.add_all([customer, short, account]); db.flush()
        short_account = PdvCliente(nome='Ana', telefone=short.telefone)
        db.add_all([Pedido(numero_pedido='WEAK', descricao='Fixture', valor_total=10, cliente_nome='Mesmo Nome'),
            Rastreamento(codigo_rastreio='WEAK1', destinatario='Mesmo Nome', destino='Asunción'),
            short_account])
        db.flush()
        assert not any(preview_customer_links(db, customer)['counts'].values())
        assert not any(preview_customer_links(db, short)['counts'].values())
        assert not auto_link_pdv_customer(db, short_account)
        assert not auto_link_pdv_customer(db, account) and account.saldo_fiado_gs == Decimal('90')
        account.email = 'other@example.test'; customer.email = account.email; db.flush()
        assert auto_link_pdv_customer(db, account) and account.cadastro_cliente_id == customer.id
        original = account.cadastro_cliente_id
        assert not auto_link_pdv_customer(db, account) and account.cadastro_cliente_id == original


def test_bounded_preview_exposes_partial_scan_and_refuses_truncated_identity_directory(env, monkeypatch):
    from app.services import customer_reconciliation as service
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome='Pessoa Teste', telefone='+595972123456'); db.add(customer); db.flush()
        db.add_all([Pedido(numero_pedido=f'BATCH-{index}', descricao='Fixture', valor_total=10,
            cliente_nome=customer.nome, cliente_telefone=customer.telefone) for index in range(3)])
        db.flush()
        plan = preview_customer_links(db, customer, limit=1)
        assert plan['limited'] and plan['limit'] == 1 and plan['counts']['orders'] == 1
        apply_customer_links(db, customer, plan['token'], db.get(Usuario, uid), limit=1)
        assert preview_customer_links(db, customer, limit=1)['counts']['orders'] == 1
        monkeypatch.setattr(service, 'CUSTOMER_REVIEW_LIMIT', 1)
        db.add(Cliente(nome='Pessoa Teste', telefone=customer.telefone)); db.flush()
        blocked = preview_customer_links(db, customer)
        assert blocked['limited'] and not any(blocked['counts'].values()) and not blocked['items']


def test_reviewed_customer_alias_name_can_match_strong_contact_but_never_claim_other_links(env):
    factory, _, uid, _ = env
    with factory() as db:
        principal = Cliente(nome='Ana Souza', telefone='+595972123456')
        other = Cliente(nome='Ana Corrêa', telefone='+595972987654')
        db.add_all([principal, other]); db.flush()
        alias = Cliente(nome='Ana Corrêa', merged_into_id=principal.id, ativo=False)
        db.add(alias); db.flush()
        matching = Pedido(numero_pedido='ALIAS-1', descricao='Snapshot', valor_total=20,
            cliente_nome=alias.nome, cliente_telefone=principal.telefone)
        claimed = Pedido(numero_pedido='ALIAS-2', descricao='Snapshot', valor_total=25,
            cliente_nome=alias.nome, cliente_telefone=principal.telefone, cliente_id=other.id)
        account = PdvCliente(nome=alias.nome, telefone=principal.telefone, cadastro_cliente_id=other.id)
        db.add_all([matching, claimed, account]); db.flush()
        plan = preview_customer_links(db, principal)
        assert plan['counts']['orders'] == 1 and plan['counts']['pdv_accounts'] == 0
        apply_customer_links(db, principal, plan['token'], db.get(Usuario, uid))
        assert matching.cliente_id == principal.id and claimed.cliente_id == other.id
        assert account.cadastro_cliente_id == other.id and alias.merged_into_id == principal.id


def test_city_and_postcode_never_corroborate_a_homonym_and_py_remains_printable(env):
    from app.services.address_book import save_or_reuse
    factory, _, uid, _ = env
    with factory() as db:
        principal = Cliente(nome='Maria Duarte', endereco='Pedro Juan Caballero, 8500, PY',
            telefone='+595972123456')
        homonym = Cliente(nome='Maria Duarte', endereco='Otra ciudad, 1234, PY')
        db.add_all([principal, homonym]); db.flush()
        data = {'pais':'PY', 'nome':'Maria Duarte', 'cidade':'Pedro Juan Caballero', 'cep':'8500'}
        unlinked = SavedAddress(label='Só cidade e CEP', data=data, created_by=uid)
        parcel = Rastreamento(codigo_rastreio='CITY-ONLY', destinatario='Maria Duarte', destino=principal.endereco)
        db.add_all([unlinked, parcel]); db.flush()
        assert find_customer(db, data)[0] is None
        assert not any(preview_customer_links(db, principal)['counts'].values())
        assert not auto_link_tracking(db, parcel) and parcel.cliente_id is None
        assert find_customer(db, {**data, 'telefone':principal.telefone})[0].id == principal.id
        # Saving/printing the available PY block is still allowed; unresolved
        # identity is reviewed rather than requiring an invented street/number.
        saved, _ = save_or_reuse(db, data, uid)
        assert saved.data == data and saved.customer_link_review
        assert saved.cliente_id not in {principal.id, homonym.id}


@pytest.mark.parametrize('location', [
    'Pedro Juan Caballero, 8500, PY',
    'Rua Central, São Paulo, SP, 01001000, BR',
    'Avenida 25, Asunción, PY',
])
def test_free_address_requires_a_street_and_house_number_not_a_city_or_postcode(env, location):
    factory, _, _, _ = env
    with factory() as db:
        principal = Cliente(nome='Pessoa Teste', endereco=location)
        db.add(principal); db.flush()
        parcel = Rastreamento(codigo_rastreio='INCOMPLETE', destinatario=principal.nome, destino=location)
        db.add(parcel); db.flush()
        assert preview_customer_links(db, principal)['counts']['tracking'] == 0
