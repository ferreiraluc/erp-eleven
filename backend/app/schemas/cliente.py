from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, Literal
from datetime import datetime
import uuid
from ..services.customer_documents import normalize_document, document_identity


class CustomerDocument(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    tipo: Literal['CPF', 'CNPJ', 'RG', 'CI', 'RUC']
    pais: Literal['BR', 'PY']
    numero: str = Field(min_length=3, max_length=40)
    emissor: Optional[str] = Field(default=None, max_length=20)

    @model_validator(mode='after')
    def valid_document(self):
        value = normalize_document(self.model_dump())
        if not value:
            raise ValueError('Confira o tipo, país e número do documento informado.')
        self.numero = value['numero']
        self.emissor = value.get('emissor')
        return self


def validate_documents(values, cpf):
    keys = [document_identity(value.model_dump()) for value in values or []]
    if len(set(keys)) != len(keys):
        raise ValueError('O mesmo documento foi informado mais de uma vez.')
    # A single CPF/CNPJ value is an established legacy field, never RG/CI/RUC.
    if cpf:
        from ..services.customer_documents import legacy_document
        document = legacy_document(cpf)
        if document:
            same = [value for value in values or [] if value.tipo == document['tipo']]
            if same and all(value.numero != document['numero'] for value in same):
                raise ValueError('O CPF/CNPJ e os documentos do cliente precisam corresponder.')


class ClienteBase(BaseModel):
    nome: str
    telefone: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    documentos: list[CustomerDocument] = Field(default_factory=list, max_length=10)
    endereco: Optional[str] = None
    ativo: Optional[bool] = True

    @model_validator(mode='after')
    def documents_consistent(self):
        validate_documents(self.documentos, self.cpf)
        return self


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    documentos: Optional[list[CustomerDocument]] = Field(default=None, max_length=10)
    endereco: Optional[str] = None
    ativo: Optional[bool] = None

    @model_validator(mode='after')
    def documents_consistent(self):
        validate_documents(self.documentos, self.cpf)
        return self


class ClienteResponse(ClienteBase):
    # Confirmed operational links may accumulate more documents over time than
    # one editor submission; presenting existing identity history must not fail.
    documentos: list[CustomerDocument] = Field(default_factory=list)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerActivity(BaseModel):
    purchase_count: int = 0
    order_count: int = 0
    shipment_count: int = 0
    print_count: int = 0
    submitted_print_count: int = 0
    pending_print_count: int = 0
    uncertain_print_count: int = 0
    last_purchase_at: Optional[datetime] = None
    last_print_at: Optional[datetime] = None
    own_sales_only: bool = False


class ClienteDirectoryEntry(ClienteResponse):
    activity: CustomerActivity


class ClientePage(BaseModel):
    items: list[ClienteDirectoryEntry]
    total: int
    page: int
    page_size: int


class ClienteSimple(BaseModel):
    id: uuid.UUID
    nome: str
    telefone: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    documentos: list[CustomerDocument] = Field(default_factory=list)
    endereco: Optional[str] = None

    class Config:
        from_attributes = True
