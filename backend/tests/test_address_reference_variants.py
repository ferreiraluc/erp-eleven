"""Reference labels and repeated PY districts must not multiply destinations."""
import copy
import uuid

import pytest
from fastapi import HTTPException

from test_address_manager import env
from test_assistant import setup
from app.models import Cliente
from app.models.address_book import SavedAddress, FreightOrder
from app.services.address_book import resolve_address, save_or_reuse
from app.services.address_identity import equivalent, fingerprint
from app.services.address_maintenance import merge_addresses


BR = {'pais': 'BR', 'nome': 'Cliente Exemplo', 'endereco': 'Av. das Flores',
      'numero': '631', 'bairro': 'Centro', 'complemento': 'Referência: Atacadão Exemplo',
      'cidade': 'Cidade Exemplo', 'estado': 'BA', 'cep': '47000-000', 'cpf': '12345678909'}
SHORT = BR | {'complemento': 'Atac Exemplo'}
REF = BR | {'complemento': 'Ref. Atacadão Exemplo'}
PY = {'pais': 'PY', 'nome': 'Juan Exemplo', 'endereco': 'Calle Ejemplo 1571 C/ Otra',
      'numero': '', 'bairro': 'Barrio Las Flores', 'complemento': '', 'cidade': 'Asunción',
      'estado': '', 'cep': '', 'cpf': 'A-1234567', 'telefone': '0972111222'}
PY_REPEATED = PY | {'endereco': 'Calle Ejemplo 1571 C/ Otra, Barrio Las Flores'}


@pytest.mark.parametrize('variant', [SHORT, REF, BR | {'complemento': 'Ponto de referência: Atacadão Exemplo'}])
def test_reference_wording_is_equivalent_without_changing_legacy_hash(variant):
    assert equivalent(BR, variant) and equivalent(variant, BR)
    assert fingerprint(BR) != fingerprint(variant)


@pytest.mark.parametrize('change', [
    {'complemento': ''}, {'complemento': 'Atac Outra Loja'},
    {'complemento': 'Atacado Exemplo'}, {'complemento': 'Ref. Atacadão Exemplo, sala 2'},
    {'numero': '632'}, {'cep': ''}, {'nome': 'Outro Cliente'}, {'bairro': 'Outro Bairro'},
])
def test_reference_comparison_never_discards_delivery_details(change):
    assert not equivalent(BR, BR | change)


def test_short_reference_does_not_make_two_full_merchant_names_equal():
    other = BR | {'complemento': 'Atacado Exemplo'}
    assert equivalent(SHORT, other)
    assert not equivalent(BR, other)


def test_py_district_is_removed_only_when_repeated_as_a_whole_suffix():
    assert equivalent(PY, PY_REPEATED) and equivalent(PY_REPEATED, PY)
    # The legacy hash already accepts moving the district entirely into the street.
    assert equivalent(PY, PY_REPEATED | {'bairro': ''})
    for change in ({'bairro': 'Otro Barrio'}, {'complemento': 'Casa 2'},
                   {'cidade': 'Otra Ciudad'}, {'telefone': '0972111223'},
                   {'endereco': 'Calle Ejemplo 1572 C/ Otra, Barrio Las Flores'},
                   {'endereco': 'Calle Ejemplo 1571 C/ Otra, Barrio Las Flores, oficina 2'}):
        assert not equivalent(PY, PY_REPEATED | change)


@pytest.mark.parametrize('left,right', [(BR, SHORT), (BR, REF), (PY, PY_REPEATED)])
@pytest.mark.parametrize('reverse', [False, True])
def test_bot_and_editor_reuse_same_address_and_customer(env, left, right, reverse):
    factory, client, uid, _ = env
    first, second = (right, left) if reverse else (left, right)
    response = client.post('/manager/addresses', json={'label': first['nome'], 'data': first})
    assert response.status_code == 200, response.text
    with factory() as db:
        row, reused = save_or_reuse(db, second, uid)
        assert reused and str(row.id) == response.json()['id']
        assert db.query(Cliente).count() == db.query(SavedAddress).count() == 1
        with pytest.raises(HTTPException):
            save_or_reuse(db, second | {'cpf': '98765432100'}, uid)


def legacy_group(db, uid, data=None):
    rows = [SavedAddress(label='Endereço', data=datum, created_by=uid)
            for datum in (data or [BR, SHORT, REF])]
    db.add_all(rows); db.flush()
    return rows


def test_group_merge_preserves_all_aliases_snapshots_and_history(env):
    factory, client, uid, _ = env
    with factory() as db:
        target, source, extra = legacy_group(db, uid)
        rows = [target, source, extra]
        originals = [copy.deepcopy(row.data) for row in rows]
        freights = [FreightOrder(request_key=uuid.uuid4(), user_id=uid, address_id=row.id,
                                environment='sandbox', state='quoted', rates=[], payload={'recipient': row.data})
                    for row in rows]
        db.add_all(freights); db.commit()
        ids = [row.id for row in rows]
        plan = merge_addresses(db, target.id, source.id, additional_source_ids=[extra.id])
        assert plan['state'] == 'ready' and plan['history_total'] == 3
        assert all(row.merged_into_id is None for row in rows)
        result = merge_addresses(db, target.id, source.id, additional_source_ids=[extra.id],
                                 apply=True, expected_plan=plan['plan_token'])
        assert result['state'] == 'merged' and len(result['source_ids']) == 2
        assert [row.data for row in rows] == originals
        assert [row.address_id for row in freights] == ids
        assert [row.payload['recipient'] for row in freights] == originals
        assert all(resolve_address(db, key).id == target.id for key in ids)
        assert db.query(SavedAddress).count() == 3
        assert db.query(SavedAddress).filter_by(merged_into_id=None).count() == 1
        assert merge_addresses(db, target.id, source.id, additional_source_ids=[extra.id],
                               apply=True, expected_plan=plan['plan_token'])['state'] == 'already_merged'
        db.commit()
    for key in ids:
        assert client.get(f'/manager/addresses/{key}/usage').json()['total'] == 3


def test_group_merge_rejects_stale_third_row_and_unreviewed_fourth(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, source, extra = legacy_group(db, uid)
        plan = merge_addresses(db, target.id, source.id, additional_source_ids=[extra.id])
        extra.data = extra.data | {'email': 'fixture@example.test'}; db.flush()
        with pytest.raises(HTTPException):
            merge_addresses(db, target.id, source.id, additional_source_ids=[extra.id],
                            apply=True, expected_plan=plan['plan_token'])
        assert all(row.merged_into_id is None for row in [target, source, extra])
        db.add(SavedAddress(label='Fora do grupo', data=BR | {'complemento': 'Atacadão Exemplo'}, created_by=uid))
        db.flush()
        with pytest.raises(HTTPException):
            merge_addresses(db, target.id, source.id, additional_source_ids=[extra.id])


@pytest.mark.parametrize('conflict', ['document', 'location', 'customer'])
def test_group_merge_rejects_conflicts_between_sources_even_when_target_is_partial(env, conflict):
    factory, _, uid, _ = env
    with factory() as db:
        target, source, extra = legacy_group(db, uid)
        if conflict == 'document':
            target.data = target.data | {'cpf': ''}
            extra.data = extra.data | {'cpf': '98765432100'}
        elif conflict == 'location':
            target.data = target.data | {'complemento': 'Ref. Atac Exemplo'}
            source.data = source.data | {'complemento': 'Atacadão Exemplo'}
            extra.data = extra.data | {'complemento': 'Atacado Exemplo'}
        else:
            customers = [Cliente(nome='Cliente A'), Cliente(nome='Cliente B')]
            db.add_all(customers); db.flush()
            source.cliente_id, extra.cliente_id = [row.id for row in customers]
        db.flush()
        with pytest.raises(HTTPException):
            merge_addresses(db, target.id, source.id, additional_source_ids=[extra.id])
        assert all(row.merged_into_id is None for row in [target, source, extra])


def test_cli_reviews_all_explicit_sources_and_audits_each_merge(env, monkeypatch, capsys):
    import json
    from app import address_maintenance as command
    from app.models import Usuario
    from app.models.access import AuditEvent
    from app.services.access_policy import OWNER_EMAIL
    factory, _, uid, _ = env
    monkeypatch.setattr(command, 'SessionLocal', factory)
    with factory() as db:
        db.get(Usuario, uid).email = OWNER_EMAIL
        target, source, extra = legacy_group(db, uid)
        ids = [row.id for row in (target, source, extra)]; db.commit()
    args = ['merge', '--target', str(ids[0]), '--source', str(ids[1]), '--source', str(ids[2])]
    command.main(args)
    plan = json.loads(capsys.readouterr().out)
    command.main([*args, '--apply', '--expected-plan', plan['plan_token']])
    assert json.loads(capsys.readouterr().out)['state'] == 'merged'
    with factory() as db:
        assert db.query(SavedAddress).filter_by(merged_into_id=None).count() == 1
        events = db.query(AuditEvent).filter_by(action='address_merged').all()
        assert {row.changes['source_id'] for row in events} == {str(key) for key in ids[1:]}
        assert all(row.user_id == uid for row in events)
