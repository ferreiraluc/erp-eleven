"""Selected merges review existing aliases, their documents and their links."""
import uuid

import pytest
from fastapi import HTTPException
from test_assistant import setup
from test_address_manager import env
from app.models import Cliente, Pedido
from app.models.address_book import SavedAddress
from app.models.pdv import PdvCliente
from app.services.customer_maintenance import merge_customer_selection


def person_document(row, kind, number):
    if kind == 'CPF':
        row.cpf = number
    else:
        row.documentos = [{'tipo': kind, 'pais': 'PY', 'numero': number}]


@pytest.mark.parametrize('kind,numbers,field', [
    ('CPF', ('12345678909', '98765432100'), 'cpf'),
    ('CI', ('1234567', '7654321'), 'documentos'),
])
def test_existing_alias_documents_are_shown_and_require_conflict_review(env, kind, numbers, field):
    factory, _, _, _ = env
    with factory() as db:
        target, source = Cliente(nome='Ana Silva'), Cliente(nome='Ana Silva')
        db.add_all([target, source]); db.flush()
        alias = Cliente(nome='Ana Silva', ativo=False, merged_into_id=target.id)
        person_document(alias, kind, numbers[0]); person_document(source, kind, numbers[1])
        db.add(alias); db.flush()
        plan = merge_customer_selection(db, target.id, [source.id])
        assert plan['state'] == 'review_conflicts' and plan['conflicting_fields'] == [field]
        assert plan['customers'][0]['documents'] == [{'tipo': kind, 'pais': 'BR' if kind == 'CPF' else 'PY', 'numero': numbers[0]}]
        with pytest.raises(HTTPException, match='mesma pessoa'):
            merge_customer_selection(db, target.id, [source.id], apply=True, expected_plan=plan['plan_token'])
        assert source.merged_into_id is None
        result = merge_customer_selection(db, target.id, [source.id], apply=True,
                                         expected_plan=plan['plan_token'], reviewed_conflicts=True)
        assert result['state'] == 'merged' and target.cpf is None
        assert alias.merged_into_id == source.merged_into_id == target.id
        if kind == 'CPF':
            assert alias.cpf == numbers[0] and source.cpf == numbers[1]
        else:
            assert alias.documentos[0]['numero'] == numbers[0] and source.documentos[0]['numero'] == numbers[1]


@pytest.mark.parametrize('change', ['changed_alias', 'new_alias'])
def test_alias_identity_changes_invalidate_the_whole_preview(env, change):
    factory, _, _, _ = env
    with factory() as db:
        target, source = Cliente(nome='Ana Silva'), Cliente(nome='Ana Silva')
        db.add_all([target, source]); db.flush()
        alias = Cliente(nome='Ana Silva', ativo=False, merged_into_id=target.id)
        person_document(alias, 'CI', '1234567'); db.add(alias); db.flush()
        plan = merge_customer_selection(db, target.id, [source.id])
        if change == 'changed_alias':
            person_document(alias, 'CI', '7654321')
        else:
            other_alias = Cliente(nome='Ana Silva', ativo=False, merged_into_id=target.id)
            person_document(other_alias, 'CI', '7654321'); db.add(other_alias)
        db.flush()
        with pytest.raises(HTTPException, match='nova prévia'):
            merge_customer_selection(db, target.id, [source.id], apply=True,
                                     expected_plan=plan['plan_token'], reviewed_conflicts=True)
        assert source.merged_into_id is None


def test_nested_aliases_contribute_documents_and_historical_links(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, source = Cliente(nome='Ana Silva'), Cliente(nome='Ana Silva')
        db.add_all([target, source]); db.flush()
        parent = Cliente(nome='Ana Silva', ativo=False, merged_into_id=target.id)
        db.add(parent); db.flush()
        leaf = Cliente(nome='Ana Silva', ativo=False, merged_into_id=parent.id)
        old_source = Cliente(nome='Ana Silva', ativo=False, merged_into_id=source.id)
        person_document(leaf, 'CI', '1234567')
        person_document(old_source, 'RUC', '800123456')
        db.add_all([leaf, old_source]); db.flush()
        address = SavedAddress(label='Casa', data={'pais': 'PY', 'nome': 'Ana Silva', 'cidade': 'Asunción'},
                               cliente_id=leaf.id, created_by=uid)
        account = PdvCliente(nome='Ana Silva', cadastro_cliente_id=old_source.id, saldo_fiado_gs=150, limite_fiado_gs=200)
        order = Pedido(numero_pedido=str(uuid.uuid4()), descricao='Histórico', valor_total=100,
                       cliente_id=old_source.id, cliente_nome='Nome preservado')
        db.add_all([address, account, order]); db.flush()
        plan = merge_customer_selection(db, target.id, [source.id])
        assert plan['state'] == 'ready'
        assert plan['customers'][0]['documents'] == [{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}]
        assert plan['customers'][1]['documents'] == [{'tipo': 'RUC', 'pais': 'PY', 'numero': '800123456'}]
        assert plan['links_to_move'] == {'orders': 1, 'tracking': 0, 'addresses': 1, 'pdv_customers': 1}
        merge_customer_selection(db, target.id, [source.id], apply=True, expected_plan=plan['plan_token'])
        assert address.cliente_id == account.cadastro_cliente_id == order.cliente_id == target.id
        assert account.saldo_fiado_gs == 150 and account.limite_fiado_gs == 200
        assert order.cliente_nome == 'Nome preservado'
        assert leaf.merged_into_id == parent.id and old_source.merged_into_id == source.id
