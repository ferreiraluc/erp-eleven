"""Bounded notification inputs; templates only interpolate explicitly named values."""
import re
import uuid
from datetime import datetime, timedelta, timezone
from string import Formatter
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal['manual', 'sales', 'tracking', 'reminder', 'greeting']
Severity = Literal['info', 'success', 'warning', 'urgent']
CATEGORIES = ['manual', 'sales', 'tracking', 'reminder', 'greeting']
TEMPLATE_VARIABLES = {'user_name', 'cliente_username', 'sale_code', 'tracking_code', 'status', 'date', 'time'}
MANUAL_TOKEN = re.compile(r'\{\{|\}\}|\{([^{}]*)\}')
MANUAL_VARIABLE_START = re.compile(r'\{(' + '|'.join(sorted(TEMPLATE_VARIABLES)) + r')(?=[^A-Za-z0-9_]|$)')
ALLOWED_PATHS = {'/notificacoes', '/dashboard', '/inventory', '/inventory/labels', '/pdv', '/vendas-pdv',
                 '/rastreamento', '/clientes', '/pedidos', '/conta', '/auditoria', '/configuracoes',
                 '/vendors', '/vendas', '/bi-vendas', '/enderecos', '/fiado', '/assistente', '/usuarios'}


def validate_action_path(value):
    if value is None or value == '':
        return None
    if any(ord(c) < 32 for c in value) or '\\' in value or '#' in value or '%' in value.split('?', 1)[0]:
        raise ValueError('Use somente um caminho interno do ERP.')
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or parts.path not in ALLOWED_PATHS:
        raise ValueError('Use somente um caminho interno conhecido do ERP.')
    return value


def validate_template(value):
    try:
        fields = Formatter().parse(value)
        for _, field, spec, conversion in fields:
            if field is not None and (field not in TEMPLATE_VARIABLES or spec or conversion):
                raise ValueError('Variáveis disponíveis: ' + ', '.join(sorted(TEMPLATE_VARIABLES)))
    except (ValueError, IndexError) as exc:
        raise ValueError('Modelo inválido: use apenas as variáveis disponíveis, entre chaves.') from exc
    return value


def validate_manual_template(value):
    # Plain manual messages historically accepted braces (sizes, JSON, etc.).
    # Only recognized variables have template semantics; escaped braces remain
    # literal and known variables cannot use Python attributes/specifiers.
    unescaped = value.replace('{{', '').replace('}}', '')
    if any(unescaped[match.end():match.end() + 1] != '}' for match in MANUAL_VARIABLE_START.finditer(unescaped)):
        raise ValueError('Use as variáveis disponíveis sem atributos, formatos ou conversões.')
    return value


class NotificationFields(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=2000)
    category: Category = 'manual'
    severity: Severity = 'info'
    action_path: str | None = Field(None, max_length=500)
    requires_ack: bool = False
    requires_response: bool = False
    _path = field_validator('action_path')(validate_action_path)

    @model_validator(mode='after')
    def response_requires_ack(self):
        if self.requires_response:
            self.requires_ack = True
        return self


class NotificationContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sale_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    target: Literal['sale', 'product'] | None = None

    @model_validator(mode='after')
    def valid_target(self):
        self.target = self.target or ('product' if self.item_id else 'sale')
        if self.target == 'sale' and self.sale_id is None:
            raise ValueError('Selecione a venda para esse atalho.')
        if self.target == 'product' and self.item_id is None:
            raise ValueError('Selecione o produto de referência para esse atalho.')
        return self


class NotificationCreate(NotificationFields):
    context: NotificationContext | None = None
    _title = field_validator('title')(validate_manual_template)
    _body = field_validator('body')(validate_manual_template)
    request_id: uuid.UUID
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    scheduled_at: datetime | None = None

    @field_validator('scheduled_at')
    @classmethod
    def aware_schedule(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError('Informe a data com o fuso horário.')
            if value > datetime.now(timezone.utc) + timedelta(days=366):
                raise ValueError('Agende a notificação dentro de um ano.')
        return value


class NotificationUpdate(NotificationFields):
    context: NotificationContext | None = None
    _title = field_validator('title')(validate_manual_template)
    _body = field_validator('body')(validate_manual_template)
    expected_version: int = Field(ge=1)
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    scheduled_at: datetime | None = None
    _schedule = field_validator('scheduled_at')(NotificationCreate.aware_schedule)


class ExpectedVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class Acknowledge(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    note: str | None = Field(None, max_length=1000)
    expected_version: int | None = Field(None, ge=1)


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    push_enabled: bool
    sound_enabled: bool
    categories: list[Category] = Field(max_length=5)


class TemplateCreate(NotificationFields):
    name: str = Field(min_length=1, max_length=100)
    _title = field_validator('title')(validate_template)
    _body = field_validator('body')(validate_template)


class TemplateUpdate(TemplateCreate):
    expected_version: int = Field(ge=1)


class RuleUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    enabled: bool
    template_id: uuid.UUID
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    local_time: str = '09:00'
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)

    @field_validator('local_time')
    @classmethod
    def valid_time(cls, value):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
            raise ValueError('Use um horário válido, como 09:00.')
        return value

    @field_validator('weekdays')
    @classmethod
    def valid_days(cls, value):
        if any(type(day) is not int or not 0 <= day <= 6 for day in value):
            raise ValueError('Dias da semana devem estar entre 0 e 6.')
        return sorted(set(value))
