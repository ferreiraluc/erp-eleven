"""Design previews and immutable print snapshots; no spooler or external service."""
from copy import deepcopy
import uuid

import pytest

from app.database import Base
from app.dependencies import get_current_active_user
from app.models.address_book import PrintLayout
from app.models.inventory import Item
from app.models.printing import PrintJob
from app.models.usuario import Usuario, UsuarioRole
from app.services import product_labels as labels
from app.services.product_label_layouts import default_config
from reportlab.graphics.barcode.qr import QrCodeWidget
from test_product_labels import label_env, setup_device, payload, enqueue, raster_from_zpl, raster_from_preview
from test_pdv_receipts import tickets
from test_pdv_unknown_stock import pdv_app


@pytest.fixture
def designs(label_env):
    factory, client, ids, lot = label_env
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[PrintLayout.__table__])
    return factory, client, ids


def save(client, config=None, key=None, version=0, name='Roupas'):
    key = key or 'product-' + uuid.uuid4().hex[:20]
    response = client.put('/api/inventory-labels/layouts/' + key,
                          json=dict(name=name, version=version, config=config or default_config()))
    assert response.status_code == 200, response.text
    return response.json()


def test_saved_models_are_shared_versioned_and_isolated_from_address_layouts(designs):
    factory, client, _ = designs
    with factory() as db:
        db.add(PrintLayout(id='br', name='Endereços', config={'font_size': 12}, version=3))
        db.commit()
    assert [l['id'] for l in client.get('/api/inventory-labels/layouts').json()] == ['standard']
    model = save(client)
    assert model['version'] == 1 and not model['builtin']
    listing = client.get('/api/inventory-labels/layouts').json()
    assert {l['id'] for l in listing} == {'standard', model['id']}
    assert client.put('/api/inventory-labels/layouts/br', json=dict(name='Invalid', version=3, config=default_config())).status_code == 422
    updated = save(client, key=model['id'], version=1, name='Calçados')
    assert updated['version'] == 2
    response = client.put('/api/inventory-labels/layouts/' + model['id'], json=dict(name='Old', version=1, config=default_config()))
    assert response.status_code == 409
    assert client.delete('/api/inventory-labels/layouts/' + model['id'], params={'version': 1}).status_code == 409
    assert client.delete('/api/inventory-labels/layouts/standard', params={'version': 1}).status_code == 404
    assert client.delete('/api/inventory-labels/layouts/' + model['id'], params={'version': 2}).status_code == 200
    with factory() as db:
        assert db.get(PrintLayout, 'br').version == 3


@pytest.mark.parametrize('change', ['outside', 'overlap', 'no-qr', 'hide-code', 'short-code', 'duplicates', 'unknown-font', 'raw-command'])
def test_invalid_designs_are_rejected_before_preview_or_saving(designs, change):
    _, client, _ = designs
    config = default_config()
    if change == 'outside': config['elements'][0]['x'] = 470
    elif change == 'overlap': config['elements'][1]['width'] = 400
    elif change == 'no-qr': config['elements'] = [e for e in config['elements'] if e['type'] != 'qr']
    elif change == 'hide-code': config['elements'][4]['visible'] = False
    elif change == 'short-code': config['elements'][4]['width'] = 30
    elif change == 'duplicates': config['elements'][1]['id'] = config['elements'][0]['id']
    elif change == 'unknown-font': config['elements'][0]['font'] = '../../secret'
    else: config['zpl'] = '^XA~JA^XZ'
    assert client.post('/api/inventory-labels/layouts/preview', json={'config': config}).status_code == 422
    assert client.put('/api/inventory-labels/layouts/product-' + 'a'*20, json=dict(name='Invalid', version=0, config=config)).status_code == 422


def test_design_preview_matches_queued_graphic_and_model_edits_do_not_change_jobs(designs):
    factory, client, ids = designs
    setup_device(client)
    config = default_config()
    config['elements'][0].update(text='ELEVEN ^XZ ~JA', font_size=30)
    config['elements'][1].update(lines=2, height=28, width=280, font='barlow')
    config['elements'][2]['visible'] = False
    model = save(client, config)
    body = payload(client, ids[:1], copies=2)
    body.update(layout_id=model['id'], layout_revision=model['version'])
    preview = client.get('/api/inventory-labels/preview/' + ids[0], params={'layout_id': model['id'], 'layout_revision': 1})
    assert preview.status_code == 200, preview.text
    batch = enqueue(client, body)
    with factory() as db:
        snap = deepcopy(db.get(PrintJob, uuid.UUID(batch['id'])).snapshot)
    assert snap['layout_version'] == 5 and snap['layout_config'] == model['config']
    raw = labels.render_zpl(snap)
    assert raw.count(b'^XZ') == 1 and b'~JA' not in raw and len(raw) <= 32768
    assert raster_from_zpl(raw).tobytes() == raster_from_preview(preview.content).tobytes()
    draft = client.post('/api/inventory-labels/layouts/preview', json={'config': model['config'], 'item_id': ids[0]})
    assert raster_from_preview(draft.content).tobytes() == raster_from_preview(preview.content).tobytes()
    config['elements'][0]['font_size'] = 20
    save(client, config, model['id'], version=1)
    assert client.get('/api/inventory-labels/preview/' + ids[0], params={'layout_id': model['id'], 'layout_revision': 1}).status_code == 409
    assert client.post('/api/inventory-labels/batches', json={**body, 'request_key': str(uuid.uuid4())}).status_code == 409
    assert enqueue(client, body)['id'] == batch['id']
    assert client.delete('/api/inventory-labels/layouts/' + model['id'], params={'version': 2}).status_code == 200
    assert enqueue(client, body)['id'] == batch['id']
    with factory() as db:
        assert labels.render_zpl(db.get(PrintJob, uuid.UUID(batch['id'])).snapshot) == raw
        assert db.query(PrintJob).count() == 1
    # Reusing an accepted key with a different model cannot create a new job.
    assert client.post('/api/inventory-labels/batches', json={**body, 'layout_revision': 2}).status_code == 409


def test_draft_preview_without_product_is_not_a_print_request_and_permissions_apply(designs):
    factory, client, ids = designs
    response = client.post('/api/inventory-labels/layouts/preview', json={'config': default_config()})
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    with factory() as db:
        assert db.query(PrintJob).count() == 0
        assert db.query(Item).count() == 3
        viewer = Usuario(nome='Consulta', email='view@synthetic.invalid', senha_hash='unused', role=UsuarioRole.VENDEDOR)
        db.add(viewer); db.commit(); db.refresh(viewer); db.expunge(viewer)
    client.app.dependency_overrides[get_current_active_user] = lambda: viewer
    assert client.get('/api/inventory-labels/layouts').status_code == 200
    assert client.put('/api/inventory-labels/layouts/product-' + 'b'*20, json=dict(name='Unauthorized', version=0, config=default_config())).status_code == 403
    assert client.delete('/api/inventory-labels/layouts/product-' + 'b'*20, params={'version': 1}).status_code == 403


@pytest.mark.parametrize('module_size', [2, 3, 4, 5])
def test_custom_qr_keeps_exact_identity_and_full_quiet_zone(module_size):
    config = default_config()
    for element in config['elements']:
        if element['type'] == 'qr':
            element.update(x=295, y=55, module_size=module_size)
        elif element['field'] == 'barcode':
            element['visible'] = False
        elif element['field'] != 'title':
            element['width'] = 250
    snap = dict(layout_version=5, layout_config=config, code='INV-WWWWWW', copies=1,
                name='Nome longo ^XZ ~JA', size='2XL', color='Navy', sale_price='0', sale_currency='USD')
    image = raster_from_zpl(labels.render_zpl(snap))
    qr = QrCodeWidget(snap['code'], barLevel='M', qrVersion=3); qr.qr.make()
    for row, bits in enumerate(qr.qr.modules):
        for col, dark in enumerate(bits):
            assert (image.getpixel((295 + (col+4)*module_size, 55 + (row+4)*module_size)) == 0) == bool(dark)
    size = 37 * module_size
    assert all(image.getpixel((x, 55)) == 255 and image.getpixel((x, 55 + size - 1)) == 255
               for x in range(295, 295 + size))
