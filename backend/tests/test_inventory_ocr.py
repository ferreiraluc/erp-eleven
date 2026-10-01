"""Read-only image parsing and stock conservation; no provider calls or live data."""
import base64
import io
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from test_assistant import setup
from app.api.endpoints import ocr, inventory
from app.config import settings
from app.database import Base, get_db
from app.dependencies import get_current_active_user
from app.models import Usuario
from app.models.inventory import Item, StockMovement, Supplier
from app.models.label_template import LabelTemplate
from app.services.ocr_images import prepare_label_image, OcrImageError, MAX_IMAGE_BYTES
from app.services.ocr_service import parse_label_image, validate_extraction, OcrProviderError
from app.services.inventory_service import create_movement, StockMovementError


def picture(format='PNG', size=(160, 100), exif=None):
    out = io.BytesIO()
    kwargs = {'exif': exif} if exif else {}
    Image.new('RGB', size, 'white').save(out, format=format, **kwargs)
    return f'data:image/{"jpeg" if format == "JPEG" else format.lower()};base64,' + base64.b64encode(out.getvalue()).decode()


def extracted(**changes):
    result = {'nome': 'AIR MAX', 'marca': 'NIKE', 'tamanho': '42', 'cor': None,
              'codigo_barras': '4006381333931', 'preco': 150.0, 'moeda': 'BRL',
              'texto_bruto': 'NIKE AIR MAX 42 4006381333931 R$ 150,00', 'qualidade': 'legivel',
              'evidencias': {'nome': 'AIR MAX', 'marca': 'NIKE', 'tamanho': '42',
                             'codigo_barras': '4006381333931', 'preco': 'R$ 150,00', 'moeda': 'R$'}}
    return {**result, **changes}


@pytest.fixture
def stock_app(setup):
    factory, _, user_id = setup
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[StockMovement.__table__, LabelTemplate.__table__, Supplier.__table__])
    app = FastAPI()
    app.include_router(ocr.router, prefix='/api/ocr')
    app.include_router(inventory.router, prefix='/api/inventory')
    def session():
        with factory() as db:
            yield db
    def user():
        with factory() as db:
            return db.get(Usuario, user_id)
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = user
    return factory, TestClient(app), user_id


def item(db, loja=3, deposito=7, **kwargs):
    row = Item(name='Camiseta', sku_internal=f'SKU-{db.query(Item).count()}', stock_loja=loja,
               stock_deposito=deposito, current_stock=loja+deposito, **kwargs)
    db.add(row); db.flush()
    return row


def test_image_validation_decodes_actual_content_and_removes_metadata():
    exif = Image.Exif(); exif[270] = 'Private original comment'
    image = prepare_label_image(picture('JPEG', (1800, 900), exif))
    assert image.media_type == 'image/jpeg' and image.width == 1600 and image.height == 800
    decoded = Image.open(io.BytesIO(base64.b64decode(image.data)))
    assert not decoded.getexif() and b'Private original comment' not in base64.b64decode(image.data)
    assert image.data_url.startswith('data:image/jpeg;base64,')


@pytest.mark.parametrize('value', [
    'data:image/jpeg;base64,NOT_BASE64',
    'data:image/jpeg;base64,' + base64.b64encode(b'not a picture').decode(),
    'data:image/svg+xml;base64,' + base64.b64encode(b'<svg/>').decode(),
    picture().replace('image/png', 'image/jpeg'),
    picture(size=(63, 64)), picture(size=(4097, 64)),
    'A' * (MAX_IMAGE_BYTES * 2),
])
def test_invalid_or_oversized_images_are_rejected(value):
    with pytest.raises(OcrImageError):
        prepare_label_image(value)


def test_animated_image_is_not_sent_to_provider():
    out = io.BytesIO()
    Image.new('RGB', (64, 64), 'white').save(out, format='WEBP', save_all=True,
        append_images=[Image.new('RGB', (64, 64), 'black')], duration=100, loop=0)
    with pytest.raises(OcrImageError):
        prepare_label_image(base64.b64encode(out.getvalue()).decode())


def test_extraction_requires_evidence_and_valid_barcode_without_repairing_it():
    parsed = validate_extraction(json.dumps(extracted(marca='ADIDAS', codigo_barras='4006381333932')))
    assert parsed.marca is None and parsed.codigo_barras is None
    assert parsed.nome == 'AIR MAX' and parsed.preco == 150
    assert 'unverified_marca' in parsed.avisos and 'invalid_barcode' in parsed.avisos
    assert parsed.requires_review is True


def test_ambiguous_currency_cannot_be_assumed_from_amount_or_country():
    data = extracted(texto_bruto='NIKE AIR MAX 42 4006381333931 $ 150', moeda='USD')
    data['evidencias'].update(preco='$ 150', moeda='$')
    parsed = validate_extraction(json.dumps(data))
    assert parsed.moeda is None and parsed.preco is None
    assert 'price_currency_missing' in parsed.avisos


def test_unreadable_image_never_fills_product_fields():
    parsed = validate_extraction(json.dumps(extracted(qualidade='ilegivel')))
    for key in ('nome', 'marca', 'tamanho', 'cor', 'codigo_barras', 'preco', 'moeda'):
        assert getattr(parsed, key) is None


@pytest.mark.parametrize('content', ['not-json', json.dumps(extracted(quantidade=10)), json.dumps(extracted(sku='invented')), json.dumps(extracted(preco=-1))])
def test_unexpected_or_malformed_provider_results_fail_closed(content):
    with pytest.raises(OcrProviderError):
        validate_extraction(content)


def test_provider_call_uses_sanitized_image_and_reference_brand_is_not_an_output(monkeypatch):
    monkeypatch.setattr(settings, "VISION_PROVIDER", "anthropic")
    import anthropic
    calls = []
    result = extracted(marca=None); result['evidencias'].pop('marca')
    fake = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: calls.append(kwargs) or
        SimpleNamespace(content=[SimpleNamespace(type='text', text=json.dumps(result))])))
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **_: fake)
    monkeypatch.setattr(settings, 'ANTHROPIC_API_KEY', 'fake-test-key')
    parsed = parse_label_image(picture(), brand='A brand supplied as context')
    assert parsed['marca'] is None
    image_block = calls[0]['messages'][-1]['content'][0]
    assert image_block['source']['media_type'] == 'image/jpeg'
    assert image_block['source']['data'] != picture().split(',')[1]
    assert 'tools' not in calls[0]


def test_parse_is_read_only_and_reports_existing_barcode(stock_app, monkeypatch):
    factory, client, _ = stock_app
    with factory() as db:
        item(db, barcode='4006381333931'); db.commit()
    monkeypatch.setattr('app.services.ocr_service.parse_label_image', lambda *_: validate_extraction(json.dumps(extracted())).model_dump())
    response = client.post('/api/ocr/parse', json={'image': picture()})
    assert response.status_code == 200 and response.json()['matches_total'] == 1
    assert response.json()['requires_review'] is True
    with factory() as db:
        assert db.query(Item).count() == 1 and db.query(StockMovement).count() == 0
        assert db.query(LabelTemplate).count() == 0


def test_parse_rejects_image_before_calling_provider(stock_app, monkeypatch):
    _, client, _ = stock_app
    monkeypatch.setattr('app.services.ocr_service.parse_label_image', lambda *_: pytest.fail('Provider called'))
    assert client.post('/api/ocr/parse', json={'image': 'broken'}).status_code == 422


def test_only_explicit_template_save_persists_sanitized_image(stock_app):
    factory, client, _ = stock_app
    raw = picture()
    response = client.post('/api/ocr/templates', json={'brand': 'Reviewed brand', 'sample_image': raw})
    assert response.status_code == 201
    with factory() as db:
        saved = db.query(LabelTemplate).one()
        assert saved.sample_image != raw and saved.sample_image.startswith('data:image/jpeg;base64,')
        assert db.query(Item).count() == db.query(StockMovement).count() == 0


@pytest.mark.parametrize(('movement', 'quantity', 'kwargs'), [
    ('transfer', 8, {'location_from': 'deposito', 'location_to': 'loja'}),
    ('exit', 4, {'location': 'loja'}), ('entry', -1, {}), ('entry', 0, {}),
    ('entry', 1.5, {}), ('entry', True, {}), ('transfer', 1, {'location_from': 'loja', 'location_to': 'loja'}),
    ('entry', 1, {'location': 'nowhere'}), ('unknown', 1, {}),
])
def test_invalid_movement_never_creates_or_destroys_units(stock_app, movement, quantity, kwargs):
    factory, _, user_id = stock_app
    with factory() as db:
        row = item(db)
        with pytest.raises(StockMovementError):
            create_movement(db, row.id, movement, quantity, user_id, **kwargs)
        assert (row.stock_loja, row.stock_deposito, row.current_stock) == (3, 7, 10)
        assert db.query(StockMovement).count() == 0


def test_transfer_conserves_total_and_movement_keeps_real_before_after(stock_app):
    factory, _, user_id = stock_app
    with factory() as db:
        row = item(db)
        move = create_movement(db, row.id, 'transfer', 4, user_id, location_from='deposito', location_to='loja')
        assert (row.stock_loja, row.stock_deposito, row.current_stock) == (7, 3, 10)
        assert move.quantity == 4 and move.quantity_before == move.quantity_after == 10
        exit_move = create_movement(db, row.id, 'exit', 2, user_id, location='loja')
        assert exit_move.quantity_before == 10 and exit_move.quantity_after == 8


def test_mismatch_requires_explicit_adjustment_and_zero_adjustment_is_valid(stock_app):
    factory, _, user_id = stock_app
    with factory() as db:
        row = item(db); row.current_stock = 50; db.flush()
        with pytest.raises(StockMovementError):
            create_movement(db, row.id, 'entry', 1, user_id)
        create_movement(db, row.id, 'adjustment', 0, user_id, location='loja')
        assert row.current_stock == row.stock_deposito == 7 and row.stock_loja == 0


def test_weighted_cost_is_preserved_and_pending_metadata_not_lost(stock_app):
    factory, _, user_id = stock_app
    with factory() as db:
        row = item(db, loja=5, deposito=0, cost_price=Decimal('10'))
        row.name = 'Nome revisado'
        create_movement(db, row.id, 'entry', 5, user_id, unit_cost=Decimal('20'))
        assert row.cost_price == 15 and row.name == 'Nome revisado'


def test_batch_transfer_failure_rolls_back_all_previous_items(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        first, second = item(db), item(db)
        ids = sorted([str(first.id), str(second.id)]); db.commit()
    response = client.post('/api/inventory/items/transfer-bulk', json={'direction': 'deposito_to_loja',
        'items': [{'item_id': ids[0], 'quantity': 2}, {'item_id': ids[1], 'quantity': 99}]})
    assert response.status_code == 409
    with factory() as db:
        assert all(row.current_stock == 10 and row.stock_loja == 3 and row.stock_deposito == 7 for row in db.query(Item))
        assert db.query(StockMovement).count() == 0


def test_batch_edit_failure_rolls_back_metadata_too(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        row = item(db); identity = str(row.id); db.commit()
    response = client.patch('/api/inventory/items/batch', json={'item_ids': [identity], 'brand': 'Must rollback',
        'stock_delta': -99, 'stock_reason': 'Test'})
    assert response.status_code == 409
    with factory() as db:
        assert db.query(Item).one().brand is None and db.query(StockMovement).count() == 0


def test_movement_api_serializes_valid_movement_and_rejects_insufficient_balance(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        row = item(db); identity = str(row.id); db.commit()
    ok = client.post('/api/inventory/movements', json={'item_id': identity, 'movement_type': 'entry', 'quantity': 2, 'location': 'loja'})
    assert ok.status_code == 201 and ok.json()['quantity_after'] == 12
    assert client.post('/api/inventory/movements', json={'item_id': identity, 'movement_type': 'exit', 'quantity': 99}).status_code == 409


def test_balance_is_refreshed_even_if_item_was_read_before_another_movement(stock_app):
    factory, _, user_id = stock_app
    with factory() as db:
        row = item(db, loja=10, deposito=0); identity = row.id; db.commit()
    with factory() as first:
        stale = first.get(Item, identity)
        assert stale.current_stock == 10
        with factory() as second:
            create_movement(second, identity, 'exit', 8, user_id); second.commit()
        with pytest.raises(StockMovementError):
            create_movement(first, identity, 'exit', 3, user_id)
        assert stale.stock_loja == stale.current_stock == 2


def test_csv_import_creates_location_balance_consistent_with_total(stock_app):
    from app.models.usuario import UsuarioRole
    factory, client, user_id = stock_app
    with factory() as db:
        db.get(Usuario, user_id).role = UsuarioRole.GERENTE; db.commit()
    response = client.post('/api/inventory/import/csv', files={'file': ('stock.csv', 'name,initial_stock\nTeste,4\n', 'text/csv')})
    assert response.status_code == 200 and response.json()['created'] == 1
    with factory() as db:
        row = db.query(Item).one()
        assert row.current_stock == row.stock_loja == 4 and row.stock_deposito == 0
        create_movement(db, row.id, 'exit', 1, user_id)
        assert row.current_stock == 3


def test_price_must_match_a_number_in_its_evidence():
    parsed = validate_extraction(json.dumps(extracted(preco=999)))
    assert parsed.preco is None and 'unverified_preco' in parsed.avisos
    data = extracted(preco=1234.56, texto_bruto='R$ 1.234,56')
    data['evidencias'].update(preco='R$ 1.234,56', moeda='R$')
    assert validate_extraction(json.dumps(data)).preco == 1234.56
