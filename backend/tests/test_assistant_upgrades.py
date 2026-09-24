"""Callbacks, unambiguous people, and delayed PDF delivery remain durable and authorized."""
import hashlib
import hmac
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from test_assistant import setup, incoming, post_telegram
from test_address_manager import env, sf_order
from app.config import settings
from app.models.assistant import AssistantAction, AssistantDelivery, AssistantMessage, AssistantKnowledge, utcnow
from app.models.address_book import FreightOrder
from app.models.printing import PrintJob, PrintDevice
from app.models.vendedor import Vendedor
from app.models.folga import Folga
from app.models.usuario import Usuario, UsuarioRole
from app.services import assistant_channels as channels, assistant_agent as agent, freight_labels as labels, superfrete as sf
from app.services.assistant_schedule import prepare_schedule, ScheduleWriteArgs
from app.services.assistant_knowledge import employee_candidates, query_team, KnowledgeArgs, prepare_alias, AliasArgs, system_catalog
from app import assistant_worker as worker


def callback(data, update=123, sender=123, chat=-100123):
    return {'update_id':update,'callback_query':{'id':'callback-test','from':{'id':sender,'is_bot':False},
        'message':{'message_id':10,'chat':{'id':chat,'type':'group'},'from':{'id':999,'is_bot':True}},'data':data}}


def draft(db,uid,name='Junior',day=date(2026,9,25)):
    db.get(Usuario,uid).role=UsuarioRole.ADMIN
    if not db.query(Vendedor).filter_by(nome=name).first():db.add(Vendedor(nome=name));db.flush()
    message=incoming(db,uid,f'Cadastra folga para {name}',channel='telegram')
    identity=channels.authorized_identity(db,'telegram','123')
    prepare_schedule(db,message,identity,ScheduleWriteArgs(vendedor=name,data=day))
    action=db.query(AssistantAction).filter_by(source_message_id=message.id).one()
    message.status='done'
    return action,identity


def test_callback_inbox_exact_action_repeat_and_owner(setup,monkeypatch):
    factory,client,uid=setup
    monkeypatch.setattr(channels,'acknowledge_callback',lambda *a:None)
    with factory() as db:
        action,_=draft(db,uid);key=action.id;db.commit()
    payload=callback('a:'+key.hex)
    for _ in range(2):assert post_telegram(client,payload).status_code==200
    assert worker.process_inbox()
    assert not worker.process_inbox()
    with factory() as db:
        assert db.query(Folga).count()==1
        assert db.query(AssistantDelivery).count()==1
    assert post_telegram(client,callback('a:'+key.hex,update=124)).status_code==200
    assert worker.process_inbox()
    with factory() as db:assert db.query(Folga).count()==1
    assert channels.telegram_message(callback('a:'+key.hex,chat=-555)) is None
    assert channels.telegram_message(callback('arbitrary-code')) is None
    assert post_telegram(client,callback('a:'+key.hex,sender=666,update=125)).status_code==200
    with factory() as db:assert db.query(AssistantMessage).filter_by(external_id='125').count()==0


def test_multiple_previews_named_choice_ambiguity_and_expiry(setup):
    factory,_,uid=setup
    with factory() as db:
        first,identity=draft(db,uid,'Júnior')
        second,_=draft(db,uid,'Maria')
        selection=agent.respond(db,incoming(db,uid,'confirmo',channel='telegram'),identity)
        assert len(selection.reply_markup['inline_keyboard'])==2
        assert str(first.id) not in selection
        response=agent.respond(db,incoming(db,uid,'confirmar JÚNIOR',channel='telegram'),identity)
        assert 'Folga cadastrada' in response and first.status=='executed' and second.status=='draft'
        second.created_at=utcnow()-timedelta(hours=25);db.flush()
        expired=agent.respond(db,incoming(db,uid,'/acao a:'+second.id.hex,channel='telegram'),identity)
        assert 'expirada' in expired


def test_same_recipient_requires_selection_and_selected_preview_has_buttons(env):
    from app.services.assistant_printing import prepare_print,AddressArgs
    factory,_,uid,_=env
    with factory() as db:
        identity=channels.authorized_identity(db,'telegram','123')
        for name,city in [('Juan','Asunción'),('Juan','Encarnación'),('Pedro','Asunción')]:
            m=incoming(db,uid,'Imprime '+name,channel='telegram')
            prepare_print(db,m,identity,AddressArgs(pais='PY',nome=name,cidade=city))
        result=agent.respond(db,incoming(db,uid,'confirmar impressão "Juan"',channel='telegram'),identity)
        assert len(result.reply_markup['inline_keyboard'])==2 and db.query(PrintJob).count()==0
        key=result.reply_markup['inline_keyboard'][0][0]['callback_data'][2:]
        preview=agent.respond(db,incoming(db,uid,'/acao v:'+key,channel='telegram'),identity)
        assert 'Juan' in preview and preview.reply_markup['inline_keyboard'][0][0]['callback_data']=='a:'+key
        response=agent.respond(db,incoming(db,uid,'confirmar Impressao "Pedro"',channel='telegram'),identity)
        assert 'fila' in response and db.query(PrintJob).count()==1


def test_employee_names_aliases_and_catalog_are_persistent(setup):
    factory,_,uid=setup
    with factory() as db:
        action,identity=draft(db,uid,'Júnior')
        assert employee_candidates(db,'Junior Favretto')[0].nome=='Júnior'
        m=incoming(db,uid,'Lembre que Juninho é o Junior',channel='telegram')
        result=prepare_alias(db,m,identity,AliasArgs(vendedor='Junior',apelido='Juninho'))
        assert 'confirmacao' in result
        saved=db.query(AssistantAction).filter_by(source_message_id=m.id).one()
        result=agent.respond(db,incoming(db,uid,'/acao a:'+saved.id.hex,channel='telegram'),identity)
        assert 'Memória salva' in result
        db.commit()
    with factory() as db:
        assert query_team(db,KnowledgeArgs(termo='Juninho'))['vendedores'][0]['nome']=='Júnior'
        catalog=system_catalog(db,KnowledgeArgs())
        assert any(r['ferramenta']=='consultar_estoque' and r['pagina']=='/inventory' for r in catalog['capacidades'])
        assert db.query(AssistantKnowledge).filter_by(kind='capability').count()>10
        db.add(Vendedor(nome='Junior Silva'));db.flush()
        # An exact ERP registration wins, while partial homonyms do not.
        db.query(Vendedor).filter_by(nome='Júnior').update({'nome':'Junior Favretto'});db.flush()
        assert len(employee_candidates(db,'Junior'))==2


def paid_order(factory,uid):
    key=sf_order(factory,uid,'released')
    with factory() as db:
        row=db.get(FreightOrder,key);row.provider_id='provider-test';row.price=Decimal('20')
        m=incoming(db,uid,'Emitir etiqueta',channel='telegram')
        labels.watch_label(db,row,auto_print=True,message=m)
        row.label_check_at=utcnow();db.commit()
    return key


def test_delayed_pdf_retry_cached_frontend_and_exactly_one_print(env,monkeypatch):
    factory,client,uid,_=env
    monkeypatch.setattr(labels,'SessionLocal',factory)
    monkeypatch.setattr(sf,'sync_tracking',lambda db,row:None)
    key=paid_order(factory,uid)
    ready=False
    def provider(method,path,body=None):
        if path.startswith('order/info'):return {'id':'provider-test','status':'generated'}
        if path=='tag/print':
            if not ready:raise sf.HTTPException(502,'Em processamento')
            return {'url':'https://etiqueta.superfrete.com/_etiqueta/pdf/test'}
        raise AssertionError('Never charge in the label worker: '+path)
    monkeypatch.setattr(sf,'call',provider)
    monkeypatch.setattr(sf,'label_pdf',lambda url:b'%PDF-1.4\nexample')
    assert labels.process_label()
    with factory() as db:
        row=db.get(FreightOrder,key)
        assert row.state=='released' and row.label_status=='waiting' and row.label_check_at
        assert db.query(PrintJob).count()==db.query(AssistantDelivery).count()==0
        row.label_check_at=utcnow();db.commit()
    ready=True
    assert labels.process_label()
    with factory() as db:
        row=db.get(FreightOrder,key)
        assert row.label_status=='ready' and row.print_job_id
        delivery=db.query(AssistantDelivery).one()
        assert 'fila de impressão' in delivery.text and delivery.document_pdf.startswith(b'%PDF-')
        # Simulates a duplicate event/restarted worker after completion.
        row.label_check_at=utcnow();db.commit()
    assert labels.process_label()
    with factory() as db:assert db.query(PrintJob).count()==db.query(AssistantDelivery).count()==1
    assert client.get(f'/freight/orders/{key}/pdf').content.startswith(b'%PDF-')
    assert client.get('/freight/orders').json()['items'][0]['pdf_available']


def test_pdf_not_lost_when_printer_temporarily_inactive(env,monkeypatch):
    factory,_,uid,did=env
    monkeypatch.setattr(labels,'SessionLocal',factory)
    key=paid_order(factory,uid)
    with factory() as db:
        row=db.get(FreightOrder,key);row.label_pdf=b'%PDF-1.4\nexample';row.label_status='ready'
        db.get(PrintDevice,uuid.UUID(did)).active=False;db.commit()
    assert labels.process_label()
    with factory() as db:
        row=db.get(FreightOrder,key);assert not row.print_job_id and row.label_error
        assert db.query(AssistantDelivery).count()==1 and db.query(PrintJob).count()==0
        db.get(PrintDevice,uuid.UUID(did)).active=True;row.label_check_at=utcnow();db.commit()
    assert labels.process_label()
    with factory() as db:assert db.query(AssistantDelivery).count()==2 and db.query(PrintJob).count()==1


def test_webhook_signed_wakeup_does_not_trust_pdf_or_pay(env,monkeypatch):
    factory,client,uid,_=env
    key=paid_order(factory,uid)
    monkeypatch.setattr(settings,'SUPERFRETE_WEBHOOK_SECRET','fake-signing-secret')
    payload=json.dumps({'event':'order.generated','data':{'id':'provider-test','url':'https://evil.test/fake.pdf'}}).encode()
    signature=hmac.new(b'fake-signing-secret',payload,hashlib.sha256).hexdigest()
    assert client.post('/freight/webhooks/superfrete',content=payload).status_code==403
    for _ in range(2):
        assert client.post('/freight/webhooks/superfrete',content=payload,headers={'X-ME-Signature':signature}).status_code==200
    with factory() as db:
        row=db.get(FreightOrder,key)
        assert row.label_url is None and row.label_check_at
        assert db.query(PrintJob).count()==0


def test_telegram_sends_durable_keyboard_and_cached_document(env,monkeypatch):
    from types import SimpleNamespace
    seen=[]
    monkeypatch.setattr(channels.requests,'post',lambda url,**kwargs: seen.append((url,kwargs)) or SimpleNamespace(status_code=200,json=lambda:{'ok':True,'result':{'message_id':7}}))
    row=AssistantDelivery(channel='telegram',destination=settings.TELEGRAM_GROUP_ID,text='Confira',
        document_pdf=b'%PDF-test',reply_markup={'inline_keyboard':[[{'text':'Confirmar','callback_data':'a:'+'1'*32}]]})
    assert channels.send_delivery(row)=='7'
    assert seen[0][0].endswith('/sendDocument')
    assert seen[0][1]['files']['document'][1]==b'%PDF-test'
    assert json.loads(seen[0][1]['data']['reply_markup'])==row.reply_markup
