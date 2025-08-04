from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, DECIMAL, Date, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base

class Funcionario(Base):
    __tablename__ = "funcionarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(100), nullable=False)
    cpf = Column(String(14), unique=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    
    cargo = Column(String(100))
    salario = Column(DECIMAL(10,2))
    data_admissao = Column(Date)
    data_demissao = Column(Date)
    
    horarios = Column(JSONB)
    
    telefone = Column(String(20))
    endereco = Column(Text)
    
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    usuario = relationship("Usuario", backref="funcionario")