"""Ticket delivery is isolated from A4, sale access and physical printing."""
import io
import uuid
import hashlib
from decimal import Decimal
from zipfile import ZipFile

import pytest
from pypdf import PdfReader
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base, get_db
from app.api.endpoints import printing
from app.dependencies import get_current_active_user
from app.models.printing import PrintDevice, PrintJob
from app.models.assistant import AssistantMessage
from app.models.pdv import PdvSale
from app.models.usuario import Usuario, UsuarioRole
from app.services import pdv_receipts as receipts
from test_pdv_unknown_stock import pdv_app, sale_payload, make_item


@compiles(JSONB, 'sqlite')
def sqlite_jsonb(element, compiler, **kwargs):
    return 'JSON'


@pytest.fixture
def tickets(pdv_app):
    factory, client, customer = pdv_app
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[PrintDevice.__table__, PrintJob.__table__, AssistantMessage.__table__])
    client.app.include_router(printing.router, prefix='/api/printing')
    return factory, client, customer


def configure(client, **kwargs):
    result = client.put('/api/printing/receipt-device', json={
        'name':'Zebra teste', 'paper_width_mm':60, 'paper_height_mm':80, 'auto_receipts':True, **kwargs})
    assert result.status_code == 200, result.text
    return result.json()


def sale(client, customer, **changes):
    payload = sale_payload([None], customer, avulso=True)
    payload.update(print_receipt=True, **changes)
    response = client.post('/api/pdv/sales', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_checkout_is_durable_and_original_is_idempotent(tickets):
    factory, client, customer = tickets
    device = configure(client)
    sold = sale(client, customer)
    url = f"/api/pdv/sales/{sold['id']}/receipt"
    first = client.get(url).json()['job']
    assert first['status'] == 'pending'
    assert client.post(url).json()['job']['id'] == first['id']
    assert client.post(url).json()['job']['id'] == first['id']
    with factory() as db:
        job = db.query(PrintJob).one()
        assert job.device_id == uuid.UUID(device['device']['id'])
        assert job.pdf == b''  # rendered only when the authorized agent collects it
        assert job.snapshot['items'][0]['name'] == 'Produto sintético'
        assert db.query(PdvSale).count() == 1
    headers = {'Authorization':'Bearer '+device['token']}
    assert client.post('/api/printing/agent/connect', headers=headers, json={'name':'Zebra'}).status_code == 409
    assert client.post('/api/printing/agent/connect', headers=headers, json={'name':'Zebra','profile':'tickets'}).status_code == 200
    claim = client.post('/api/printing/agent/claim', headers=headers)
    assert claim.status_code == 200, claim.text
    assert claim.json()['profile'] == 'tickets' and claim.json()['paper_width_mm'] == 60
    pdf = client.get('/api/printing/agent/jobs/'+first['id']+'/pdf', headers=headers).content
    assert hashlib.sha256(pdf).hexdigest() == claim.json()['sha256']
    assert client.post('/api/printing/agent/claim', headers=headers).status_code == 204
    assert client.post('/api/printing/agent/jobs/'+first['id']+'/result', headers=headers, json={'status':'submitted'}).status_code == 200
    assert client.get(url).json()['job']['status'] == 'submitted'


def test_copy_requires_explicit_confirmation_and_replays_same_key(tickets):
    factory, client, customer = tickets
    configure(client)
    sold = sale(client, customer)
    url=f"/api/pdv/sales/{sold['id']}/receipt"
    key=str(uuid.uuid4())
    assert client.post(url, params={'copy_key':key}).status_code == 422
    assert client.post(url, params={'copy_key':key,'confirm_copy':True}).status_code == 409
    with factory() as db:
        db.query(PrintJob).one().status='uncertain'; db.commit()
    params={'copy_key':key,'confirm_copy':True}
    copy = client.post(url, params=params).json()['job']
    assert client.post(url, params=params).json()['job']['id'] == copy['id']
    assert client.get(url).json()['job']['id'] == copy['id']
    assert client.post(url, params={'copy_key':str(uuid.uuid4()),'confirm_copy':True}).status_code == 409
    with factory() as db:
        assert db.query(PrintJob).count() == 2


def test_no_configuration_or_disabled_does_not_block_sales(tickets):
    factory, client, customer=tickets
    sale(client, customer)
    configure(client, auto_receipts=False)
    sale(client, customer)
    with factory() as db:
        assert db.query(PdvSale).count() == 2
        assert db.query(PrintJob).count() == 0


def test_profile_and_paper_changes_preserve_a4(tickets):
    factory, client, customer=tickets
    a4=client.post('/api/printing/devices',json={'name':'Samsung A4'}).json()
    device=configure(client)
    sold=sale(client,customer)
    # Generic PDF endpoint cannot route A4 documents to the receipt printer.
    response=client.post('/api/printing/jobs',data={'device_id':device['device']['id'],'request_key':str(uuid.uuid4())},files={'file':('x.pdf',b'%PDF-1.4')})
    assert response.status_code == 404
    headers={'Authorization':'Bearer '+a4['token']}
    assert client.post('/api/printing/agent/claim',headers=headers).status_code == 204
    response=client.put('/api/printing/receipt-device',json={'name':'Zebra','paper_width_mm':80,'paper_height_mm':200,'auto_receipts':True})
    assert response.status_code == 409
    again=configure(client)
    assert again['token'] is None and again['device']['id'] == device['device']['id']
    with factory() as db:
        assert db.get(PrintDevice,uuid.UUID(a4['id'])).purpose=='documents'


def test_personal_sale_permissions_and_owner_configuration(tickets):
    factory, client, customer=tickets
    configure(client)
    sold=sale(client,customer)
    with factory() as db:
        employee=Usuario(nome='Denis sintético',email='denis@eleven.com',role=UsuarioRole.VENDEDOR,sales_scope='own',senha_hash='unused')
        db.add(employee);db.commit();employee_id=employee.id
    def current_employee():
        with factory() as db:return db.get(Usuario,employee_id)
    client.app.dependency_overrides[get_current_active_user]=current_employee
    url=f"/api/pdv/sales/{sold['id']}/receipt"
    assert client.get(url).status_code == 404
    assert client.post(url).status_code == 404
    assert client.get(url+'/preview').status_code == 404
    assert client.get(url+'/pdf').status_code == 404
    assert client.get('/api/pdv/management',params={'q':sold['id'].replace('-','')[:10]}).json()['total']==0
    assert client.put('/api/printing/receipt-device',json={'name':'Zebra'}).status_code == 403


def test_failed_checkout_never_enqueues(tickets):
    factory,client,customer=tickets
    configure(client)
    with factory() as db:
        item=make_item(db, stock_loja=None);item_id=item.id;db.commit()
    payload=sale_payload([item_id],customer);payload['print_receipt']=True
    assert client.post('/api/pdv/sales',json=payload).status_code == 409
    with factory() as db:
        assert db.query(PrintJob).count()==0 and db.query(PdvSale).count()==0


def test_receipt_pdf_paginated_and_escaped(tickets):
    factory,client,customer=tickets
    configure(client)
    sold=sale(client,customer)
    with factory() as db:snapshot=db.query(PrintJob).one().snapshot
    item=dict(snapshot['items'][0],name='Tênis <Givenchy> & modelo muito comprido DN0281 '+('A'*120),size='11 US',color='Branco')
    snapshot['items']=[item]*18
    pdf=receipts.render(snapshot)
    pages=PdfReader(io.BytesIO(pdf)).pages
    assert len(pages)>1
    text='\n'.join(p.extract_text() for p in pages)
    assert 'Givenchy' in text and 'TOTAL' in text and 'A cuenta (fiado)' in text
    assert text.count('DN0281')==18
    for page in pages:
        assert float(page.mediabox.width)==pytest.approx(60*72/25.4,abs=.01)
        assert float(page.mediabox.height)==pytest.approx(80*72/25.4,abs=.01)


def test_ticket_installer_is_distinct_and_has_no_credential(tickets):
    _,client,_=tickets
    response=client.get('/api/printing/agent-package?profile=tickets')
    assert response.status_code==200
    with ZipFile(io.BytesIO(response.content)) as package:
        assert b'-Profile tickets' in package.read('Eleven-Impressao/Instalar.cmd')
        installer = package.read('Eleven-Impressao/Instalar.ps1')
        assert b'ElevenPrintTickets' in installer
        assert b"$AgentProfile = 'tickets'" in installer
        assert b"$AgentProfile = 'documents'" not in installer
        assert b'-NoExit' in installer
        assert 'Eleven-Impressao/TicketContinuo.ps1' in package.namelist()
        assert not any(name.endswith(('config.json','.env')) for name in package.namelist())


def test_credential_rotation_preserves_queue_and_requires_confirmation(tickets):
    factory,client,customer=tickets
    device=configure(client)
    sold=sale(client,customer)
    old={'Authorization':'Bearer '+device['token']}
    assert client.post('/api/printing/receipt-device/credential').status_code==422
    response=client.post('/api/printing/receipt-device/credential?confirm=true')
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert client.post('/api/printing/agent/connect',headers=old,json={'name':'Zebra','profile':'tickets'}).status_code==401
    fresh={'Authorization':'Bearer '+response.json()['token']}
    assert client.post('/api/printing/agent/connect',headers=fresh,json={'name':'Zebra','profile':'tickets'}).status_code==200
    with factory() as db:
        assert db.query(PrintDevice).count()==1 and db.query(PrintJob).count()==1
        db.query(PrintJob).one().status='claimed';db.commit()
    assert client.post('/api/printing/receipt-device/credential?confirm=true').status_code==409


def test_generation_failure_does_not_claim_or_block_later_jobs(tickets, monkeypatch):
    factory,client,customer=tickets
    device=configure(client)
    sale(client,customer)
    headers={'Authorization':'Bearer '+device['token']}
    def fail(_):raise ValueError('Synthetic invalid snapshot')
    monkeypatch.setattr(receipts,'render',fail)
    assert client.post('/api/printing/agent/claim',headers=headers).status_code==204
    with factory() as db:
        job=db.query(PrintJob).one()
        assert job.status=='failed' and job.claimed_at is None
        assert job.diagnostic=={'code':'document_generation_failed'}


def test_download_and_preview_are_read_only_and_work_without_a_printer(tickets):
    factory,client,customer=tickets
    sold=sale(client,customer)
    url=f"/api/pdv/sales/{sold['id']}/receipt"
    preview=client.get(url+'/preview')
    assert preview.status_code==200 and preview.headers['cache-control']=='no-store'
    data=preview.json()
    assert data['code']==sold['id'].replace('-','')[:10].upper()
    assert data['location']=='Shopping Paris - PY' and data['email']=='contato@elevenparispy.com'
    assert data['payments'][0]['label']=='A cuenta (fiado)'
    assert data['barcode'].startswith('data:image/svg+xml;base64,')
    pdf=client.get(url+'/pdf')
    assert pdf.status_code==200 and pdf.headers['content-type']=='application/pdf'
    text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    for value in ('ELEVEN','Shopping Paris - PY','contato@elevenparispy.com',data['code'],'Gracias por su compra','Vendedor:','Cliente:'):
        assert value in text
    with factory() as db:
        assert db.query(PrintJob).count()==0 and db.query(PdvSale).count()==1


def test_printed_revision_remains_downloadable_after_temporary_pdf_removed(tickets):
    factory,client,customer=tickets
    configure(client);sold=sale(client,customer)
    url=f"/api/pdv/sales/{sold['id']}/receipt"
    with factory() as db:
        job=db.query(PrintJob).one();job.pdf=b'';job.status='submitted'
        db.get(PdvSale,uuid.UUID(sold['id'])).cliente_nome='Name changed outside receipt snapshot'
        db.commit()
    assert client.get(url+'/preview').json()['customer']!='Name changed outside receipt snapshot'
    assert client.get(url+'/pdf').status_code==200
    with factory() as db:assert db.query(PrintJob).count()==1


def test_refunded_receipt_marks_status_and_preserves_original_values(tickets):
    factory,client,customer=tickets
    configure(client);sold=sale(client,customer)
    with factory() as db:
        row=db.get(PdvSale,uuid.UUID(sold['id']));row.status='refunded';row.refunded_gs=row.total_gs;row.version+=1
        row.items[0].returned_quantity=row.items[0].quantity;db.commit()
    url=f"/api/pdv/sales/{sold['id']}/receipt"
    preview=client.get(url+'/preview').json()
    assert preview['status']=='Venta devuelta' and preview['status_changed']
    assert preview['refunded'] and preview['items'][0]['returned']
    assert client.post(url).status_code==200
    with factory() as db:
        latest=db.query(PrintJob).filter_by(request_key=receipts.original_key(db.get(PdvSale,uuid.UUID(sold['id'])))).one()
        assert latest.snapshot['status']=='refunded'
        assert db.query(PdvSale).count()==1


def test_ticket_lookup_includes_collisions_for_review_and_accepts_full_id(tickets):
    factory,client,customer=tickets
    sold=sale(client,customer)
    code=sold['id'].replace('-','')[:10].upper()
    with factory() as db:
        original=db.get(PdvSale,uuid.UUID(sold['id']))
        # The legacy UUID column has numeric affinity in SQLite. Keep the
        # synthetic collision textual even when the random prefix is all digits.
        collision=PdvSale(id=uuid.UUID(code+'a'*22),vendedor_id=original.vendedor_id,status='completed',cliente_nome='Coincidencia sintética')
        db.add(collision);db.commit();collision_id=str(collision.id)
    for query in (code,code.lower(),'#'+code):
        result=client.get('/api/pdv/management',params={'q':query}).json()
        assert {row['id'] for row in result['items']}=={sold['id'],collision_id}
    assert client.get('/api/pdv/management',params={'q':sold['id']}).json()['total']==1
