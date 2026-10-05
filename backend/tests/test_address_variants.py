"""Conservative address variants, entirely isolated from postal providers."""
import pytest
from fastapi import HTTPException

from test_address_manager import env
from test_assistant import setup
from app.services.address_identity import fingerprint, matches_known_variants
from app.services.address_maintenance import merge_addresses


ADDRESS = {'pais': 'BR', 'nome': 'Cliente Exemplo', 'endereco': 'Avenida das Palmeiras',
           'numero': '1002', 'bairro': 'Padroeira', 'cidade': 'Cidade Exemplo',
           'estado': 'SP', 'cep': '06172-004', 'complemento': '', 'cpf': ''}
VARIANT = {**ADDRESS, 'endereco': 'Av das Palmeiras', 'bairro': 'Jardim Padroeira', 'cpf': '12345678909'}


def create(client, data):
    return client.post('/manager/addresses', json={'label': data['nome'], 'data': data})


@pytest.mark.parametrize('street', ['Av das Palmeiras', 'AV. DAS PALMEIRAS', 'Avenida das Palmeiras'])
@pytest.mark.parametrize('district', ['Padroeira', 'Jardim Padroeira', 'Jd. Padroeira'])
def test_known_spelling_variants_require_complete_equal_location(street, district):
    changed = VARIANT | {'endereco': street, 'bairro': district}
    assert matches_known_variants(ADDRESS, changed)
    assert matches_known_variants(changed, ADDRESS)
    # Hashes remain compatible with earlier releases; matching is a fallback.
    assert fingerprint(ADDRESS) != fingerprint(VARIANT)


@pytest.mark.parametrize('change', [
    {'pais': 'PY'}, {'nome': 'Outra Pessoa'}, {'cidade': 'Outra Cidade'}, {'estado': 'PR'},
    {'cep': '06172005'}, {'cep': ''}, {'endereco': 'Avenida Outra'}, {'numero': '1003'},
    {'complemento': 'Apartamento 12'}, {'bairro': 'Jardim Outro'}, {'bairro': 'Vila Padroeira'},
])
def test_different_recipient_or_delivery_location_never_matches(change):
    assert not matches_known_variants(ADDRESS, VARIANT | change)


def test_missing_cep_and_house_number_do_not_match_by_name_and_street_alone():
    assert not matches_known_variants(ADDRESS | {'cep': ''}, VARIANT | {'cep': ''})
    assert not matches_known_variants(ADDRESS | {'numero': ''}, VARIANT | {'numero': ''})
    assert not matches_known_variants(ADDRESS | {'numero': '', 'endereco': 'Avenida 25'},
                                      VARIANT | {'numero': '', 'endereco': 'Av 25'})


def test_legacy_print_can_embed_the_same_structured_house_number():
    printed = VARIANT | {'endereco': 'Av das Palmeiras, 1002', 'numero': '', 'bairro': ''}
    assert matches_known_variants(ADDRESS, printed)
    assert not matches_known_variants(ADDRESS, printed | {'endereco': 'Av das Palmeiras, 1003'})


@pytest.mark.parametrize('variant_first', [False, True])
def test_create_reuses_legacy_hash_in_either_order_and_enriches_document(env, variant_first):
    factory, client, _, _ = env
    first = create(client, VARIANT if variant_first else ADDRESS)
    assert first.status_code == 200
    second = create(client, ADDRESS if variant_first else VARIANT)
    assert second.status_code == 200, second.text
    assert second.json()['id'] == first.json()['id'] and second.json()['reused'] is True
    assert second.json()['data']['cpf'] == VARIANT['cpf']
    assert client.get('/manager/addresses').json()['total'] == 1


def test_document_conflict_is_not_hidden_by_spelling_variants(env):
    _, client, _, _ = env
    assert create(client, ADDRESS | {'cpf': '98765432100'}).status_code == 200
    assert create(client, VARIANT).status_code == 409
    assert client.get('/manager/addresses').json()['total'] == 1


def test_legacy_multiple_compatible_roots_require_explicit_review(env):
    from app.models.address_book import SavedAddress
    factory, client, user_id, _ = env
    with factory() as db:
        # Existing hashes may predate the new comparison. No broad merge runs.
        db.add_all([SavedAddress(label='A', data=ADDRESS, created_by=user_id),
                    SavedAddress(label='B', data=VARIANT, created_by=user_id)])
        db.commit()
    response = create(client, VARIANT | {'endereco': 'AV. DAS PALMEIRAS', 'bairro': 'Jd Padroeira'})
    assert response.status_code == 409
    assert client.get('/manager/addresses').json()['total'] == 2


def legacy_pair(db, user_id, **source_changes):
    from app.models.address_book import SavedAddress
    target = SavedAddress(label='Principal', data=ADDRESS, created_by=user_id)
    source = SavedAddress(label='Duplicado', data=VARIANT | source_changes, created_by=user_id)
    db.add_all([target, source]); db.flush()
    return target, source


def test_explicit_merge_dry_run_preserves_aliases_and_historical_snapshots(env):
    import copy
    import uuid
    from app.models.address_book import FreightOrder, SavedAddress
    from app.models.assistant import utcnow
    from app.models.printing import PrintJob
    from app.services.address_book import resolve_address

    factory, client, user_id, device_id = env
    with factory() as db:
        target, source = legacy_pair(db, user_id)
        alias = SavedAddress(label='Alias antigo', data=VARIANT, created_by=user_id,
                             active=False, merged_into_id=source.id)
        db.add(alias); db.flush()
        freight = FreightOrder(request_key=uuid.uuid4(), user_id=user_id, address_id=source.id,
                               environment='sandbox', state='quoted', rates=[], payload={'original': 'frete intacto'})
        printed = PrintJob(device_id=uuid.UUID(device_id), user_id=user_id, request_key=uuid.uuid4(),
                           snapshot={'editor': copy.deepcopy(VARIANT)}, address_id=alias.id, source='bot',
                           status='submitted', pdf=b'original', sha256='a' * 64, expires_at=utcnow())
        db.add_all([freight, printed]); db.commit()
        ids = target.id, source.id, alias.id
        previous = copy.deepcopy(freight.payload), copy.deepcopy(printed.snapshot), printed.pdf
        versions = target.version, source.version
        plan = merge_addresses(db, target.id, source.id)
        assert plan['state'] == 'ready' and plan['history_total'] == 2
        assert plan['fields_added'] == ['cpf']
        assert source.merged_into_id is None and (target.version, source.version) == versions
        assert target.data['cpf'] == ''
        assert VARIANT['cpf'] not in str(plan)
        result = merge_addresses(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])
        assert result['state'] == 'merged'
        assert target.data['cpf'] == VARIANT['cpf'] and source.merged_into_id == target.id
        assert resolve_address(db, alias.id).id == target.id
        assert (freight.payload, printed.snapshot, printed.pdf) == previous
        assert freight.address_id == source.id and printed.address_id == alias.id
        assert db.query(SavedAddress).count() == 3 and db.query(PrintJob).count() == 1
        assert merge_addresses(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])['state'] == 'already_merged'
        db.commit()
    assert client.get('/manager/addresses').json()['total'] == 1
    for address_id in ids:
        usage = client.get(f'/manager/addresses/{address_id}/usage').json()
        assert usage['total'] == 2 and usage['summary']['address_prints'] == 1
    assert create(client, VARIANT).json()['id'] == str(ids[0])


@pytest.mark.parametrize('change', [{'cpf': '98765432100'}, {'numero': '1003'}, {'bairro': 'Outro bairro'}])
def test_explicit_merge_rejects_incompatible_pair(env, change):
    factory, _, user_id, _ = env
    with factory() as db:
        target, source = legacy_pair(db, user_id, **change)
        target.data = {**target.data, 'cpf': '12345678909'}; db.flush()
        with pytest.raises(HTTPException) as error:
            merge_addresses(db, target.id, source.id)
        assert error.value.status_code == 409
        assert source.merged_into_id is None


def test_explicit_merge_rejects_distinct_customer_links(env):
    from app.models.cliente import Cliente
    factory, _, user_id, _ = env
    with factory() as db:
        left = Cliente(nome='Cliente A', telefone='111'); right = Cliente(nome='Cliente B', telefone='222')
        db.add_all([left, right]); db.flush()
        target, source = legacy_pair(db, user_id)
        target.cliente_id, source.cliente_id = left.id, right.id; db.flush()
        with pytest.raises(HTTPException, match='409'):
            merge_addresses(db, target.id, source.id)
        assert source.merged_into_id is None


def test_explicit_merge_preserves_source_customer_and_active_state(env):
    from app.models.cliente import Cliente
    factory, _, user_id, _ = env
    with factory() as db:
        customer = Cliente(nome='Cliente A', telefone='111'); db.add(customer); db.flush()
        target, source = legacy_pair(db, user_id)
        target.active = False; source.cliente_id = customer.id; db.flush()
        plan = merge_addresses(db, target.id, source.id)
        merge_addresses(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])
        assert target.active and target.cliente_id == customer.id and not source.active


def test_explicit_merge_requires_reviewed_plan_and_rejects_stale_data(env):
    factory, _, user_id, _ = env
    with factory() as db:
        target, source = legacy_pair(db, user_id)
        plan = merge_addresses(db, target.id, source.id)
        with pytest.raises(HTTPException):
            merge_addresses(db, target.id, source.id, apply=True)
        source.label = 'Editado depois da simulação'; source.version += 1; db.flush()
        with pytest.raises(HTTPException):
            merge_addresses(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])
        assert source.merged_into_id is None and target.data['cpf'] == ''


def test_explicit_merge_rejects_unreviewed_third_candidate(env):
    from app.models.address_book import SavedAddress
    factory, _, user_id, _ = env
    with factory() as db:
        target, source = legacy_pair(db, user_id)
        db.add(SavedAddress(label='Terceiro', data=ADDRESS | {'bairro': 'Jd Padroeira'}, created_by=user_id)); db.flush()
        with pytest.raises(HTTPException):
            merge_addresses(db, target.id, source.id)
        assert source.merged_into_id is None


def test_cli_defaults_to_dry_run_and_applies_only_expected_pair(env, monkeypatch, capsys):
    import json
    from app import address_maintenance as command
    from app.models.address_book import SavedAddress
    factory, _, user_id, _ = env
    monkeypatch.setattr(command, 'SessionLocal', factory)
    with factory() as db:
        target, source = legacy_pair(db, user_id)
        target_id, source_id = target.id, source.id; db.commit()
    args = ['merge', '--target', str(target_id), '--source', str(source_id)]
    command.main(args)
    plan = json.loads(capsys.readouterr().out)
    assert plan['state'] == 'ready'
    with factory() as db:
        assert db.get(SavedAddress, source_id).merged_into_id is None
    with pytest.raises(SystemExit):
        command.main([*args, '--apply'])
    command.main([*args, '--apply', '--expected-plan', plan['plan_token']])
    assert json.loads(capsys.readouterr().out)['state'] == 'merged'
    with factory() as db:
        assert db.get(SavedAddress, source_id).merged_into_id == target_id
