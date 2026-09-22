from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AddressData(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    pais: Literal['BR','PY'] = 'PY'
    nome: str = Field(default='', max_length=120)
    telefone: str = Field(default='', max_length=40)
    cpf: str = Field(default='', max_length=20)
    endereco: str = Field(default='', max_length=250)
    numero: str = Field(default='', max_length=10)
    bairro: str = Field(default='', max_length=60)
    complemento: str = Field(default='', max_length=60)
    cidade: str = Field(default='', max_length=100)
    estado: str = Field(default='', max_length=60)
    cep: str = Field(default='', max_length=15)
    email: str = Field(default='', max_length=100)


class AddressInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field(min_length=1,max_length=120)
    cliente_id: UUID | None = None
    pdv_cliente_id: UUID | None = None
    data: AddressData
    active: bool = True
    version: int = Field(default=1,ge=1)
    @model_validator(mode='after')
    def one_customer(self):
        if self.cliente_id and self.pdv_cliente_id: raise ValueError('Selecione somente um cadastro de cliente.')
        return self


class SenderInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=100)
    lines: list[str] = Field(min_length=1,max_length=10)
    data: AddressData | None = None
    active: bool = True
    version: int = Field(default=1,ge=1)
    @model_validator(mode='after')
    def bounds(self):
        if any(len(line)>150 for line in self.lines): raise ValueError('Linha do remetente muito longa.')
        return self


class LayoutConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    font_size: int = Field(default=17,ge=10,le=24)
    margin: int = Field(default=42,ge=20,le=80)
    sender_font_size: int = Field(default=12,ge=9,le=20)
    sender_gap: int = Field(default=40,ge=10,le=100)
    bold: bool = True
    title: str = Field(default='DESTINATÁRIO',max_length=60)
    fields: list[Literal['nome','endereco','cidade','cep','pais','telefone','cpf']] = Field(default_factory=lambda:['nome','endereco','cidade','cep','pais','telefone','cpf'],min_length=1,max_length=7)
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.fields)) != len(self.fields): raise ValueError('Campos repetidos no modelo.')
        return self


class LayoutInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    config: LayoutConfig
    version: int = Field(default=0,ge=0)


class PrintInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: UUID
    address_id: UUID | None = None
    device_id: UUID
    sender_id: str | None = Field(default=None,max_length=30)
    data: AddressData
    layout_id: Literal['br','py'] | None = None
    parent_id: UUID | None = None
