"""Bag receipts reuse tickets without a sale or physical printer side effect."""
import hashlib
import io
import uuid

import pytest
from pypdf import PdfReader
from app.api.endpoints import pedidos_tickets, printing
from app.database import Base
from app.models.assistant import AssistantMessage
from app.models.assistant_whatsapp_media import WhatsAppMedia
from app.models.printing import PrintDevice, PrintJob
from app.models.pdv import PdvSale
from app.services import order_tickets
from test_order_reservations import orders, reserve, command, body, balances


@pytest.fixture
def tickets(orders):
    factory, client, *_ = orders
    client.app.include_router(pedidos_tickets.router, prefix='/api/pedidos')
    client.app.include_router(printing.router, prefix='/api/printing')
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[AssistantMessage.__table__, WhatsAppMedia.__table__])
        device = PrintDevice(name='3nStar QA', token_hash=hashlib.sha256(b'synthetic-key-for-isolated-test-123').hexdigest(),
            purpose='tickets', driver='escpos_tcp', paper_width_mm=80, paper_height_mm=0, auto_receipts=True)
        db.add(device); db.commit()
    return orders


def test_pdf_has_one_continuous_page_and_separation_identification_only(tickets):
    factory, client, cid, iid, *_ = tickets
    order = reserve(client, cid, iid, 2)
    url = f"/api/pedidos/{order['id']}/reserva/ticket"
    response = client.get(url)
    assert response.status_code == 200, response.text
    pdf = PdfReader(io.BytesIO(response.content))
    text = pdf.pages[0].extract_text()
    assert len(pdf.pages) == 1
    assert round(float(pdf.pages[0].mediabox.width) * 25.4 / 72) == 80
    for expected in ('ELEVEN', 'PEDIDO SEPARADO', 'Gustavo QA', 'Lucas QA', 'Separado:', 'Piezas: 2', 'Saldo pendiente: US$ 20,00'):
        assert expected in text
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(PrintJob).count() == 0
    assert balances(factory, iid) == (10, 6, 4, 2, 0)


def test_confirmed_print_is_immutable_idempotent_and_compatible_with_macos(tickets):
    factory, client, cid, iid, *_ = tickets
    order = reserve(client, cid, iid)
    url = f"/api/pedidos/{order['id']}/reserva/ticket"
    payload = command(1)
    assert client.post(url, json={**payload, 'confirm': False}).status_code == 422
    first = client.post(url, json=payload)
    assert first.status_code == 200, first.text
    job_id = first.json()['job']['id']
    assert client.post(url, json=payload).json()['job']['id'] == job_id
    assert client.post(url, json=command(1)).status_code == 409
    changed = body(cid, iid, 2); changed['expected_version'] = 1
    assert client.put(f"/api/pedidos/{order['id']}/reserva", json=changed).status_code == 200
    assert client.post(url, json=payload).json()['job']['id'] == job_id
    with factory() as db:
        saved = db.get(PrintJob, uuid.UUID(job_id))
        assert saved.snapshot['items'][0]['quantity'] == 1
    headers = {'Authorization': 'Bearer synthetic-key-for-isolated-test-123'}
    claim = client.post('/api/printing/agent/claim', headers=headers,
        params={'driver': 'escpos_tcp', 'continuous_tickets': True, 'claim_key': str(uuid.uuid4())})
    assert claim.status_code == 200, claim.text
    assert claim.json()['id'] == job_id
    assert claim.json()['profile'] == 'tickets' and claim.json()['paper_mode'] == 'continuous'
    pdf = client.get(f'/api/printing/agent/jobs/{job_id}/pdf', headers=headers)
    assert hashlib.sha256(pdf.content).hexdigest() == claim.json()['sha256']
    assert client.post(f'/api/printing/agent/jobs/{job_id}/result', headers=headers, json={'status': 'uncertain'}).status_code == 200
    assert client.get(url + '/status').json()['job']['status'] == 'uncertain'
    assert client.post(url, json=command(1)).status_code == 409  # stale print preview
    assert client.post(url, json=command(2)).status_code == 200  # explicit new copy


def test_other_sellers_cannot_print_or_download_someones_order(tickets):
    factory, client, cid, iid, control, other = tickets
    order = reserve(client, cid, iid)
    control['user_id'] = other
    url = f"/api/pedidos/{order['id']}/reserva/ticket"
    assert client.get(url).status_code == 404
    assert client.get(url + '/status').status_code == 404
    assert client.post(url, json=command(1)).status_code == 404


def test_cancelled_order_pdf_is_marked_and_cannot_be_enqueued(tickets):
    factory, client, cid, iid, *_ = tickets
    order = reserve(client, cid, iid)
    url = f"/api/pedidos/{order['id']}"
    assert client.post(url + '/cancelar', json=command(1, reason='Cancelamento sintético')).status_code == 200
    assert client.post(url + '/reserva/ticket', json=command(2)).status_code == 409
    pdf = PdfReader(io.BytesIO(client.get(url + '/reserva/ticket').content))
    assert 'RESERVA CANCELADA' in pdf.pages[0].extract_text()


def test_long_description_is_wrapped_without_html_interpretation(tickets):
    factory, client, cid, iid, *_ = tickets
    order = reserve(client, cid, iid)
    data = {**order, 'items': [{**order['items'][0], 'item_name': 'Camiseta <Boss> & algodón ' * 7}]}
    pdf = PdfReader(io.BytesIO(order_tickets.render(data)))
    assert len(pdf.pages) == 1
    assert '<Boss> &' in pdf.pages[0].extract_text()


def test_conditional_ticket_tracks_handoff_returns_and_keeps_queued_snapshot(tickets):
    factory, client, cid, iid, *_ = tickets
    order = reserve(client, cid, iid, 3)
    url = f"/api/pedidos/{order['id']}"
    response = client.post(url + '/condicional', json=command(1))
    assert response.status_code == 200, response.text
    ticket = url + '/reserva/ticket'
    queued = client.post(ticket, json=command(2))
    assert queued.status_code == 200, queued.text
    returned = client.post(url + '/devolver-itens', json=command(2,
        reason='Devolução sintética de uma peça', lines=[{'line_id': order['items'][0]['id'], 'quantity': 1}]))
    assert returned.status_code == 200, returned.text
    pdf_response = client.get(ticket)
    assert 'condicional' in pdf_response.headers['content-disposition']
    pdf = PdfReader(io.BytesIO(pdf_response.content))
    text = pdf.pages[0].extract_text()
    assert len(pdf.pages) == 1
    for expected in ('ENTREGA EN CONDICIONAL', 'PENDIENTE DE RESOLUCIÓN', 'Entregado:',
                     'Devueltas: 1', 'Por resolver: 2', 'Saldo pendiente: US$ 20,00', 'Comprobante de control'):
        assert expected in text
    with factory() as db:
        saved = db.get(PrintJob, uuid.UUID(queued.json()['job']['id']))
        assert saved.snapshot['items'][0]['remaining_quantity'] == 3
        assert saved.snapshot['commerce_status'] == 'conditional'
        assert db.query(PdvSale).count() == 0
    assert balances(factory, iid) == (8, 4, 4, 0, 0)
