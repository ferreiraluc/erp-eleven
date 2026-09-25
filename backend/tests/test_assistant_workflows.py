"""Cases from actual conversations, entirely isolated from providers and production."""
import hashlib
import io
import json
import uuid
from datetime import date,timedelta
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas
from test_assistant import setup,incoming,telegram_update
from test_address_manager import env
from test_assistant_queries import shipment,tool_call
from app.database import Base,get_db
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.assistant import AssistantMessage,AssistantAction,AssistantIdentity,utcnow
from app.models.address_book import FreightOrder
from app.models.inventory import Item,StockMovement
from app.models.printing import PrintJob,PrintDevice
from app.services import assistant_agent as agent,assistant_channels as channels,assistant_documents as documents
from app.services.assistant_tracking import CustomerTrackingArgs,customer_tracking,customer_tracking_reply
from app.services.assistant_schedule import confirm_action
from app.services.assistant_inventory import ItemsArgs,EntryArgs,prepare_inventory


def pdf_bytes():
    data=io.BytesIO();c=Canvas(data);c.drawString(60,700,'Documento de teste');c.showPage();c.save();return data.getvalue()


def identity(db,msg):
    return channels.authorized_identity(db,msg.channel,msg.sender_id)


def test_taigoro_current_code_ignores_old_delivered_name_variations(setup,monkeypatch):
    factory,_,uid=setup
    # Also protect old tool calls if the model chooses the generic query.
    monkeypatch.setattr(agent,'complete',lambda *a,**k:tool_call('buscar_rastreios',{'termo':'Taigoro','ordem':'recentes'}))
    with factory() as db:
        shipment(db,'CURRENT',name='Taigoro Muller Hames')
        shipment(db,'OLD1',name='Taigoro Muller',status='ENTREGUE')
        shipment(db,'OLD2',name='Taigoro Hames',status='ENTREGUE')
        msg=incoming(db,uid,'Manda o rastreio do taigoro')
        result=agent.respond(db,msg,identity(db,msg))
        assert result.parts[0]=='CURRENT' and len(result.parts)==2
        assert 'Em trânsito' in result.parts[1] and 'OLD' not in result and '?' not in result


def test_customer_multiple_active_codes_each_copyable_and_delivered_is_opt_in(setup):
    factory,_,_=setup
    with factory() as db:
        shipment(db,'CURRENT1',name='Maria Silva');shipment(db,'CURRENT2',name='Maria Silva')
        shipment(db,'OLD',name='Maria Silva',status='ENTREGUE')
        result=customer_tracking(db,CustomerTrackingArgs(termo='Maria'))
        answer=customer_tracking_reply(result)
        assert set(answer.parts[::2])=={'CURRENT1','CURRENT2'} and len(answer.parts)==4
        shipment(db,'OTHER',name='Maria Souza')
        ambiguous=customer_tracking_reply(customer_tracking(db,CustomerTrackingArgs(termo='Maria')))
        assert 'Qual deles' in ambiguous and not hasattr(ambiguous,'parts')
        only_old=customer_tracking_reply(customer_tracking(db,CustomerTrackingArgs(termo='OLD')))
        assert 'Não encontrei envio em andamento' in only_old and 'OLD' not in only_old


def test_pdf_consultation_is_not_overwritten_by_tracking_reply(env,monkeypatch):
    factory,_,uid,_=env
    steps=iter([tool_call('buscar_rastreios',{'termo':'Peter','ordem':'priorizar_abertos'}),
        {'content':'A etiqueta de código OY859210230BR está aguardando o PDF. A impressão está sendo acompanhada.'}])
    monkeypatch.setattr(agent,'complete',lambda *a,**k:next(steps))
    with factory() as db:
        shipment(db,'OY859210230BR',name='Peter')
        msg=incoming(db,uid,'Consulte o PDF da etiqueta para imprimir',channel='telegram')
        answer=agent.respond(db,msg,identity(db,msg))
        assert len(answer.parts)==1 and 'aguardando o PDF' in answer


def test_group_context_does_not_mix_employees(env,monkeypatch):
    factory,_,uid,_=env
    captured=[]
    monkeypatch.setattr(agent,'complete',lambda messages,**k:captured.extend(messages) or {'content':'Resposta simples.'})
    with factory() as db:
        other=Usuario(nome='Outro',email='other@test.test',senha_hash='x',role=UsuarioRole.VENDEDOR)
        db.add(other);db.flush()
        a=incoming(db,other.id,'SEGREDO_DO_PEDIDO_DE_OUTRO_AUTOR',channel='telegram');a.status='done';a.response='Resposta de outro'
        b=incoming(db,uid,'CONTEXTO_DO_PROPRIO_AUTOR',channel='telegram');b.status='done';b.response='Sua resposta'
        db.flush()
        msg=incoming(db,uid,'Continua',channel='telegram')
        agent.respond(db,msg,identity(db,msg))
        data=json.dumps(captured)
        assert 'CONTEXTO_DO_PROPRIO_AUTOR' in data and 'SEGREDO_DO_PEDIDO_DE_OUTRO_AUTOR' not in data


def test_fabricated_quote_cannot_reuse_previous_customer(env,monkeypatch):
    factory,_,uid,_=env
    answers=iter([{'content':'Cotação para Taigoro: PAC R$ 25,65; SEDEX R$ 46,49.'},
        {'content':'Informe o peso e as medidas do pacote.'}])
    monkeypatch.setattr(agent,'complete',lambda *a,**k:next(answers))
    with factory() as db:
        msg=incoming(db,uid,'Emita uma etiqueta para Taigoro',channel='telegram')
        answer=agent.respond(db,msg,identity(db,msg))
        assert 'Informe o peso' in answer and db.query(FreightOrder).count()==0


def test_service_number_does_not_select_older_quote_after_another_request(env):
    from app.services.assistant_freight import service_choice,quote_preview
    factory,_,uid,_=env
    with factory() as db:
        old=incoming(db,uid,'Cote para Renata',channel='telegram')
        q=FreightOrder(request_key=old.id,user_id=uid,environment='sandbox',state='quoted',rates=[{'id':2,'price':20,'name':'SEDEX'}],payload={'to':{'name':'Renata'},'from':{'name':'Mona'}})
        db.add(q);db.flush();old.status='done';old.response=quote_preview(q)
        other=incoming(db,uid,'Agora Taigoro',channel='telegram');other.status='done';other.response='Falta o peso.';db.flush()
        msg=incoming(db,uid,'2',channel='telegram')
        assert service_choice(db,msg,identity(db,msg),'2') is None
        assert db.query(AssistantAction).count()==0


def test_attachment_metadata_is_temporary_and_filename_is_not_retained(env):
    update=telegram_update('Imprima esse arquivo')
    update['message']['document']={'file_id':'telegram-file','file_size':100,'file_name':'documento-contador-confidencial.pdf','mime_type':'application/pdf'}
    data=channels.telegram_message(update)
    assert data.attachment['file_id']=='telegram-file'
    assert 'confidencial' not in json.dumps(data.attachment)
    copied=telegram_update('Imprima',sender='123');copied['message']['reply_to_message']=update['message']
    assert channels.telegram_message(copied).attachment
    copied['message']['reply_to_message']['from']['id']=321
    assert channels.telegram_message(copied).attachment is None


def test_pdf_bridge_never_stores_bytes_and_clears_reference_after_agent_result(env,monkeypatch):
    from app.api.endpoints import printing
    factory,client,uid,did=env
    pdf=pdf_bytes();monkeypatch.setattr(documents,'download_pdf',lambda a:pdf)
    with factory() as db:
        source=incoming(db,uid,'[Arquivo recebido: anexo para impressão]',channel='telegram')
        source.attachment={'file_id':'tg-file','mime_type':'application/pdf','name':'PDF recebido','size':len(pdf)};db.flush()
        msg=incoming(db,uid,'Imprima o documento do contador',channel='telegram')
        result=documents.prepare_file(db,msg,identity(db,msg),documents.FilePrintArgs())
        assert 'confirmacao' in result and db.query(PrintJob).count()==0
        action=db.query(AssistantAction).one()
        assert 'arquivo_imprimir'==action.kind and 'tg-file' not in json.dumps(action.payload)
        confirm=incoming(db,uid,'confirmo',channel='telegram')
        assert 'PDF encaminhado' in confirm_action(db,confirm,identity(db,confirm),action)
        job=db.query(PrintJob).one();jid=job.id
        assert job.pdf==b'' and source.attachment is None
        assert job.snapshot['telegram_file']['file_id']=='tg-file'
        assert 'Nenhuma alteração' in confirm_action(db,confirm,identity(db,confirm),action)
        db.commit()
    assert client.get('/manager/history').json()['total']==0
    assert client.get(f'/manager/history/{jid}/pdf').status_code==410
    with factory() as db:
        device=db.get(PrintDevice,uuid.UUID(did))
        claim=printing.claim(device,db)
        assert claim['id']==str(jid)
        response=printing.document(jid,device,db)
        assert response.body==pdf
        assert db.get(PrintJob,jid).pdf==b''
        printing.result(jid,printing.ResultInput(status='submitted'),device,db)
        assert db.get(PrintJob,jid).snapshot is None


def test_pdf_wrong_author_expiry_cancel_and_invalid_file(env,monkeypatch):
    factory,_,uid,_=env
    real_download=documents.download_pdf
    monkeypatch.setattr(documents,'download_pdf',lambda a:pdf_bytes())
    with factory() as db:
        source=incoming(db,uid,'arquivo',channel='telegram');source.attachment={'file_id':'test','mime_type':'application/pdf','name':'PDF recebido'};db.flush()
        msg=incoming(db,uid,'imprima',channel='whatsapp')
        assert 'erro' in documents.prepare_file(db,msg,identity(db,msg),documents.FilePrintArgs(mensagem_id=source.id))
        msg=incoming(db,uid,'imprima',channel='telegram')
        assert 'confirmacao' in documents.prepare_file(db,msg,identity(db,msg),documents.FilePrintArgs())
        action=db.query(AssistantAction).one()
        assert 'cancelada' in confirm_action(db,msg,identity(db,msg),action,cancel=True)
        assert source.attachment is None and db.query(PrintJob).count()==0
        source.attachment={'file_id':'expired'};source.created_at=utcnow()-timedelta(hours=25);db.flush()
        documents.cleanup_documents(db);db.expire_all();assert db.get(AssistantMessage,source.id).attachment is None
    with pytest.raises(ValueError):documents.validate_pdf(b'%PDF-fake')
    with pytest.raises(ValueError):real_download({'size':6*1024*1024})


def test_pdf_caption_or_followup_prepares_without_sending_contents_to_ai(env,monkeypatch):
    factory,_,uid,_=env
    monkeypatch.setattr(documents,'download_pdf',lambda a:pdf_bytes())
    def no_ai(*args,**kwargs):raise AssertionError('Document printing must not send file contents to AI')
    monkeypatch.setattr(agent,'complete',no_ai)
    with factory() as db:
        source=incoming(db,uid,'[Arquivo recebido: anexo para impressão]',channel='telegram')
        source.attachment={'file_id':'test','mime_type':'application/pdf','name':'PDF recebido'}
        source.status='done';source.response='Arquivo recebido.';db.flush()
        msg=incoming(db,uid,'Consegue imprimir?',channel='telegram')
        answer=agent.respond(db,msg,identity(db,msg))
        assert 'Imprimir PDF' in answer and answer.reply_markup
        assert db.query(PrintJob).count()==0


def test_telegram_download_is_memory_only_bounded_and_hash_checked(env,monkeypatch):
    data=pdf_bytes();calls=[]
    class Response:
        status_code=200
        def json(self):return {'result':{'file_path':'documents/file_123.pdf','file_size':len(data)}}
        def iter_content(self,*args):yield data
        def __enter__(self):return self
        def __exit__(self,*args):pass
    def post(url,**kwargs):calls.append(('post',url,kwargs));return Response()
    def get(url,**kwargs):calls.append(('get',url,kwargs));return Response()
    monkeypatch.setattr(documents.requests,'post',post);monkeypatch.setattr(documents.requests,'get',get)
    result=documents.download_pdf({'file_id':'test','mime_type':'application/pdf'})
    assert result==data and calls[0][1].endswith('/getFile') and calls[1][1].endswith('/documents/file_123.pdf')
    assert calls[1][2]['stream'] and not calls[1][2]['allow_redirects']
    job=PrintJob(snapshot={'telegram_file':{'file_id':'test','mime_type':'application/pdf'}},sha256='wrong',expires_at=utcnow()+timedelta(hours=1))
    with pytest.raises(ValueError,match='diferente'):documents.ephemeral_pdf(job)
    job.sha256=hashlib.sha256(data).hexdigest();assert documents.ephemeral_pdf(job)==data


def test_inventory_creation_entry_confirmation_and_duplicates(env):
    factory,_,uid,_=env
    with factory() as db:
        Base.metadata.create_all(db.get_bind(),tables=[StockMovement.__table__])
        args=ItemsArgs(itens=[{'nome':'Camiseta Teste','tamanho':'M','cor':'azul','preco_venda':'25.50','moeda_venda':'USD','quantidade':3,'local':'deposito'}])
        msg=incoming(db,uid,'Cadastre camiseta M azul 3 no depósito',channel='telegram')
        assert 'confirmacao' in prepare_inventory(db,msg,identity(db,msg),'preparar_itens',args)
        assert db.query(Item).count()==0
        action=db.query(AssistantAction).one();confirm=incoming(db,uid,'confirmo',channel='telegram')
        assert 'cadastrados' in confirm_action(db,confirm,identity(db,confirm),action)
        item=db.query(Item).one();assert item.stock_deposito==3 and item.current_stock==3 and item.sale_price==Decimal('25.50')
        assert db.query(StockMovement).count()==1
        confirm_action(db,confirm,identity(db,confirm),action)
        assert db.query(Item).count()==1 and db.query(StockMovement).count()==1
        duplicate=incoming(db,uid,'Cadastre de novo',channel='telegram')
        assert 'candidatos' in prepare_inventory(db,duplicate,identity(db,duplicate),'preparar_itens',args)
        entry=incoming(db,uid,'Entraram 2 camisetas na loja',channel='telegram')
        result=prepare_inventory(db,entry,identity(db,entry),'preparar_entrada_estoque',EntryArgs(termo='Camiseta Teste',quantidade=2,local='loja'))
        assert 'confirmacao' in result
        action=db.query(AssistantAction).filter_by(source_message_id=entry.id).one()
        assert 'Entrada registrada' in confirm_action(db,entry,identity(db,entry),action)
        assert item.current_stock==5 and item.stock_loja==2 and db.query(StockMovement).count()==2


def test_inventory_permissions_and_required_money_units(env):
    factory,_,uid,_=env
    with factory() as db:
        db.get(Usuario,uid).role=UsuarioRole.VENDEDOR
        msg=incoming(db,uid,'cadastre produto',channel='telegram')
        args=ItemsArgs(itens=[{'nome':'Produto teste'}])
        assert 'erro' in prepare_inventory(db,msg,identity(db,msg),'preparar_itens',args)
        assert db.query(AssistantAction).count()==0
    with pytest.raises(ValueError):ItemsArgs(itens=[{'nome':'Produto','preco_venda':25}])
    with pytest.raises(ValueError):ItemsArgs(itens=[{'nome':'Produto','quantidade':3}])
