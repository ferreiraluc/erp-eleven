"""Only synthetic catalog data and mocked vision; no production providers/DB."""
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import jwt
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from test_assistant import setup
from test_inventory_ocr import stock_app, picture
from test_product_intake_grade import manager_stock_app
from test_access_postgres import pg
from app.config import settings
from app.database import Base
from app.models.access import AuditEvent
from app.models import Usuario, Vendedor
from app.models.inventory import Item, StockMovement, Supplier
from app.models.usuario import UsuarioRole
from app.services import inventory_grade_analysis as grades, product_photo
from app.services.vision_provider import VisionError
from app.schemas.inventory_grade_analysis import GradeLinkPreviewRequest, GradeLinkCommitRequest


@pytest.fixture
def grade_app(manager_stock_app, monkeypatch):
    factory, client, user_id = manager_stock_app
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[AuditEvent.__table__])
    product_photo._cache.clear()
    product_photo._requests.clear()
    monkeypatch.setattr(grades, 'configured_provider', lambda: 'deepseek')
    monkeypatch.setattr(settings, 'DEEPSEEK_VISION_MODEL', 'deepseek-flash')
    monkeypatch.setattr(settings, 'SECRET_KEY', 'grade-tests-only-signing-key-32-characters')
    monkeypatch.setattr(grades, 'complete_vision', lambda **_: pytest.fail('Mock the provider explicitly'))
    return factory, client, user_id


def add(db, name='Polo 102', *, size='S', color='Azul', group_key=None, active=True, image=None):
    row = Item(name=name, sku_internal=f'GRADE-{uuid.uuid4().hex}',
        barcode='COMMON', category='Camisas', brand='Marca', unit='un',
        size=size, color=color, group_key=group_key, is_active=active,
        image_data=image, stock_loja=3, stock_deposito=7, current_stock=10,
        cost_price=8, sale_price=15)
    db.add(row)
    db.flush()
    return row


def selection(factory, **changes):
    with factory() as db:
        a = add(db, size='S', **changes)
        b = add(db, size='M', **changes)
        db.commit()
        return [str(a.id), str(b.id)]


def advice(ids, **changes):
    return json.dumps({'suggestions': [{
        'item_ids': ids, 'confidence': 'high',
        'evidence': ['Mesmo nome de modelo e categoria; tamanhos diferentes.'],
        'warnings': [], **changes,
    }]})


def preview(client, ids, **changes):
    return client.post('/api/inventory/grades/preview', json={
        'item_ids': ids, 'new_group_name': 'Grade conferida', **changes})


def commit(client, token):
    return client.post('/api/inventory/grades/commit', json={'preview_token': token, 'confirmed': True})


@pytest.mark.parametrize('route,payload', [
    ('ai-analysis', {'include_photos': False}),
    ('preview', {'new_group_name': 'Grade'}),
    ('commit', {'preview_token': 'test-only-token-000000000000', 'confirmed': True}),
])
def test_only_managers_can_analyze_preview_or_commit(stock_app, route, payload):
    _, client, _ = stock_app
    data = {'item_ids': [str(uuid.uuid4()), str(uuid.uuid4())], **payload}
    if route == 'commit':
        data.pop('item_ids')
    assert client.post(f'/api/inventory/grades/{route}', json=data).status_code == 403


def test_analysis_sends_only_selected_product_metadata_and_sanitized_photos(grade_app, monkeypatch):
    factory, client, _ = grade_app
    ids = selection(factory, image=picture())
    with factory() as db:
        add(db, name='Produto fora da seleção', image='DO-NOT-SEND')
        db.commit()
    calls = []
    def complete(**kwargs):
        calls.append(kwargs)
        return advice(ids)
    monkeypatch.setattr(grades, 'complete_vision', complete)
    response = client.post('/api/inventory/grades/ai-analysis', json={'item_ids': ids})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['advisory_only'] is True
    assert result['provider'] == 'deepseek' and result['model'] == 'deepseek-flash'
    assert result['analyzed_count'] == result['photos_analyzed'] == 2
    assert {row['id'] for row in result['products']} == set(ids)
    assert all(len(row['version']) == 64 and row['has_image'] for row in result['products'])
    assert response.headers['Cache-Control'] == 'no-store'
    payload = calls[0]
    assert payload['timeout'] == 35 and payload['max_tokens'] == 2500
    assert 'DADOS NÃO CONFIÁVEIS' in payload['system']
    images = [block for block in payload['messages'][0]['content'] if block['type'] == 'image']
    assert len(images) == 2 and all(block['source']['media_type'] == 'image/jpeg' for block in images)
    text = json.dumps(payload, ensure_ascii=False)
    assert 'DO-NOT-SEND' not in text and 'Produto fora da seleção' not in text
    assert all(field not in text for field in ('sale_price', 'cost_price', 'stock_loja', 'COMMON', 'cliente'))
    # A double click reuses the bounded successful result, without new photo/provider work.
    assert client.post('/api/inventory/grades/ai-analysis', json={'item_ids': ids}).status_code == 200
    assert len(calls) == 1
    with factory() as db:
        assert all(db.get(Item, uuid.UUID(identity)).group_key is None for identity in ids)
        assert db.query(StockMovement).count() == db.query(AuditEvent).count() == 0


def test_text_only_analysis_never_selects_originals(grade_app, monkeypatch):
    factory, client, _ = grade_app
    ids = selection(factory, image='not-a-real-image')
    statements = []
    with factory() as db:
        engine = db.bind
    def record(_, __, statement, *args):
        statements.append(statement)
    sa.event.listen(engine, 'before_cursor_execute', record)
    monkeypatch.setattr(grades, 'complete_vision', lambda **_: advice(ids))
    try:
        response = client.post('/api/inventory/grades/ai-analysis', json={
            'item_ids': ids, 'include_photos': False})
    finally:
        sa.event.remove(engine, 'before_cursor_execute', record)
    assert response.status_code == 200, response.text
    assert response.json()['photos_analyzed'] == 0
    assert not any('substr(inventory_items.image_data' in statement for statement in statements)
    assert all('inventory_items.image_data AS' not in statement for statement in statements)


@pytest.mark.parametrize('kind', ['unknown', 'overlap', 'bad_json', 'failure'])
def test_provider_errors_and_out_of_scope_ids_never_become_fake_success(grade_app, monkeypatch, kind):
    factory, client, _ = grade_app
    ids = selection(factory)
    def provider(**_):
        if kind == 'failure':
            raise VisionError('PRIVATE-PROVIDER-DETAIL')
        if kind == 'unknown':
            return advice([ids[0], str(uuid.uuid4())])
        if kind == 'overlap':
            suggestion = json.loads(advice(ids))['suggestions'][0]
            return json.dumps({'suggestions': [suggestion, suggestion]})
        return 'This is not JSON'
    monkeypatch.setattr(grades, 'complete_vision', provider)
    response = client.post('/api/inventory/grades/ai-analysis', json={'item_ids': ids})
    assert response.status_code == (503 if kind == 'failure' else 502), response.text
    assert 'PRIVATE' not in response.text and 'suggestions' not in response.json()
    with factory() as db:
        assert all(db.get(Item, uuid.UUID(identity)).group_key is None for identity in ids)


def test_provider_call_holds_no_database_transaction_and_stale_result_is_rejected(grade_app, monkeypatch):
    factory, client, _ = grade_app
    ids = selection(factory)
    def provider(**_):
        with factory() as db:
            row = db.get(Item, uuid.UUID(ids[0]))
            row.name = 'Outro modelo 900'
            db.commit()
        return advice(ids)
    monkeypatch.setattr(grades, 'complete_vision', provider)
    response = client.post('/api/inventory/grades/ai-analysis', json={'item_ids': ids})
    assert response.status_code == 409, response.text


def test_invalid_selection_is_rejected_without_provider(grade_app):
    factory, client, _ = grade_app
    ids = selection(factory)
    for selected, status in (([ids[0]], 422), ([ids[0], ids[0]], 422),
                             ([ids[0], str(uuid.uuid4())], 404),
                             ([str(uuid.uuid4()) for _ in range(25)], 422)):
        assert client.post('/api/inventory/grades/ai-analysis', json={
            'item_ids': selected}).status_code == status


def test_server_guardrails_lower_confidence_and_keep_every_warning_bounded(grade_app, monkeypatch):
    factory, client, _ = grade_app
    with factory() as db:
        first = add(db, name='Polo 102', size='S')
        second = add(db, name='Polo 900', size='P')
        second.brand = 'Outra marca'
        db.commit()
        ids = [str(first.id), str(second.id)]
    monkeypatch.setattr(grades, 'complete_vision', lambda **_: advice(
        ids, warnings=[f'Incerteza do modelo {index}' for index in range(8)]))
    response = client.post('/api/inventory/grades/ai-analysis', json={'item_ids': ids})
    assert response.status_code == 200, response.text
    result = response.json()['suggestions'][0]
    assert result['confidence'] == 'low' and len(result['warnings']) == 8
    assert any('tamanho/cor' in warning for warning in result['warnings'])
    assert any('números de modelo' in warning for warning in result['warnings'])
    assert any('marcas ou categorias' in warning for warning in result['warnings'])


def test_image_payload_is_bounded_and_text_only_fallback_is_visible(grade_app, monkeypatch):
    factory, client, _ = grade_app
    ids = selection(factory, image=picture())
    image = grades.prepare_label_image(picture())
    monkeypatch.setattr(grades, 'MAX_PHOTO_PAYLOAD', len(image.data))
    blocks = []
    def provider(**kwargs):
        blocks.extend(kwargs['messages'][0]['content'])
        return advice(ids)
    monkeypatch.setattr(grades, 'complete_vision', provider)
    response = client.post('/api/inventory/grades/ai-analysis', json={'item_ids': ids})
    assert response.status_code == 200, response.text
    assert response.json()['photos_analyzed'] == 1
    assert any('Limite total de fotos' in warning for warning in response.json()['warnings'])
    assert len([block for block in blocks if block['type'] == 'image']) == 1


def test_text_only_deepseek_configuration_is_rejected_without_sending_photos(grade_app, monkeypatch):
    factory, client, _ = grade_app
    monkeypatch.setattr(settings, 'DEEPSEEK_VISION_MODEL', 'deepseek-reasoner')
    response = client.post('/api/inventory/grades/ai-analysis', json={
        'item_ids': selection(factory, image=picture())})
    assert response.status_code == 503


def test_preview_does_not_write_or_embed_sensitive_fields_and_commit_only_links(grade_app):
    factory, client, _ = grade_app
    ids = selection(factory, image='PRIVATE-PHOTO')
    with factory() as db:
        before = {identity: (db.get(Item, uuid.UUID(identity)).sku_internal,
            db.get(Item, uuid.UUID(identity)).barcode) for identity in ids}
    response = preview(client, ids)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['existing_members'] == [] and result['source_groups'] == []
    claims = jwt.decode(result['preview_token'], settings.SECRET_KEY, algorithms=['HS256'])
    assert claims['exp'] - claims['iat'] == grades.PREVIEW_TTL
    assert all(key not in json.dumps(claims) for key in ('PRIVATE-PHOTO', 'cost_price', 'sale_price', 'stock_loja'))
    with factory() as db:
        assert all(db.get(Item, uuid.UUID(identity)).group_key is None for identity in ids)
        assert db.query(AuditEvent).count() == 0
    confirmed = commit(client, result['preview_token'])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()['applied_count'] == 2 and not confirmed.json()['already_applied']
    with factory() as db:
        for identity in ids:
            row = db.get(Item, uuid.UUID(identity))
            assert row.group_key == 'Grade conferida'
            assert (row.sku_internal, row.barcode) == before[identity]
            assert (row.current_stock, row.stock_loja, row.stock_deposito) == (10, 3, 7)
            assert (row.cost_price, row.sale_price, row.image_data) == (8, 15, 'PRIVATE-PHOTO')
        assert db.query(StockMovement).count() == 0
        assert db.query(AuditEvent).filter_by(action='grade_link').count() == 1
    replay = commit(client, result['preview_token'])
    assert replay.status_code == 200, replay.text
    assert replay.json()['already_applied'] is True and replay.json()['applied_count'] == 0


@pytest.mark.parametrize('change', ['name', 'photo', 'stock', 'deleted', 'membership'])
def test_preview_is_invalidated_by_product_changes_and_never_partially_applies(grade_app, change):
    factory, client, _ = grade_app
    ids = selection(factory)
    token = preview(client, ids).json()['preview_token']
    with factory() as db:
        row = db.get(Item, uuid.UUID(ids[0]))
        if change == 'name': row.name = 'Outro modelo'
        elif change == 'photo': row.image_data = 'CHANGED-PHOTO'
        elif change == 'stock': row.stock_loja += 1; row.current_stock += 1
        elif change == 'deleted': row.deleted_at = settings.now()
        else: row.group_key = 'Grade concorrente'
        db.commit()
    assert commit(client, token).status_code == 409
    with factory() as db:
        assert db.get(Item, uuid.UUID(ids[1])).group_key is None
        assert db.query(AuditEvent).count() == db.query(StockMovement).count() == 0


def test_retry_rejects_changes_after_success(grade_app):
    factory, client, _ = grade_app
    ids = selection(factory)
    token = preview(client, ids).json()['preview_token']
    assert commit(client, token).status_code == 200
    with factory() as db:
        row = db.get(Item, uuid.UUID(ids[0]))
        row.stock_deposito += 1
        row.current_stock += 1
        db.commit()
    assert commit(client, token).status_code == 409


def test_existing_destination_members_are_shown_and_outside_inactive_variant_conflicts(grade_app):
    factory, client, _ = grade_app
    ids = selection(factory)
    with factory() as db:
        destination = add(db, size='L', group_key='Existente')
        inactive = add(db, size='XL', group_key='Existente', active=False)
        db.commit()
        destination_ids = {str(destination.id), str(inactive.id)}
    response = preview(client, ids, new_group_name=None, target_group_key='Existente')
    assert response.status_code == 200, response.text
    assert {row['id'] for row in response.json()['existing_members']} == destination_ids
    with factory() as db:
        add(db, size='P', group_key='Existente', active=False)
        db.commit()
    # Destination changed after review, even though the conflicting row is inactive.
    assert commit(client, response.json()['preview_token']).status_code == 409
    response = preview(client, ids, new_group_name=None, target_group_key='Existente')
    assert response.status_code == 409, response.text


def test_moves_include_source_counts_and_preserve_unselected_members(grade_app):
    factory, client, _ = grade_app
    ids = selection(factory, group_key='Origem')
    with factory() as db:
        remaining = add(db, size='L', group_key='Origem')
        db.commit()
        remaining_id = remaining.id
    response = preview(client, ids)
    assert response.status_code == 200, response.text
    assert response.json()['source_groups'] == [{'group_key': 'Origem', 'moving_count': 2, 'remaining_count': 1}]
    assert commit(client, response.json()['preview_token']).status_code == 200
    with factory() as db:
        assert db.get(Item, remaining_id).group_key == 'Origem'


@pytest.mark.parametrize('kind', ['expired', 'another_user', 'tampered'])
def test_signed_preview_is_user_bound_expiring_and_tamper_resistant(grade_app, kind):
    factory, client, _ = grade_app
    token = preview(client, selection(factory)).json()['preview_token']
    if kind == 'tampered':
        token = token[:-6] + ('AAAAAA' if not token.endswith('AAAAAA') else 'BBBBBB')
    else:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        if kind == 'expired':
            claims['iat'] = int(time.time()) - grades.PREVIEW_TTL - 1
            claims['exp'] = int(time.time()) - 1
        else:
            claims['sub'] = str(uuid.uuid4())
        token = jwt.encode(claims, settings.SECRET_KEY, algorithm='HS256')
    assert commit(client, token).status_code == 409


def test_commit_requires_confirmation_and_preview_checks_analysis_versions(grade_app, monkeypatch):
    factory, client, _ = grade_app
    ids = selection(factory)
    monkeypatch.setattr(grades, 'complete_vision', lambda **_: advice(ids))
    analysis = client.post('/api/inventory/grades/ai-analysis', json={'item_ids': ids}).json()
    versions = {row['id']: row['version'] for row in analysis['products']}
    response = preview(client, ids, expected_versions=versions)
    assert response.status_code == 200, response.text
    for confirmation in (False, 1, 'true'):
        assert client.post('/api/inventory/grades/commit', json={
            'preview_token': response.json()['preview_token'], 'confirmed': confirmation}).status_code == 422
    with factory() as db:
        db.get(Item, uuid.UUID(ids[0])).name = 'Produto alterado'
        db.commit()
    assert preview(client, ids, expected_versions=versions).status_code == 409


def test_destination_limit_is_enforced_without_loading_originals(grade_app):
    factory, client, _ = grade_app
    ids = selection(factory)
    with factory() as db:
        for index in range(501):
            add(db, size=str(index), color='Preto', group_key='Grande', image='PRIVATE-PHOTO')
        db.commit()
    response = preview(client, ids, new_group_name=None, target_group_key='Grande')
    assert response.status_code == 409 and '500' in response.text


@pytest.fixture
def grade_pg(pg, monkeypatch):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    monkeypatch.setattr(settings, 'SECRET_KEY', 'grade-tests-only-signing-key-32-characters')
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in
            (Usuario, Vendedor, Supplier, Item, StockMovement, AuditEvent)])
        factory = sessionmaker(bind=isolated, autoflush=False)
        with factory() as db:
            user = Usuario(nome='Gestor de teste', email='grades@example.test', senha_hash='unused',
                           role=UsuarioRole.GERENTE)
            db.add(user)
            db.commit()
            user_id = user.id
        yield factory, user_id
    finally:
        isolated.dispose()


def test_concurrent_postgres_confirmations_have_one_durable_receipt(grade_pg):
    factory, user_id = grade_pg
    ids = selection(factory)
    with factory() as db:
        result = grades.preview_grade_links(db, GradeLinkPreviewRequest(
            item_ids=ids, new_group_name='Grade atômica'), db.get(Usuario, user_id))
    request = GradeLinkCommitRequest(preview_token=result['preview_token'], confirmed=True)
    barrier = Barrier(2)
    def apply():
        with factory() as db:
            user = db.get(Usuario, user_id)
            barrier.wait(timeout=5)
            return grades.commit_grade_links(db, request, user)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=15) for future in [pool.submit(apply), pool.submit(apply)]]
    assert sorted(row['already_applied'] for row in results) == [False, True]
    assert sorted(row['applied_count'] for row in results) == [0, 2]
    with factory() as db:
        assert db.query(AuditEvent).filter_by(action='grade_link').count() == 1
        assert db.query(Item).filter_by(group_key='Grade atômica').count() == 2
        assert db.query(StockMovement).count() == 0


def test_concurrent_postgres_selections_serialize_destination_snapshot(grade_pg):
    factory, user_id = grade_pg
    ids_a, ids_b = selection(factory), selection(factory)
    with factory() as db:
        add(db, size='L', group_key='Destino')
        db.commit()
    tokens = []
    for ids in (ids_a, ids_b):
        with factory() as db:
            result = grades.preview_grade_links(db, GradeLinkPreviewRequest(
                item_ids=ids, target_group_key='Destino'), db.get(Usuario, user_id))
            tokens.append(result['preview_token'])
    barrier = Barrier(2)
    def apply(token):
        with factory() as db:
            user = db.get(Usuario, user_id)
            barrier.wait(timeout=5)
            try:
                grades.commit_grade_links(db, GradeLinkCommitRequest(
                    preview_token=token, confirmed=True), user)
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, tokens))
    assert sorted(results) == [200, 409]
    with factory() as db:
        assert db.query(Item).filter_by(group_key='Destino').count() == 3
        assert db.query(Item).filter(Item.group_key.is_(None)).count() == 2
        assert db.query(AuditEvent).filter_by(action='grade_link').count() == 1


def test_postgres_receipt_failure_rolls_back_every_membership(grade_pg, monkeypatch):
    factory, user_id = grade_pg
    ids = selection(factory)
    with factory() as db:
        result = grades.preview_grade_links(db, GradeLinkPreviewRequest(
            item_ids=ids, new_group_name='Não aplicar'), db.get(Usuario, user_id))
    def reject_receipt(*_):
        raise RuntimeError('Synthetic receipt failure')
    sa.event.listen(AuditEvent, 'before_insert', reject_receipt)
    try:
        with factory() as db:
            with pytest.raises(RuntimeError, match='Synthetic receipt failure'):
                grades.commit_grade_links(db, GradeLinkCommitRequest(
                    preview_token=result['preview_token'], confirmed=True), db.get(Usuario, user_id))
    finally:
        sa.event.remove(AuditEvent, 'before_insert', reject_receipt)
    with factory() as db:
        assert db.query(Item).filter(Item.group_key.isnot(None)).count() == 0
        assert db.query(AuditEvent).count() == db.query(StockMovement).count() == 0


def test_postgres_reviewed_commit_shares_lock_with_existing_grade_attachment(grade_pg):
    from app.services.inventory_grade_management import attach_existing_grade
    factory, user_id = grade_pg
    ids = selection(factory)
    with factory() as db:
        add(db, size='L', group_key='Destino')
        legacy_candidate = add(db, size='P')
        db.commit()
        candidate_id = legacy_candidate.id
        result = grades.preview_grade_links(db, GradeLinkPreviewRequest(
            item_ids=ids, target_group_key='Destino'), db.get(Usuario, user_id))
    barrier = Barrier(2)
    def reviewed():
        with factory() as db:
            user = db.get(Usuario, user_id)
            barrier.wait(timeout=5)
            try:
                grades.commit_grade_links(db, GradeLinkCommitRequest(
                    preview_token=result['preview_token'], confirmed=True), user)
                return 200
            except HTTPException as exc:
                return exc.status_code
    def legacy():
        with factory() as db:
            barrier.wait(timeout=5)
            try:
                attach_existing_grade(db, candidate_id, 'Destino', None)
                return 200
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=15) for future in [pool.submit(reviewed), pool.submit(legacy)]]
    assert sorted(results) == [200, 409]
    with factory() as db:
        members = db.query(Item).filter_by(group_key='Destino').all()
        assert len({grades.variant_identity(row.size, row.color) for row in members}) == len(members)
        assert sum(db.get(Item, uuid.UUID(identity)).group_key == 'Destino' for identity in ids) in (0, 2)


def test_confirmed_grade_receipt_shares_request_with_membership_audit(grade_app):
    factory, _, user_id = grade_app
    ids = selection(factory)
    with factory() as db:
        user = db.get(Usuario, user_id)
        db.info['audit_enabled'] = True
        grades.bind_actor(db, user, request_id='synthetic-grade-operation', route='/api/inventory/grades/commit', method='POST')
        planned = grades.preview_grade_links(db, GradeLinkPreviewRequest(item_ids=ids, new_group_name='Grade da auditoria'), user)
        grades.commit_grade_links(db, GradeLinkCommitRequest(preview_token=planned['preview_token'], confirmed=True), user)
        events = db.query(AuditEvent).all()
        assert len(events) >= 3
        assert {event.request_id for event in events} == {'synthetic-grade-operation'}
        assert any(event.action == 'grade_link' for event in events)
