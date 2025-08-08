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
    senha: str = Field(..., min_length=6, max_length=100, description="Senha do usuário (mínimo 6 caracteres)")
    
    @validator('senha')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Senha deve ter pelo menos 6 caracteres')
        return v

class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UsuarioRole] = None
    ativo: Optional[bool] = None
    senha: Optional[str] = None

class UsuarioResponse(UsuarioBase):
    id: uuid.UUID
    ultimo_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UsuarioLogin(BaseModel):
    email: EmailStr = Field(..., description="Email do usuário")
    senha: str = Field(..., min_length=1, description="Senha do usuário")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    email: Optional[str] = None