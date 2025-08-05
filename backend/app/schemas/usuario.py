from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import uuid
from ..models.usuario import UsuarioRole

class UsuarioBase(BaseModel):
    nome: str
    email: EmailStr
    role: UsuarioRole = UsuarioRole.VENDEDOR
    ativo: Optional[bool] = True

class UsuarioCreate(UsuarioBase):
    senha: str

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
    email: EmailStr
    senha: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    email: Optional[str] = None