"""Confirmed address printing through the existing device queue."""
from .sender_addresses import sender_lines
import hashlib
import io
import re
import uuid
from datetime import timedelta
from typing import Literal
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.platypus.doctemplate import LayoutError

from ..models.assistant import AssistantAction, utcnow
from ..models.printing import PrintDevice, PrintJob
from .assistant_print_policy import may_print


def printable_cpf(value):
    if not value:
        return ''
    digits = re.sub(r'[^0-9]', '', value)
    if len(digits) == 11 and len(set(digits)) == 1:
        return ''  # Placeholders, including legacy all-zero drafts, never reach paper.
    if len(digits) != 11 or not re.fullmatch(r'[0-9. -]+', value):
        raise ValueError('CPF informado deve conter 11 dígitos; se ausente, deixe vazio.')
    return f'{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}'


def document_line(address, *, preview=False):
    """The persisted key stays cpf; Paraguay documents keep the supplied text."""
    kind = address.get('documento_tipo')
    if kind and kind != 'CPF':
        value = (address.get('cpf') or '').strip()
        label = kind + (' do destinatário' if preview else '')
    elif address['pais'] == 'BR':
        value = printable_cpf(address.get('cpf'))
        label = 'CPF do destinatário' if preview else 'CPF'
    else:
        value = (address.get('cpf') or '').strip()
        label = 'RUC/C.I do destinatário' if preview else 'RUC/C.I'
    return f'{label}: {value}' if value else ''


class AddressArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    pais: Literal['BR', 'PY']
    nome: str = Field(default='', max_length=120)
    endereco: str = Field(default='', max_length=250, description='Rua ou detalhes fornecidos. Opcional no PY: deixe vazio quando ausente, nunca invente.')
    numero: str = Field(default='', max_length=10)
    bairro: str = Field(default='', max_length=60)
    complemento: str = Field(default='', max_length=60)
    cidade: str = Field(default='', max_length=100)
    estado: str = Field(default='', max_length=60, description='UF obrigatória no Brasil; departamento opcional no Paraguai.')
    cep: str = Field(default='', max_length=15)
    cpf: str = Field(default='', max_length=20, description='Documento opcional do destinatário: CPF no BR; RUC/C.I no PY, preservando texto, letras, pontos e hífen sem validar como CPF brasileiro. Extraia somente do endereço informado. Ausente ou pedido sem documento: string vazia. Nunca preencha zeros nem use documento do remetente.')
    documento_tipo: Literal['CPF', 'CNPJ', 'RG', 'CI', 'RUC'] | None = None
    documento_emissor: str | None = Field(default=None, max_length=20)
    telefone: str = Field(default='', max_length=40)
    remetente: str | None = Field(default=None, max_length=100, description='ID, apelido cadastrado no ID ou nome do remetente ativo consultado no gestor. Uma referência ambígua exige escolha.')

    @field_validator('nome', 'endereco', 'cidade', 'estado', 'cep', 'cpf', 'telefone', mode='before')
    @classmethod
    def plain_text(cls, value):
        return ' '.join(value.split()) if isinstance(value, str) else value

    @model_validator(mode='after')
    def address_rules(self):
        if self.documento_tipo:
            from .customer_documents import DOCUMENT_COUNTRIES, normalize_document
            if DOCUMENT_COUNTRIES[self.documento_tipo] != self.pais:
                raise ValueError('O país não corresponde ao tipo de documento.')
            if self.cpf and not normalize_document({'tipo': self.documento_tipo, 'pais': self.pais,
                    'numero': self.cpf, 'emissor': self.documento_emissor}):
                raise ValueError('Confira o tipo e o número do documento do destinatário.')
        for value in self.model_dump().values():
            if isinstance(value, str) and any(ord(c) < 32 and c not in '\n\r' for c in value):
                raise ValueError('Caracteres de controle não permitidos.')
        if self.pais == 'BR':
            if len(self.nome) < 2 or len(self.endereco) < 5 or len(self.cidade) < 2:
                raise ValueError('Para Brasil, informe nome, endereço e cidade.')
            self.estado = self.estado.upper()
            if self.estado not in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split():
                raise ValueError('Informe uma UF válida para o Brasil.')
            digits = re.sub(r'\D', '', self.cep)
            if len(digits) != 8 or not re.fullmatch(r'[0-9 -]+', self.cep):
                raise ValueError('Informe o CEP com 8 dígitos.')
            self.cep = digits[:5] + '-' + digits[5:]
            if not self.documento_tipo or self.documento_tipo == 'CPF':
                self.cpf = printable_cpf(self.cpf)
            if not self.remetente:
                raise ValueError('Escolha um remetente ativo cadastrado no gestor.')
        else:
            self.remetente = None
        return self


class ReprintAddressArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    trabalho_id: uuid.UUID = Field(description='ID completo de um trabalho de endereço retornado pela consulta atual. Nunca invente.')


def prepare_address_reprint(db, message, identity, args):
    """Reuse a saved address, but require a new, explicit confirmation for a copy."""
    from .assistant_schedule import may_schedule, action_preview
    from .print_diagnostics import diagnostic_message
    if not message.should_reply or not may_print(db, message, identity):
        return {'erro': 'Reimpressão exige pedido direto de um usuário autorizado nesta conversa.'}
    previous = db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if previous:
        return {'confirmacao': action_preview(previous)}
    query = db.query(PrintJob).filter_by(id=args.trabalho_id, source='bot')
    if not may_schedule(db, message, identity):
        query = query.filter_by(user_id=message.user_id)
    original = query.first()
    data = (original.snapshot or {}).get('endereco') if original else None
    if not data:
        return {'erro': 'Esse trabalho não contém um endereço disponível para reimpressão. Consulte os endereços salvos. Para etiqueta de frete use preparar_impressao_etiqueta; para PDF externo solicite o arquivo novamente.'}
    if original.status in ('pending', 'claimed') or db.query(PrintJob.id).filter(
            PrintJob.parent_id == original.id, PrintJob.status.in_(('pending', 'claimed'))).first():
        return {'erro': 'O endereço ainda está na fila ou em processamento. Consulte a situação; nenhuma segunda cópia foi preparada.'}
    result = prepare_print(db, message, identity, AddressArgs.model_validate(data))
    if 'confirmacao' not in result:
        return result
    action = db.query(AssistantAction).filter_by(source_message_id=message.id).one()
    action.payload = {**action.payload, 'reprint_of': str(original.id),
                      'previous_print_status': original.status,
                      'previous_print_diagnostic': diagnostic_message(original)}
    return {'confirmacao': print_preview(action)}


def render_address(payload):
    """One fresh A4 sheet, only the requested recipient; no legacy document history."""
    data = io.BytesIO()
    from ..schemas.address_book import LayoutConfig
    layout = LayoutConfig.model_validate(payload.get('layout', {}))
    doc = SimpleDocTemplate(data, pagesize=A4, leftMargin=layout.margin, rightMargin=layout.margin, topMargin=layout.margin, bottomMargin=layout.margin)
    title = ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=13, leading=17, spaceAfter=10)
    body = ParagraphStyle('address', fontName='Helvetica-Bold' if layout.bold else 'Helvetica', fontSize=layout.font_size, leading=layout.font_size+6)
    sender_style = ParagraphStyle('sender', fontName='Helvetica', fontSize=layout.sender_font_size, leading=layout.sender_font_size+5)
    p = payload['endereco']
    from .postal_codes import street_line
    fields = {'nome':p['nome'], 'endereco':street_line(p),
              'cidade':' - '.join(value for value in (p['cidade'],p['estado']) if value),
              'cep':'CEP '+p['cep'] if p['cep'] else '', 'pais':'Brasil' if p['pais']=='BR' else 'Paraguay',
              'telefone':'Tel.: '+p['telefone'] if p['telefone'] else '',
              'cpf':document_line(p)}
    rows = [fields[key] for key in layout.fields]
    def paragraph(text, style):
        return Paragraph(escape(text).replace('\n', '<br/>'), style)
    story = [paragraph(layout.title, title)]
    story.extend(paragraph(row, body) for row in rows if row)
    if p['pais'] == 'BR':
        story += [Spacer(1, layout.sender_gap), Paragraph('REMETENTE', title)]
        story.extend(paragraph(row, sender_style) for row in payload['remetente']['linhas'])
    if layout.template != 'classic':
        from .address_layouts import presentation
        story = presentation(layout, fields, payload.get('remetente') if p['pais'] == 'BR' else None, doc.width - 12)
    try:
        doc.build(story)
    except LayoutError:
        raise ValueError('Endereço excede uma página A4. Reduza os complementos.') from None
    if doc.page != 1:
        raise ValueError('Endereço excede uma página A4. Reduza os complementos.')
    return data.getvalue()


def print_preview(action):
    p = action.payload['endereco']
    from .postal_codes import street_line
    lines = [p['nome'], street_line(p), ' - '.join(value for value in (p['cidade'], p['estado']) if value), p['cep'], p['telefone']]
    lines += action.payload.get('postal_warnings', [])
    if document := document_line(p, preview=True):
        lines.append(document)
    if action.payload.get('reprint_of'):
        lines += ['Nova cópia do endereço já salvo.',
                  action.payload.get('previous_print_diagnostic') or 'O estado anterior não comprova a saída física do papel.',
                  'Confira o papel e a fila da impressora antes de confirmar outra cópia.']
    sender = action.payload.get('remetente')
    from .assistant_controls import preview_reply
    from .address_layouts import TEMPLATES
    return preview_reply(action, ('Imprimir endereço em A4, uma cópia:\n' + '\n'.join(x for x in lines if x) +
            '\nPaís: ' + ('Brasil' if p['pais'] == 'BR' else 'Paraguai') +
            '\nRemetente: ' + (sender['nome'] if sender else 'sem remetente') +
            '\nModelo: ' + TEMPLATES.get(action.payload.get('layout', {}).get('template', 'classic'), 'Clássico') +
            '\nImpressora: ' + action.payload.get('device_name', 'da loja') +
            '\nDiga “confirmo” para enviar à impressora da loja ou “cancela”.\n' +
            'Ainda não foi enviado. Prévia válida por 24 horas.\nIdentificador da prévia: ' + str(action.id)))


def prepare_print(db, message, identity, args, postal_check=None):
    if not message.should_reply or not may_print(db, message, identity):
        return {'erro': 'Impressão exige pedido direto de um usuário autorizado nesta conversa.'}
    omit_document = re.search(r'\bsem\s+(?:o\s+)?cpf\b', message.text, re.I)
    if args.pais == 'PY':
        omit_document = omit_document or re.search(r'\bsem\s+(?:o\s+)?(?:ruc|c\.?\s*i\.?|documento)(?=\W|$)', message.text, re.I)
    if omit_document:
        args = args.model_copy(update={'cpf': ''})
    previous = db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if previous:
        from .assistant_schedule import action_preview
        return {'confirmacao': action_preview(previous)}
    devices = db.query(PrintDevice).filter(PrintDevice.purpose == 'documents').filter_by(active=True).limit(2).all()
    if len(devices) != 1:
        return {'erro': 'É necessário configurar uma única impressora ativa da loja.'}
    sender = None
    if args.pais == 'BR':
        from .assistant_senders import resolve_sender
        profile, sender_error = resolve_sender(db, args.remetente)
        if sender_error:
            return sender_error
        args = args.model_copy(update={'remetente': profile.id})
        sender = {'nome': profile.name, 'linhas': sender_lines(profile)}
    from .address_manager import get_layout
    action_id = uuid.uuid4()
    payload = {'layout': get_layout(db, args.pais, action_id), 'endereco': args.model_dump(), 'remetente': sender, 'device_id': str(devices[0].id), 'device_name': devices[0].name}
    if postal_check:
        payload['postal_warnings'] = postal_check['warnings']
    action = AssistantAction(id=action_id, source_message_id=message.id, user_id=message.user_id, kind='impressao', payload=payload)
    db.add(action)
    db.flush()
    return {'confirmacao': print_preview(action)}


def enqueue_print(db, action):
    from .address_book import lock_addresses, save_print_address
    from ..schemas.address_book import AddressData
    lock_addresses(db)
    device = db.query(PrintDevice).filter(PrintDevice.purpose == 'documents').filter_by(id=uuid.UUID(action.payload['device_id']), active=True).with_for_update().first()
    if not device:
        return 'A impressora foi desativada. Nenhuma impressão enviada.'
    # Action UUID is stable across retries; confirmation and queue commit atomically.
    job = db.query(PrintJob).filter_by(request_key=action.id).first()
    if not job:
        parent_id = uuid.UUID(action.payload['reprint_of']) if action.payload.get('reprint_of') else None
        if parent_id:
            parent = db.query(PrintJob).filter_by(id=parent_id).with_for_update().first()
            pending_copy = db.query(PrintJob.id).filter(
                PrintJob.parent_id == parent_id, PrintJob.status.in_(('pending', 'claimed'))).first()
            if not parent or parent.status in ('pending', 'claimed') or pending_copy:
                return 'O trabalho anterior está em processamento ou indisponível. Nenhuma segunda cópia foi enviada.'
        try:
            pdf = render_address(action.payload)
        except ValueError:
            return 'O endereço excedeu uma folha A4. Cancele esta prévia e envie um endereço mais curto.'
        data = {k:v for k,v in action.payload['endereco'].items() if k in AddressData.model_fields}
        saved=save_print_address(db,AddressData.model_validate(data).model_dump(),action.user_id)
        job = PrintJob(device_id=device.id, user_id=action.user_id, request_key=action.id, address_id=saved.id, parent_id=parent_id,
                       pdf=pdf, snapshot=action.payload, source='bot', sha256=hashlib.sha256(pdf).hexdigest(), expires_at=utcnow()+timedelta(hours=24))
        db.add(job)
        db.flush()
    action.status, action.result_id, action.executed_at = 'executed', job.id, utcnow()
    return ('Endereço enviado à fila de impressão da loja: uma folha A4, uma cópia. '
            f'Impressora: {device.name}. '
            'Mantenha o Eleven Impressao aberto no Windows. O envio à fila ainda não confirma a saída do papel. '
            'Trabalho: ' + str(job.id))
