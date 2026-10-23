"""Real lock/idempotency checks against disposable localhost PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
import uuid

from app.api.endpoints import printing, inventory_labels
from app.database import Base
from app.models.printing import PrintDevice, PrintJob
from app.models.inventory import Item
from app.models.address_book import PrintLayout
from test_access_postgres import pg
from test_pdv_stock_postgres import pdv_pg, item
from app.services.product_label_layouts import default_config


def test_concurrent_confirmation_claim_and_cancellation(pdv_pg):
    factory, client, *_ = pdv_pg
    client.app.include_router(printing.router, prefix='/api/printing')
    client.app.include_router(inventory_labels.router, prefix='/api/inventory-labels')
    with factory() as db:
        Base.metadata.create_all(db.get_bind())
    uid = item(factory)
    device = client.post('/api/inventory-labels/device', json={'confirm': True}).json()
    with factory() as db:
        product = db.get(Item, uid)
        line = dict(item_id=str(uid), name=product.name, code=product.inventory_code,
                    color=product.color, size=product.size, copies=3)
    body = dict(request_key=str(uuid.uuid4()), confirm=True, items=[line])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post('/api/inventory-labels/batches', json=body), range(2)))
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    batch = responses[0].json()
    assert responses[1].json()['id'] == batch['id']
    with factory() as db:
        assert db.query(PrintJob).count() == 1
        assert db.get(Item, uid).current_stock == 10
    headers = {'Authorization': 'Bearer '+device['token']}
    claim = {'product_labels': True, 'claim_key': str(uuid.uuid4())}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post('/api/printing/agent/claim', params=claim, headers=headers), range(2)))
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    cancelled = client.post('/api/inventory-labels/batches/'+batch['id']+'/cancel', json={'confirm': True}).json()
    assert cancelled['jobs'][0]['status'] == 'claimed'
    with factory() as db:
        assert db.query(PrintDevice).filter_by(purpose='product_labels').count() == 1


def test_concurrent_layout_edits_keep_one_revision_and_reject_stale_prints(pdv_pg):
    factory, client, *_ = pdv_pg
    client.app.include_router(printing.router, prefix='/api/printing')
    client.app.include_router(inventory_labels.router, prefix='/api/inventory-labels')
    with factory() as db:
        Base.metadata.create_all(db.get_bind())
    key = 'product-' + uuid.uuid4().hex[:20]
    url = '/api/inventory-labels/layouts/' + key
    body = dict(name='Modelo sintético', version=0, config=default_config())
    assert client.put(url, json=body).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda index: client.put(url, json={**body, 'version': 1, 'name': f'Modelo {index}'}), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    with factory() as db:
        assert db.get(PrintLayout, key).version == 2
    uid = item(factory)
    assert client.post('/api/inventory-labels/device', json={'confirm': True}).status_code == 200
    with factory() as db:
        product = db.get(Item, uid)
        line = dict(item_id=str(uid), name=product.name, code=product.inventory_code,
                    color=product.color, size=product.size, copies=1)
    request = dict(request_key=str(uuid.uuid4()), confirm=True, items=[line], layout_id=key, layout_revision=1)
    assert client.post('/api/inventory-labels/batches', json=request).status_code == 409
    with factory() as db:
        assert db.query(PrintJob).count() == 0
