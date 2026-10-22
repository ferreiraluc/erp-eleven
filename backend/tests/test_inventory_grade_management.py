"""Grade suggestions remain advisory; explicit membership preserves item identity."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from test_assistant import setup
from test_inventory_ocr import stock_app
from test_product_intake_grade import manager_stock_app
from test_access_postgres import pg
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier, StockMovement
from app.schemas.inventory_variants import VariantCreateRequest
from app.services.inventory_variants import create_variants, source_version
from app.models.access import AuditEvent
from app.services.user_audit import bind_actor
from app.services.inventory_grade_management import attach_existing_grade, model_name


def add_item(db, name, *, size=None, color=None, group_key=None, brand='Boss',
             category='Acessórios > Bonés', stock=2, image_data=None):
    row = Item(name=name, size=size, color=color, group_key=group_key, brand=brand,
               category=category, unit='un', current_stock=stock,
               stock_loja=stock, stock_deposito=0, sku_internal=f'SKU-{uuid.uuid4().hex}',
               barcode='SAME-BARCODE', image_data=image_data)
    db.add(row)
    db.flush()
    return row


def inventory_url(item):
    return f'/api/inventory/items/{item.id}'


def test_suggestions_match_model_across_colors_without_erasing_model_code(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        original = add_item(db, 'Boné Boss 2001020 Preto', color='Preto', group_key='grade-boss',
                            image_data='data:image/png;base64,' + 'x' * 100000)
        other = add_item(db, 'Boné Boss 2001020 Azul', color='Azul')
        different_code = add_item(db, 'Boné Boss 2002020 Azul', color='Azul')
        different_brand = add_item(db, 'Boné Boss 2001020 Branco', color='Branco', brand='Prada')
        another_color = add_item(db, 'Boné Boss 2001020 Verde', color='Verde')
        db.commit()
        ids = [row.id for row in (original, other, different_code, different_brand, another_color)]

    response = client.get(f'/api/inventory/groups/suggestions?group_key=grade-boss')
    assert response.status_code == 200, response.text
    assert {row['id'] for row in response.json()['items']} == {str(ids[1]), str(ids[4])}
    assert response.json()['items'][0]['image_data'] is None

    response = client.get(f'/api/inventory/items/{ids[1]}/grade-suggestions')
    assert response.status_code == 200, response.text
    assert response.json()['groups'] == [{
        'group_key': 'grade-boss', 'display_name': 'grade-boss', 'member_count': 1,
        'match_reason': 'Mesmo modelo, marca, categoria e unidade',
    }]
    assert client.get(f'/api/inventory/items/{ids[2]}/grade-suggestions').json()['groups'] == []
    legacy = client.get('/api/inventory/suggestions').json()
    assert len(legacy) == 1
    assert {row['id'] for row in legacy[0]['items']} == {str(ids[1]), str(ids[4])}
    assert model_name('Tênis Givenchy DN0281 11', '11', None) == 'Tênis Givenchy DN0281'
    assert model_name('Boné Boss 2001020', None, None) == 'Boné Boss 2001020'


def test_directory_is_bounded_searchable_and_preserves_human_grade_name(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        for number in range(30):
            add_item(db, f'Modelo {number}', group_key=f'Grade {number:02}',
                     color=f'Cor {number}')
        db.commit()
    data = client.get('/api/inventory/groups/directory', params={'limit': 5}).json()
    assert len(data['groups']) == 5
    assert all(row['member_count'] == 1 for row in data['groups'])
    data = client.get('/api/inventory/groups/directory', params={'search': 'Modelo 22'}).json()
    assert [row['group_key'] for row in data['groups']] == ['Grade 22']


def test_multicolor_generated_grade_shows_model_without_first_color(manager_stock_app):
    factory, client, _ = manager_stock_app
    key = 'Boné Boss 2001020 Preto'
    with factory() as db:
        add_item(db, 'Boné Boss 2001020 Azul', color='Azul', group_key=key)
        add_item(db, 'Boné Boss 2001020 Preto', color='Preto', group_key=key)
        db.commit()
    data = client.get('/api/inventory/groups/directory', params={'search': '2001020'}).json()
    assert data['groups'] == [{'group_key': key, 'display_name': 'Boné Boss 2001020',
                               'member_count': 2}]


def test_grade_members_are_paginated_and_ignore_catalog_filters(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        ids = [add_item(db, f'Camisa M {color}', size='M', color=color,
                        group_key='camisa', image_data='data:image/png;base64,fixture').id
               for color in ('Azul', 'Branco', 'Preto')]
        db.commit()
    first = client.get('/api/inventory/groups/members', params={
        'group_key': 'camisa', 'limit': 2}).json()
    second = client.get('/api/inventory/groups/members', params={
        'group_key': 'camisa', 'limit': 2, 'page': 2}).json()
    assert first['total'] == second['total'] == 3
    assert len(first['items']) == 2 and len(second['items']) == 1
    assert {row['id'] for row in first['items'] + second['items']} == {str(row) for row in ids}
    assert all(row['image_data'] is None and row['has_image'] for row in first['items'] + second['items'])


def test_attach_move_and_detach_do_not_touch_stock_or_identity(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        first = add_item(db, 'Boné Boss 2001020 Preto', color='Preto', group_key='grade-1')
        second = add_item(db, 'Boné Boss 2001020 Branco', color='Branco', group_key='grade-2')
        candidate = add_item(db, 'Boné Boss 2001020 Azul', color='Azul', stock=7)
        db.commit()
        ids = [row.id for row in (first, second, candidate)]
        prior = (candidate.sku_internal, candidate.barcode, candidate.current_stock,
                 candidate.stock_loja, candidate.stock_deposito)

    url = f'/api/inventory/items/{ids[2]}/grade'
    response = client.post(url, json={'group_key': 'grade-1', 'expected_group_key': None})
    assert response.status_code == 200, response.text
    assert response.json()['previous_group_key'] is None
    assert client.post(url, json={'group_key': 'grade-1', 'expected_group_key': None}).status_code == 200
    stale = client.post(url, json={'group_key': 'grade-2', 'expected_group_key': None})
    assert stale.status_code == 409
    moved = client.post(url, json={'group_key': 'grade-2', 'expected_group_key': 'grade-1'})
    assert moved.status_code == 200, moved.text
    assert moved.json()['previous_group_key'] == 'grade-1'
    stale_delete = client.delete(f'/api/inventory/items/{ids[2]}/group',
                                 params={'expected_group_key': 'grade-1'})
    assert stale_delete.status_code == 409
    removed = client.delete(f'/api/inventory/items/{ids[2]}/group',
                            params={'expected_group_key': 'grade-2'})
    assert removed.status_code == 200, removed.text
    assert removed.json()['previous_group_key'] == 'grade-2'
    with factory() as db:
        row = db.get(Item, ids[2])
        assert row.group_key is None
        assert (row.sku_internal, row.barcode, row.current_stock,
                row.stock_loja, row.stock_deposito) == prior
        assert db.query(StockMovement).count() == 0


def test_attach_rejects_missing_grade_and_duplicate_variant(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        target = add_item(db, 'Camiseta Boss S', size='S', color='Preto',
                          group_key='grade-shirt', category='Camisetas')
        duplicate = add_item(db, 'Camiseta Boss P', size='P', color='preto',
                             category='Camisetas')
        unique = add_item(db, 'Camiseta Boss M', size='M', color='Azul',
                          category='Camisetas')
        inactive = add_item(db, 'Camiseta Boss L', size='L', color='Verde',
                            group_key='grade-shirt', category='Camisetas')
        inactive.is_active = False
        inactive_duplicate = add_item(db, 'Camiseta Boss G', size='G', color='Verde',
                                      category='Camisetas')
        db.commit()
        ids = [row.id for row in (target, duplicate, unique, inactive_duplicate)]
    for item_id, group_key, expected in ((ids[1], 'grade-shirt', 409),
                                         (ids[2], 'does-not-exist', 404),
                                         (ids[3], 'grade-shirt', 409)):
        response = client.post(f'/api/inventory/items/{item_id}/grade',
                               json={'group_key': group_key, 'expected_group_key': None})
        assert response.status_code == expected, response.text
    with factory() as db:
        assert all(db.get(Item, id).group_key is None for id in ids[1:])


def test_legacy_empty_group_key_is_ungrouped(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        add_item(db, 'Boné Boss 2001020 Preto', color='Preto', group_key='grade-boss')
        candidate = add_item(db, 'Boné Boss 2001020 Azul', color='Azul', group_key='')
        db.commit()
        candidate_id = candidate.id
    response = client.post(f'/api/inventory/items/{candidate_id}/grade', json={
        'group_key': 'grade-boss', 'expected_group_key': None})
    assert response.status_code == 200, response.text
    assert response.json()['previous_group_key'] is None


def test_grade_writes_require_manager_and_legacy_routes_cannot_overwrite(stock_app):
    factory, client, user_id = stock_app
    with factory() as db:
        target = add_item(db, 'Boné Boss Preto', color='Preto', group_key='grade-a')
        candidate = add_item(db, 'Boné Boss Azul', color='Azul')
        db.commit()
        ids = [target.id, candidate.id]
    for method, path, payload in [
        ('post', f'/api/inventory/items/{ids[1]}/grade', {'group_key': 'grade-a', 'expected_group_key': None}),
        ('delete', f'/api/inventory/items/{ids[0]}/group', None),
        ('post', '/api/inventory/items/ungroup', {'group_key': 'grade-a'}),
        ('patch', '/api/inventory/groups', {'old_key': 'grade-a', 'new_key': 'another'}),
        ('post', '/api/inventory/items/group', {'item_ids': [str(ids[1])], 'group_key': 'grade-a'}),
        ('patch', '/api/inventory/items/batch', {'item_ids': [str(ids[1])],
                                                'sizes': [{'id': str(ids[1]), 'group_key': 'grade-a'}]}),
    ]:
        response = getattr(client, method)(path, json=payload) if payload else getattr(client, method)(path)
        assert response.status_code == 403, response.text
    with factory() as db:
        assert db.get(Item, ids[0]).group_key == 'grade-a'
        assert db.get(Item, ids[1]).group_key is None


def test_legacy_batch_and_rename_reject_accidental_merges(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        left = add_item(db, 'Boné Boss Preto', color='Preto', group_key='left')
        right = add_item(db, 'Boné Boss Azul', color='Azul', group_key='right')
        free = add_item(db, 'Boné Boss Branco', color='Branco')
        db.commit()
        ids = [row.id for row in (left, right, free)]
    rename = client.patch('/api/inventory/groups', json={'old_key': 'left', 'new_key': 'right'})
    assert rename.status_code == 409
    overwrite = client.post('/api/inventory/items/group', json={
        'item_ids': [str(ids[0]), str(ids[2])], 'group_key': 'right'})
    assert overwrite.status_code == 409
    missing = client.post('/api/inventory/items/group', json={
        'item_ids': [str(ids[2]), str(uuid.uuid4())], 'group_key': 'right'})
    assert missing.status_code == 404
    with factory() as db:
        assert [db.get(Item, row).group_key for row in ids] == ['left', 'right', None]


def test_create_grade_allows_color_matrix_but_rejects_collisions(manager_stock_app):
    factory, client, _ = manager_stock_app
    key = 'grade-' + str(uuid.uuid4())
    for color in ('Branco', 'Azul'):
        response = client.post('/api/inventory/items/grade/quantities', json={
            'name': 'Boné Boss', 'brand': 'Boss', 'category': 'Acessórios > Bonés',
            'color': color, 'sizes': ['S', 'M'], 'group_key': key,
            'stock_by_size': {'S': 2, 'M': 3}})
        assert response.status_code == 201, response.text
    collision = client.post('/api/inventory/items/grade/quantities', json={
        'name': 'Boné Boss', 'brand': 'Boss', 'category': 'Acessórios > Bonés',
        'color': 'Azul', 'sizes': ['M'], 'group_key': key})
    assert collision.status_code == 409, collision.text
    unrelated = client.post('/api/inventory/items/grade/quantities', json={
        'name': 'Boné Prada', 'brand': 'Prada', 'category': 'Acessórios > Bonés',
        'color': 'Preto', 'sizes': ['L'], 'group_key': key})
    assert unrelated.status_code == 409, unrelated.text
    with factory() as db:
        members = db.query(Item).filter(Item.group_key == key).all()
        assert len(members) == 4
        assert {(row.size, row.color) for row in members} == {
            ('S', 'Branco'), ('M', 'Branco'), ('S', 'Azul'), ('M', 'Azul')}
        assert db.query(StockMovement).count() == 4


def test_single_edit_cannot_silently_move_grade_and_mass_edit_checks_variant(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        target = add_item(db, 'Boné Boss Preto', color='Preto', group_key='grade-a')
        free = add_item(db, 'Boné Boss Preto', color='Preto')
        db.commit()
        ids = (target.id, free.id)
        baseline = free.updated_at.isoformat()
    direct = client.put(f'/api/inventory/items/{ids[1]}', json={
        'name': 'Boné Boss Preto', 'group_key': 'grade-a'})
    assert direct.status_code == 409
    bulk = client.patch('/api/inventory/items/batch', json={
        'item_ids': [str(ids[1])], 'sizes': [{
            'id': str(ids[1]), 'group_key': 'grade-a', 'expected_updated_at': baseline}]})
    assert bulk.status_code == 409
    with factory() as db:
        assert db.get(Item, ids[1]).group_key is None


def test_direct_item_create_and_size_edit_cannot_duplicate_grade_slot(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        first = add_item(db, 'Boné Boss S Preto', size='S', color='Preto', group_key='grade-boss')
        second = add_item(db, 'Boné Boss M Preto', size='M', color='Preto', group_key='grade-boss')
        db.commit()
        second_id = second.id
    create = client.post('/api/inventory/items', json={
        'name': 'Boné Boss P Preto', 'size': 'P', 'color': 'Preto',
        'brand': 'Boss', 'category': 'Acessórios > Bonés', 'group_key': 'grade-boss'})
    assert create.status_code == 409, create.text
    edit = client.put(f'/api/inventory/items/{second_id}', json={'size': 'P'})
    assert edit.status_code == 409, edit.text
    with factory() as db:
        assert db.get(Item, second_id).size == 'M'
        assert db.query(Item).filter(Item.group_key == 'grade-boss').count() == 2


def test_bulk_size_edit_cannot_duplicate_grade_slot(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        add_item(db, 'Boné Boss S Preto', size='S', color='Preto', group_key='grade-boss')
        second = add_item(db, 'Boné Boss M Preto', size='M', color='Preto', group_key='grade-boss')
        db.commit()
        second_id = second.id
    response = client.patch('/api/inventory/items/batch/details', json={
        'item_ids': [str(second_id)], 'sizes': [{'id': str(second_id), 'size': 'P'}]})
    assert response.status_code == 409, response.text
    with factory() as db:
        assert db.get(Item, second_id).size == 'M'


def test_explicit_grade_move_is_audited_with_previous_and_new_identity(manager_stock_app):
    factory, _, user_id = manager_stock_app
    with factory() as db:
        AuditEvent.__table__.create(db.bind, checkfirst=True)
        target = add_item(db, 'Boné Boss Preto', color='Preto', group_key='grade-a')
        item = add_item(db, 'Boné Boss Azul', color='Azul')
        db.commit()
        item_id = item.id
    with factory() as db:
        db.info['audit_enabled'] = True
        bind_actor(db, db.get(Usuario, user_id))
        attach_existing_grade(db, item_id, 'grade-a', None)
    with factory() as db:
        event = db.query(AuditEvent).filter(AuditEvent.entity_id == str(item_id),
                                            AuditEvent.action == 'update').one()
        assert event.changes['group_key'] == {'before': None, 'after': 'grade-a'}


def test_concurrent_same_variant_attachments_serialize_in_postgres(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    try:
        with factory() as db:
            target = add_item(db, 'Boné Boss Preto', color='Preto', group_key='grade-a')
            one = add_item(db, 'Boné Boss Azul', color='Azul')
            two = add_item(db, 'Boné Boss Azul', color='Azul')
            db.commit()
            ids = [one.id, two.id]
        barrier = Barrier(2)
        def attach(item_id):
            with factory() as db:
                barrier.wait(timeout=5)
                try:
                    attach_existing_grade(db, item_id, 'grade-a', None)
                    return 200
                except HTTPException as error:
                    db.rollback()
                    return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attach, ids)) == [200, 409]
        with factory() as db:
            assert sum(db.get(Item, id).group_key == 'grade-a' for id in ids) == 1
    finally:
        isolated.dispose()


def test_attach_and_variant_creation_share_grade_lock_in_postgres(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[m.__table__ for m in (
        Usuario, Vendedor, Supplier, Item, StockMovement)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    try:
        with factory() as db:
            user = Usuario(nome='Fixture', email='fixture-grade@example.com', senha_hash='unused')
            db.add(user)
            target = add_item(db, 'Boné Boss 2001020 Preto', size='S', color='Preto',
                              group_key='grade-boss')
            candidate = add_item(db, 'Boné Boss 2001020 Azul', size='M', color='Azul')
            db.commit()
            target_id, candidate_id, user_id = target.id, candidate.id, user.id
            version = source_version(target)
        request = VariantCreateRequest(model_name='Boné Boss 2001020',
            variants=[{'size': 'M', 'color': 'Azul', 'quantity': 0}],
            source_version=version, confirm=True)
        barrier = Barrier(2)

        def attach():
            with factory() as db:
                barrier.wait(timeout=5)
                try:
                    attach_existing_grade(db, candidate_id, 'grade-boss', None)
                    return 'attached'
                except HTTPException as error:
                    db.rollback()
                    assert error.status_code == 409
                    return 'conflict'

        def create():
            with factory() as db:
                barrier.wait(timeout=5)
                return create_variants(db, target_id, request, user_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            attach_future = pool.submit(attach)
            create_future = pool.submit(create)
            attach_result = attach_future.result(timeout=15)
            created = create_future.result(timeout=15)
        with factory() as db:
            matching = db.query(Item).filter(Item.group_key == 'grade-boss',
                Item.size == 'M', Item.color == 'Azul').all()
            assert len(matching) == 1
            if attach_result == 'attached':
                assert matching[0].id == candidate_id
                assert created['created'] == []
            else:
                assert created['created'][0].id == matching[0].id
                assert db.get(Item, candidate_id).group_key is None
    finally:
        isolated.dispose()
