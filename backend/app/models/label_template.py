from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base
from ..config import settings


class LabelTemplate(Base):
    __tablename__ = "label_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand = Column(String(100), nullable=False, index=True)
    notes = Column(Text)              # extra hints for Claude
    sample_image = Column(Text)       # base64 JPEG ~600px
    parsed_name = Column(String(200))
    parsed_size = Column(String(50))
    parsed_color = Column(String(50))
    parsed_barcode = Column(String(50))
    parsed_price = Column(String(30))
    parsed_currency = Column(String(10))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
