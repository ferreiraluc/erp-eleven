"""Photo drafts never write inventory; external providers are always mocked."""
import json
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.endpoints import product_photo as endpoint
from app.dependencies import get_current_active_user
from app.models.usuario import UsuarioRole
from app.schemas.product_photo import ProductPhotoResponse
from app.services import product_photo as service
from app.services.ocr_images import prepare_label_image
from test_inventory_ocr import picture


@pytest.fixture(autouse=True)
def reset_cache():
    service._cache.clear()
    service._requests.clear()
    yield
    service._cache.clear()
    service._requests.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(endpoint.router, prefix='/photo')
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id='operator', role=UsuarioRole.GERENTE)
    return TestClient(app)


def test_analysis_strips_unsupported_identity_and_never_accepts_stock(monkeypatch):
    calls = []
    def complete(**kwargs):
        calls.append(kwargs)
        return json.dumps({'name': 'Camiseta azul', 'brand': 'Guess', 'brand_evidence': '',
                           'size': 'M', 'size_evidence': 'M', 'single_product': True,
                           'quantity': 900, 'barcode': '12345', 'cost_price': 2})
    monkeypatch.setattr(service, 'complete_vision', complete)
    result = service.analyze(prepare_label_image(picture()))
    assert result.name == 'Camiseta azul' and not result.brand and result.size == 'M'
    assert not {'quantity', 'barcode', 'cost_price'}.intersection(result.model_dump())
    assert calls[0]['max_tokens'] == 650
    assert result.requires_review is True


def test_multiple_products_and_invalid_output_do_not_become_suggestions(monkeypatch):
    monkeypatch.setattr(service, 'complete_vision', lambda **kw: '{"single_product":false,"name":"Invented"}')
    assert service.analyze(prepare_label_image(picture())).name == ''
    monkeypatch.setattr(service, 'complete_vision', lambda **kw: 'not json')
    with pytest.raises(service.PhotoError, match='invalid_analysis'):
        service.analyze(prepare_label_image(picture()))


def test_permission_validation_and_confirmation_before_external_calls(client, monkeypatch):
    calls = []
    monkeypatch.setattr(service, 'edit_catalog', lambda image: calls.append(image))
    assert client.post('/photo/catalog', json={'image': picture()}).status_code == 422
    assert client.post('/photo/catalog', json={'image': picture(), 'confirmed': False}).status_code == 422
    assert client.post('/photo/analyze', json={'image': 'bad'}).status_code == 422
    client.app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id='seller', role=UsuarioRole.VENDEDOR)
    assert client.post('/photo/catalog', json={'image': picture(), 'confirmed': True}).status_code == 403
    assert not calls


def test_identical_photo_reuses_result_and_other_user_is_isolated(client, monkeypatch):
    calls = []
    def analyze(image):
        calls.append(image)
        return ProductPhotoResponse(name='Camisa', single_product=True)
    monkeypatch.setattr(service, 'analyze', analyze)
    for _ in range(2):
        result = client.post('/photo/analyze', json={'image': picture()})
        assert result.status_code == 200 and result.headers['cache-control'] == 'no-store'
    assert len(calls) == 1
    client.app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id='other', role=UsuarioRole.GERENTE)
    assert client.post('/photo/analyze', json={'image': picture()}).status_code == 200
    assert len(calls) == 2


def test_failed_or_overlapping_edit_is_not_repeated():
    image = prepare_label_image(picture())
    calls = []
    def fail(image):
        calls.append(1)
        with pytest.raises(service.PhotoError, match='in_progress'):
            service.bounded_call('user', 'catalog', image, fail)
        raise service.PhotoError('edit_uncertain')
    for _ in range(2):
        with pytest.raises(service.PhotoError, match='edit_uncertain'):
            service.bounded_call('user', 'catalog', image, fail)
    assert len(calls) == 1


def test_provider_request_is_single_low_cost_and_hides_failure(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, 'OPENAI_API_KEY', 'test-private-secret')
    monkeypatch.setattr(settings, 'PRODUCT_PHOTO_IMAGE_MODEL', 'gpt-image-1-mini')
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs)
        raise RuntimeError('private-secret should not leak')
    monkeypatch.setattr(service.requests, 'post', post)
    with pytest.raises(service.PhotoError, match='^edit_uncertain$'):
        service.edit_catalog(prepare_label_image(picture()))
    assert len(calls) == 1
    data = calls[0]['json']
    assert data['model'] == 'gpt-image-1-mini' and data['n'] == 1 and data['quality'] == 'low'
    assert data['size'] == '1024x1024' and len(data['images']) == 1
    assert calls[0]['allow_redirects'] is False
