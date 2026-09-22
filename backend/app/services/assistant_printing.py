"""Confirmed address printing through the existing device queue."""
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

from ..models.assistant import AssistantAction, utcnow
from ..models.printing import PrintDevice, PrintJob, PrintSender
from .assistant_schedule import may_schedule


def printable_cpf(value):
    if not value:
        return ''
    digits = re.sub(r'[^0-9]', '', value)
    if len(digits) == 11 and len(set(digits)) == 1:
        return ''  # Placeholders, including legacy all-zero drafts, never reach paper.
    if len(digits) != 11 or not re.fullmatch(r'[0-9. -]+', value):
        raise ValueError('CPF informado deve conter 11 dígitos; se ausente, deixe vazio.')
    return f'{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}'


class AddressArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    pais: Literal['BR', 'PY']
    nome: str = Field(default='', max_length=120)
    endereco: str = Field(default='', max_length=250, description='Rua ou detalhes fornecidos. Opcional no PY: deixe vazio quando ausente, nunca invente.')
    cidade: str = Field(default='', max_length=100)
    estado: str = Field(default='', max_length=60, description='UF obrigatória no Brasil; departamento opcional no Paraguai.')
    cep: str = Field(default='', max_length=15)
    cpf: str = Field(default='', max_length=20, description='CPF opcional do destinatário. Extraia do endereço informado. Ausente ou pedido sem CPF: string vazia. Nunca preencha zeros nem use CPF do remetente.')
    telefone: str = Field(default='', max_length=40)
    remetente: str | None = Field(default=None, max_length=30, description='ID do remetente ativo cadastrado no gestor; debora e mona são os iniciais.')

    @field_validator('nome', 'endereco', 'cidade', 'estado', 'cep', 'cpf', 'telefone', mode='before')
    @classmethod
    def plain_text(cls, value):
        return ' '.join(value.split()) if isinstance(value, str) else value

    @model_validator(mode='after')
    def address_rules(self):
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
            self.cpf = printable_cpf(self.cpf)
            if not self.remetente:
                raise ValueError('Escolha um remetente ativo cadastrado no gestor.')
        else:
            self.remetente = None
            self.cpf = ''
        return self


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
    fields = {'nome':p['nome'], 'endereco':p['endereco'],
              'cidade':' - '.join(value for value in (p['cidade'],p['estado']) if value),
              'cep':'CEP '+p['cep'] if p['cep'] else '', 'pais':'Brasil' if p['pais']=='BR' else 'Paraguay',
              'telefone':'Tel.: '+p['telefone'] if p['telefone'] else '',
              'cpf':'CPF: '+printable_cpf(p.get('cpf')) if p['pais']=='BR' and printable_cpf(p.get('cpf')) else ''}
    rows = [fields[key] for key in layout.fields]
    def paragraph(text, style):
        return Paragraph(escape(text).replace('\n', '<br/>'), style)
    story = [paragraph(layout.title, title)]
    story.extend(paragraph(row, body) for row in rows if row)
    if p['pais'] == 'BR':
        story += [Spacer(1, layout.sender_gap), Paragraph('REMETENTE', title)]
        story.extend(paragraph(row, sender_style) for row in payload['remetente']['linhas'])
    doc.build(story)
    if doc.page != 1:
        raise ValueError('Endereço excede uma página A4. Reduza os complementos.')
    return data.getvalue()


def print_preview(action):
    p = action.payload['endereco']
    lines = [p['nome'], p['endereco'], ' - '.join(value for value in (p['cidade'], p['estado']) if value), p['cep'], p['telefone']]
    if p['pais'] == 'BR' and printable_cpf(p.get('cpf')):
        lines.append('CPF do destinatário: ' + printable_cpf(p.get('cpf')))
    sender = action.payload.get('remetente')
    return ('Imprimir endereço em A4, uma cópia:\n' + '\n'.join(x for x in lines if x) +
            '\nPaís: ' + ('Brasil' if p['pais'] == 'BR' else 'Paraguai') +
            '\nRemetente: ' + (sender['nome'] if sender else 'sem remetente') +
            '\nDiga “confirmo” para enviar à impressora da loja ou “cancela”.\n' +
            'Ainda não foi enviado. Prévia válida por 24 horas.\nIdentificador da prévia: ' + str(action.id))


def prepare_print(db, message, identity, args):
    if not message.should_reply or not may_schedule(db, message, identity):
        return {'erro': 'Impressão exige pedido direto de ADMIN/GERENTE habilitado para registros.'}
    if re.search(r'\bsem\s+(?:o\s+)?cpf\b', message.text, re.I):
        args = args.model_copy(update={'cpf': ''})
    previous = db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if previous:
        from .assistant_schedule import action_preview
        return {'confirmacao': action_preview(previous)}
    devices = db.query(PrintDevice).filter_by(active=True).limit(2).all()
    if len(devices) != 1:
        return {'erro': 'É necessário configurar uma única impressora ativa da loja.'}
    sender = None
    if args.pais == 'BR':
        profile = db.get(PrintSender, args.remetente)
        if not profile or not profile.active:
            return {'erro': 'Remetente ainda não configurado no ERP. Nenhuma impressão enviada.'}
        sender = {'nome': profile.name, 'linhas': list(profile.lines)}
    from .address_manager import get_layout
    payload = {'layout': get_layout(db, args.pais), 'endereco': args.model_dump(), 'remetente': sender, 'device_id': str(devices[0].id)}
    action = AssistantAction(source_message_id=message.id, user_id=message.user_id, kind='impressao', payload=payload)
    db.add(action)
    db.flush()
    return {'confirmacao': print_preview(action)}


def enqueue_print(db, action):
    device = db.query(PrintDevice).filter_by(id=uuid.UUID(action.payload['device_id']), active=True).with_for_update().first()
    if not device:
        return 'A impressora foi desativada. Nenhuma impressão enviada.'
    # Action UUID is stable across retries; confirmation and queue commit atomically.
    job = db.query(PrintJob).filter_by(request_key=action.id).first()
    if not job:
        try:
            pdf = render_address(action.payload)
        except ValueError:
            return 'O endereço excedeu uma folha A4. Cancele esta prévia e envie um endereço mais curto.'
        job = PrintJob(device_id=device.id, user_id=action.user_id, request_key=action.id,
                       pdf=pdf, snapshot=action.payload, source='bot', sha256=hashlib.sha256(pdf).hexdigest(), expires_at=utcnow()+timedelta(hours=24))
        db.add(job)
        db.flush()
    action.status, action.result_id, action.executed_at = 'executed', job.id, utcnow()
    return ('Endereço enviado à fila de impressão da loja: uma folha A4, uma cópia. '
            'Mantenha o Eleven Impressao aberto no Windows. O envio à fila ainda não confirma a saída do papel. '
            'Trabalho: ' + str(job.id))
