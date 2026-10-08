"""Names/model references preserve reviewed casing; facets/search still fold it."""
import uuid

from test_assistant import setup, incoming
from test_inventory_ocr import stock_app
from test_product_intake_grade import manager_stock_app
from app.models.inventory import Item
from app.models.assistant import AssistantAction
from app.services.assistant_channels import authorized_identity
from app.services.assistant_inventory import ItemsArgs, prepare_inventory, confirm_inventory, duplicate_items


def test_create_edit_and_case_insensitive_search_preserve_product_reference(manager_stock_app):
    factory, client, _ = manager_stock_app
    name = 'Tênis Givenchy DN0281'
    created = client.post('/api/inventory/items', json={
        'name': name, 'brand': 'gIVENCHY', 'category': 'CALÇADOS > tênis', 'color': 'PRETO', 'size': '11',
    })
    assert created.status_code == 201, created.text
    row = created.json()
    assert row['name'] == name
    assert (row['brand'], row['category'], row['color']) == ('Givenchy', 'Calçados > Tênis', 'Preto')
    for edited_name in ['TÊNIS GIVENCHY DN0281', 'Tênis Givenchy dN0281', name]:
        updated = client.put(f"/api/inventory/items/{row['id']}", json={'name': edited_name})
        assert updated.status_code == 200, updated.text
        assert updated.json()['name'] == edited_name
        # Name display and matching intentionally have different normalization.
        found = client.get('/api/inventory/items', params={'search': 'tenis GIVENCHY dn0281', 'brand': 'GIVENCHY', 'color': 'preto'}).json()
        assert found['total'] == 1 and found['items'][0]['name'] == edited_name
    with factory() as db:
        assert db.get(Item, uuid.UUID(row['id'])).name == name


def test_grade_new_variants_and_edited_copy_keep_name_casing(manager_stock_app):
    _, client, _ = manager_stock_app
    name = 'Tênis Givenchy DN0281'
    created = client.post('/api/inventory/items/grade', json={
        'name': name, 'sizes': ['11', '12'], 'brand': 'GIVENCHY', 'color': 'PRETO',
        'category': 'CALÇADOS > tênis', 'initial_stock': 0,
    })
    assert created.status_code == 201, created.text
    rows = created.json()['items']
    assert [r['name'] for r in rows] == [name + ' 11', name + ' 12']
    assert all(r['brand'] == 'Givenchy' and r['color'] == 'Preto' for r in rows)
    assert created.json()['group_key'] == name + ' Preto'
    url = f"/api/inventory/items/{rows[0]['id']}"
    context = client.get(url + '/variants').json()
    variants = client.post(url + '/variants', json={
        'model_name': context['model_name'], 'source_version': context['source_version'],
        'sizes': ['13'], 'confirm': True,
    })
    assert variants.status_code == 201, variants.text
    assert variants.json()['created'][0]['name'] == name + ' 13'
    context = client.get(url + '/variants').json()
    copy = client.post(url + '/duplicate', json={
        'source_version': context['source_version'], 'request_id': str(uuid.uuid4()), 'confirm': True,
        'keep_group': False, 'item': {'name': 'TÊNIS GIVENCHY DN0281-B', 'size': '10'},
    })
    assert copy.status_code == 201, copy.text
    assert copy.json()['name'] == 'TÊNIS GIVENCHY DN0281-B'


def test_bot_saves_confirmed_casing_and_still_detects_case_only_duplicates(manager_stock_app):
    factory, _, uid = manager_stock_app
    with factory() as db:
        args = ItemsArgs(itens=[{'nome': 'Tênis Givenchy DN0281', 'marca': 'GIVENCHY',
                                'categoria': 'Calçados > Tênis', 'cor': 'PRETO', 'tamanho': '11'}])
        message = incoming(db, uid, 'Cadastre Tênis Givenchy DN0281', channel='telegram')
        prepared = prepare_inventory(db, message, authorized_identity(db, 'telegram', '123'), 'preparar_itens', args)
        assert 'confirmacao' in prepared
        assert db.query(Item).count() == 0
        action = db.query(AssistantAction).one()
        answer = confirm_inventory(db, message, action)
        db.commit()
        item = db.query(Item).one()
        assert item.name == 'Tênis Givenchy DN0281' and item.name in answer
        assert (item.brand, item.category, item.color) == ('Givenchy', 'Calçados > Tênis', 'Preto')
        data = args.model_dump(mode='json')['itens']
        data[0]['nome'] = 'tênis givenchy dn0281'
        data[0]['marca'] = 'givenchy'
        assert len(duplicate_items(db, data)) == 1
