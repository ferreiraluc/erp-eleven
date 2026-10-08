from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import uuid
from ..models.usuario import UsuarioRole

class UsuarioBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100, description="Nome completo do usuário")
    email: EmailStr = Field(..., description="Email válido do usuário")
    role: UsuarioRole = UsuarioRole.VENDEDOR
    ativo: Optional[bool] = True

class UsuarioCreate(UsuarioBase):
    senha: str = Field(..., min_length=12, max_length=100, description="Senha do usuário (mínimo 12 caracteres)")
    
    @validator('senha')
    def validate_password(cls, v):
        if len(v) < 12:
            raise ValueError('Senha deve ter pelo menos 12 caracteres')
        return v

class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UsuarioRole] = None
    ativo: Optional[bool] = None
    senha: Optional[str] = None

class UsuarioResponse(UsuarioBase):
    # Historical bot identities use reserved internal domains. Validate real e-mail
    # on input, but do not make listing those existing accounts fail serialization.
    email: str
    must_change_password: bool = False
    sales_scope: str = "all"
    sales_seller: Optional[str] = None
    vendedor_id: Optional[uuid.UUID] = None
    id: uuid.UUID
    ultimo_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UsuarioLogin(BaseModel):
    email: EmailStr = Field(..., max_length=100, description="Email do usuário")
    senha: str = Field(..., min_length=1, max_length=72, repr=False, description="Senha do usuário")

    @validator('senha')
    def login_password_bytes(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('Senha excede o limite de 72 bytes.')
        return value

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    email: Optional[str] = None
