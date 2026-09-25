"""Ephemeral Telegram-to-printer bridge: never persist PDF bytes or document contents."""
import hashlib
import io
import re
import uuid
from datetime import timedelta
import requests
from pydantic import BaseModel, ConfigDict
from sqlalchemy import String,cast
from ..config import settings
from ..models.assistant import AssistantMessage,AssistantAction,utcnow
from ..models.printing import PrintDevice,PrintJob
from .assistant_schedule import may_schedule
from .assistant_controls import preview_reply
from .assistant_queries import QueryArgs,literal_pattern

MAX_BYTES=5*1024*1024


class FilePrintArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mensagem_id: uuid.UUID | None = None


def download_pdf(attachment):
    if attachment.get('size',0) and attachment['size']>MAX_BYTES:raise ValueError('Envie um PDF de até 5 MB.')
    if attachment.get('mime_type')!='application/pdf' and not attachment.get('name','').lower().endswith('.pdf'):
        raise ValueError('Para imprimir esse arquivo, envie-o em PDF. Endereços em texto continuam disponíveis.')
    try:
        response=requests.post(f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getFile',
            json={'file_id':attachment['file_id']},timeout=(5,20),allow_redirects=False)
        if response.status_code!=200:raise ValueError('Não consegui obter o arquivo do Telegram. Reenvie o PDF.')
        result=response.json().get('result',{})
        path=result.get('file_path','')
        if not isinstance(path,str) or not re.fullmatch(r'[A-Za-z0-9_./-]+',path) or path.startswith('/') or '..' in path.split('/'):
            raise ValueError('O Telegram não retornou um arquivo válido. Reenvie o PDF.')
        if result.get('file_size',0)>MAX_BYTES:raise ValueError('Envie um PDF de até 5 MB.')
        with requests.get(f'https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{path}',
                          stream=True,timeout=(5,25),allow_redirects=False) as stream:
            if stream.status_code!=200:raise ValueError('Não consegui baixar o PDF. Reenvie o arquivo.')
            data=bytearray()
            for chunk in stream.iter_content(65536):
                data.extend(chunk)
                if len(data)>MAX_BYTES:raise ValueError('Envie um PDF de até 5 MB.')
        return bytes(data)
    except requests.RequestException:
        raise ValueError('O download do Telegram falhou. Tente novamente ou reenvie o PDF.') from None


def validate_pdf(data):
    if not data.startswith(b'%PDF-') or len(data)>MAX_BYTES:raise ValueError('O arquivo precisa ser um PDF válido de até 5 MB.')
    from pypdf import PdfReader
    try:
        reader=PdfReader(io.BytesIO(data),strict=True)
        if reader.is_encrypted:raise ValueError('Remova a senha do PDF antes de enviar para impressão.')
        pages=len(reader.pages)
        if not 1<=pages<=30:raise ValueError('Envie um PDF com 1 a 30 páginas.')
        root=reader.trailer['/Root']
        names=root.get('/Names',{})
        if hasattr(names,'get_object'):names=names.get_object()
        action=root.get('/OpenAction')
        if hasattr(action,'get_object'):action=action.get_object()
        unsafe_action=isinstance(action,dict) and action.get('/S') in ('/JavaScript','/Launch','/SubmitForm','/ImportData','/URI')
        if unsafe_action or '/AA' in root or '/JavaScript' in names:
            raise ValueError('Exporte uma cópia simples do PDF, sem ações automáticas.')
        return pages
    except ValueError:raise
    except Exception:raise ValueError('Não consegui validar esse PDF. Exporte-o novamente e reenvie.') from None


def file_preview(action):
    p=action.payload
    return preview_reply(action,f"Imprimir PDF: {p['pages']} página(s), uma cópia na impressora da loja.\nO documento não será arquivado no ERP nem usado para cadastrar dados.\nConfirme para enviar à fila ou cancele.")


def prepare_file(db,message,identity,args):
    if not message.should_reply or not may_schedule(db,message,identity):return {'erro':'Impressão de arquivos exige gestor habilitado e pedido direto.'}
    previous=db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if previous:return {'confirmacao':file_preview(previous)} if previous.kind=='arquivo_imprimir' else {'erro':'Esta mensagem já possui outra prévia. Conclua-a antes de pedir uma nova.'}
    query=db.query(AssistantMessage).filter(AssistantMessage.user_id==message.user_id,AssistantMessage.channel=='telegram',
        AssistantMessage.channel==message.channel,AssistantMessage.conversation_id==message.conversation_id,
        AssistantMessage.created_at<=message.created_at,AssistantMessage.created_at>=utcnow()-timedelta(hours=24),AssistantMessage.attachment.isnot(None))
    source=query.filter(AssistantMessage.id==args.mensagem_id).first() if args.mensagem_id else (
        message if message.attachment else query.order_by(AssistantMessage.created_at.desc()).first())
    if not source or not source.attachment:return {'erro':'Envie o arquivo PDF nesta conversa do Telegram e peça para imprimir. Um nome de arquivo em texto não contém o PDF.'}
    devices=db.query(PrintDevice).filter_by(active=True).limit(2).all()
    if len(devices)!=1:return {'erro':'Configure uma única impressora ativa no ERP.'}
    try:
        pdf=download_pdf(source.attachment)
        pages=validate_pdf(pdf)
    except ValueError as exc:return {'erro':str(exc)}
    action=AssistantAction(source_message_id=message.id,user_id=message.user_id,kind='arquivo_imprimir',payload={
        'attachment_message_id':str(source.id),'pages':pages,
        'sha256':hashlib.sha256(pdf).hexdigest(),'device_id':str(devices[0].id)})
    db.add(action);db.flush()
    return {'confirmacao':file_preview(action)}


def confirm_file(db,message,action):
    p=action.payload
    source=db.get(AssistantMessage,uuid.UUID(p['attachment_message_id']))
    if not source or source.user_id!=message.user_id or source.channel!=message.channel or source.conversation_id!=message.conversation_id:
        return 'Arquivo não disponível para este usuário e conversa.'
    if not source.attachment:return 'A referência temporária do PDF expirou. Envie o arquivo novamente.'
    device=db.query(PrintDevice).filter_by(id=uuid.UUID(p['device_id']),active=True).with_for_update().first()
    if not device:return 'A impressora foi desativada. Nenhum arquivo enviado.'
    job=db.query(PrintJob).filter_by(request_key=action.id).first()
    if not job:
        # The existing Windows agent downloads this through its scoped endpoint.
        # Only a temporary Telegram reference is queued, never the PDF itself.
        job=PrintJob(device_id=device.id,user_id=message.user_id,request_key=action.id,pdf=b'',sha256=p['sha256'],
            snapshot={'telegram_file':source.attachment},source='bot_pdf_ephemeral',expires_at=utcnow()+timedelta(hours=24))
        db.add(job);db.flush()
    source.attachment=None
    action.status='executed';action.result_id=job.id;action.executed_at=utcnow()
    return f"PDF encaminhado à impressora: {p['pages']} página(s), uma cópia. O ERP não arquiva esse documento. O envio à fila ainda não confirma a saída do papel."


def ephemeral_pdf(job):
    expires=job.expires_at.replace(tzinfo=utcnow().tzinfo) if job.expires_at.tzinfo is None else job.expires_at
    if expires < utcnow():raise ValueError('Solicitação de impressão expirada.')
    attachment=(job.snapshot or {}).get('telegram_file')
    if not attachment:raise ValueError('Referência temporária do arquivo indisponível.')
    data=download_pdf(attachment)
    if hashlib.sha256(data).hexdigest()!=job.sha256:raise ValueError('Arquivo diferente do PDF aprovado. Reenvie e confirme uma nova prévia.')
    return data


def cleanup_documents(db):
    db.query(AssistantMessage).filter(AssistantMessage.attachment.isnot(None),
        AssistantMessage.created_at<utcnow()-timedelta(hours=24)).update({'attachment':None},synchronize_session=False)
    db.query(PrintJob).filter(PrintJob.source=='bot_pdf_ephemeral',PrintJob.expires_at<=utcnow(),
        PrintJob.status=='pending').update({'status':'expired','snapshot':None,'pdf':b''},synchronize_session=False)
    db.query(PrintJob).filter(PrintJob.source=='bot_pdf_ephemeral',PrintJob.expires_at<=utcnow(),
        PrintJob.snapshot.isnot(None)).update({'snapshot':None,'pdf':b''},synchronize_session=False)


def query_prints(db,message,identity,args):
    if not may_schedule(db,message,identity):return {'erro':'Histórico de impressões exige gestor habilitado.'}
    q=db.query(PrintJob).filter(PrintJob.source!='bot_pdf_ephemeral')
    if args.termo:q=q.filter(cast(PrintJob.snapshot,String).ilike(literal_pattern(args.termo),escape='\\'))
    total=q.count();rows=q.order_by(PrintJob.created_at.desc()).offset((args.pagina-1)*args.limite).limit(args.limite).all()
    return {'total':total,'resultados':[{'id':str(j.id),'status':j.status,'origem':j.source,'data':j.created_at.isoformat(),
        'arquivo':(j.snapshot or {}).get('filename'),'destinatario':(j.snapshot or {}).get('endereco',{}).get('nome')} for j in rows],
        'aviso':'submitted significa enviado pelo agente à impressora, não comprova saída física do papel. Nunca reimprima sem pedido explícito.'}
