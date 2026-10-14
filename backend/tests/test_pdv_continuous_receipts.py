import io
import uuid

import pytest
from pypdf import PdfReader
from app.models.printing import PrintJob
from app.services import pdv_receipts as receipts
from test_pdv_receipts import tickets, configure, sale
from test_pdv_unknown_stock import pdv_app


def test_roll_claim_requires_capability_and_has_one_measured_page(tickets):
    factory, client, customer = tickets
    device = configure(client, paper_width_mm=80, paper_height_mm=0)
    sold = sale(client, customer)
    headers = {'Authorization': 'Bearer '+device['token']}
    rejected = client.post('/api/printing/agent/claim', headers=headers)
    assert rejected.status_code == 409 and 'Atualize' in rejected.text
    with factory() as db:
        job = db.query(PrintJob).one()
        assert job.status == 'pending' and job.pdf == b''
    claimed = client.post('/api/printing/agent/claim?continuous_tickets=true', headers=headers).json()
    assert claimed['paper_mode'] == 'continuous'
    pdf = client.get('/api/printing/agent/jobs/'+claimed['id']+'/pdf', headers=headers).content
    pages = PdfReader(io.BytesIO(pdf)).pages
    assert len(pages) == 1
    assert float(pages[0].mediabox.width)*25.4/72 == pytest.approx(80, abs=.01)
    assert float(pages[0].mediabox.height)*25.4/72 == pytest.approx(claimed['paper_height_mm'], abs=.01)
    text = pages[0].extract_text()
    assert text.index('ELEVEN') < text.index('TOTAL') < text.index('PAGO') < text.index('Gracias')
    assert 'Pág.' not in text
    assert client.post('/api/printing/agent/claim?continuous_tickets=true', headers=headers).status_code == 204
    # Read-only download uses the same roll format, without making a second job.
    assert len(PdfReader(io.BytesIO(client.get(f"/api/pdv/sales/{sold['id']}/receipt/pdf").content)).pages) == 1
    with factory() as db: assert db.query(PrintJob).count() == 1


def test_old_receipt_reflows_without_changing_job_or_sale(tickets):
    factory, client, customer = tickets
    device = configure(client)
    sold = sale(client, customer)
    with factory() as db:
        job = db.query(PrintJob).one()
        original = dict(job.snapshot)
        job.status = 'submitted'
        db.commit()
    updated = configure(client, paper_width_mm=80, paper_height_mm=0)
    assert updated['token'] is None and updated['device']['id'] == device['device']['id']
    url = f"/api/pdv/sales/{sold['id']}/receipt"
    page = PdfReader(io.BytesIO(client.get(url+'/pdf').content)).pages[0]
    assert float(page.mediabox.width)*25.4/72 == pytest.approx(80, abs=.01)
    response = client.post(url, params={'copy_key': str(uuid.uuid4()), 'confirm_copy': True})
    assert response.status_code == 200
    with factory() as db:
        jobs = db.query(PrintJob).order_by(PrintJob.created_at).all()
        assert jobs[0].snapshot == original and jobs[1].snapshot['height'] == 0


def test_height_tracks_content_and_rejects_oversize_instead_of_splitting(tickets):
    factory, client, customer = tickets
    configure(client, paper_width_mm=80, paper_height_mm=0)
    sale(client, customer)
    with factory() as db: snapshot = dict(db.query(PrintJob).one().snapshot)
    small = PdfReader(io.BytesIO(receipts.render(snapshot))).pages[0]
    snapshot['items'] *= 12
    large = PdfReader(io.BytesIO(receipts.render(snapshot)))
    assert len(large.pages) == 1
    assert large.pages[0].mediabox.height > small.mediabox.height
    assert large.pages[0].extract_text().count('Produto sintético') == 12
    snapshot['items'] *= 20
    with pytest.raises(ValueError, match='991 mm'): receipts.render(snapshot)


@pytest.mark.parametrize('height', [-1, 1, 49, 401])
def test_invalid_media_is_rejected(tickets, height):
    _, client, _ = tickets
    assert client.put('/api/printing/receipt-device', json={'name':'Zebra', 'paper_height_mm':height}).status_code == 422
