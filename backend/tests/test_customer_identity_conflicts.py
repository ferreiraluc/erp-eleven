"""Duplicate typed documents never select one unconfirmed principal by name."""
import pytest
from test_assistant import setup
from test_address_manager import env
from app.models import Cliente
from app.services.customer_identity import find_customer
from app.services.address_book import save_or_reuse


def document(kind, number):
    return {'tipo': kind, 'pais': 'PY', 'numero': number}


@pytest.mark.parametrize('second_name', ['Ana Silva', 'Maria Santos'])
def test_duplicate_ci_on_two_principals_is_ambiguous_even_when_only_one_name_matches(env, second_name):
    factory, _, uid, _ = env
    with factory() as db:
        first = Cliente(nome='Ana Silva', documentos=[document('CI', '1234567')])
        second = Cliente(nome=second_name, documentos=[document('CI', '1234567')])
        db.add_all([first, second]); db.flush()
        customer, reason, candidates = find_customer(db, {'nome': 'Ana Silva',
            'documentos': [document('CI', '1234567')]})
        assert customer is None and reason == 'ambiguous'
        assert {candidate.id for candidate in candidates} == {first.id, second.id}
        address, _ = save_or_reuse(db, {'pais': 'PY', 'nome': 'Ana Silva', 'cpf': '1234567',
            'documento_tipo': 'CI', 'cidade': 'Asunción'}, uid)
        assert address.cliente_id is None and address.customer_link_review
        assert address.customer_link_reason == 'ambiguous'
        assert db.query(Cliente).count() == 2


def test_one_known_document_with_an_incompatible_name_is_a_conflict(env):
    factory, _, _, _ = env
    with factory() as db:
        known = Cliente(nome='Maria Santos', documentos=[document('CI', '1234567')])
        db.add(known); db.flush()
        selected, reason, candidates = find_customer(db, {'nome': 'Ana Silva',
            'documentos': [document('CI', '1234567')]})
        assert selected is None and reason == 'document_name_conflict'
        assert [candidate.id for candidate in candidates] == [known.id]


def test_one_payload_with_two_peoples_documents_never_selects_by_one_matching_name(env):
    factory, _, _, _ = env
    with factory() as db:
        first = Cliente(nome='Ana Silva', documentos=[document('CI', '1234567')])
        second = Cliente(nome='Maria Santos', documentos=[document('RUC', '800123456')])
        db.add_all([first, second]); db.flush()
        selected, reason, candidates = find_customer(db, {'nome': 'Ana Silva', 'documentos': [
            document('CI', '1234567'), document('RUC', '800123456'),
        ]})
        assert selected is None and reason == 'ambiguous'
        assert {candidate.id for candidate in candidates} == {first.id, second.id}


def test_confirmed_aliases_with_repeated_documents_remain_one_identity(env):
    factory, _, _, _ = env
    with factory() as db:
        main = Cliente(nome='Ana Silva', documentos=[document('CI', '1234567')])
        db.add(main); db.flush()
        alias = Cliente(nome='Ana Correa', documentos=[document('CI', '1234567'), document('RUC', '800123456')],
                        merged_into_id=main.id, ativo=False)
        db.add(alias); db.flush()
        incoming = {'nome': 'Ana Correa', 'documentos': [document('CI', '1234567'), document('RUC', '800123456')]}
        selected, reason, candidates = find_customer(db, incoming)
        assert selected.id == main.id and reason == 'document' and candidates == []
        selected, _, candidates = find_customer(db, incoming, exclude_id=main.id)
        assert selected is None and candidates == []


def test_alias_document_still_conflicts_with_a_different_unconfirmed_principal(env):
    factory, _, _, _ = env
    with factory() as db:
        main = Cliente(nome='Ana Silva')
        db.add(main); db.flush()
        alias = Cliente(nome='Ana Correa', documentos=[document('CI', '1234567')], merged_into_id=main.id, ativo=False)
        other = Cliente(nome='Maria Santos', documentos=[document('CI', '1234567')])
        db.add_all([alias, other]); db.flush()
        selected, reason, candidates = find_customer(db, {'nome': 'Ana Correa', 'documentos': [document('CI', '1234567')]})
        assert selected is None and reason == 'ambiguous'
        assert {candidate.id for candidate in candidates} == {main.id, other.id}
