from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from ...database import get_db
from ...models.label_template import LabelTemplate
from ...models.usuario import Usuario
from ...dependencies import get_current_active_user
from ...config import settings
from pydantic import BaseModel

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class LabelParseRequest(BaseModel):
    image: str          # base64 JPEG
    brand: Optional[str] = None


class TemplateSaveRequest(BaseModel):
    brand: str
    notes: Optional[str] = None
    sample_image: str   # base64 JPEG
    parsed_name: Optional[str] = None
    parsed_size: Optional[str] = None
    parsed_color: Optional[str] = None
    parsed_barcode: Optional[str] = None
    parsed_price: Optional[str] = None
    parsed_currency: Optional[str] = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    brand: str
    notes: Optional[str] = None
    has_image: bool
    parsed_name: Optional[str] = None
    parsed_size: Optional[str] = None
    parsed_color: Optional[str] = None
    parsed_barcode: Optional[str] = None
    parsed_price: Optional[str] = None
    parsed_currency: Optional[str] = None

    class Config:
        from_attributes = True


class TemplateWithImageResponse(TemplateResponse):
    sample_image: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/parse")
def parse_label(
    request: LabelParseRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Parse a product label image using Claude Vision with optional brand few-shot examples."""
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OCR com IA não configurado — defina ANTHROPIC_API_KEY no ambiente."
        )

    templates = []
    if request.brand:
        templates = (
            db.query(LabelTemplate)
            .filter(LabelTemplate.brand.ilike(request.brand), LabelTemplate.is_active == True)
            .order_by(LabelTemplate.created_at.desc())
            .limit(3)
            .all()
        )

    try:
        from ...services.ocr_service import parse_label_image
        result = parse_label_image(request.image, request.brand, templates)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar imagem: {str(e)}")


@router.get("/brands")
def get_brands(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """List brands that have saved templates with counts."""
    rows = (
        db.query(LabelTemplate.brand)
        .filter(LabelTemplate.is_active == True)
        .all()
    )
    counts: dict = {}
    for (brand,) in rows:
        counts[brand] = counts.get(brand, 0) + 1
    return [{"brand": b, "count": c} for b, c in sorted(counts.items())]


@router.get("/templates", response_model=List[TemplateResponse])
def list_templates(
    brand: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """List saved label templates (without images for performance)."""
    q = db.query(LabelTemplate).filter(LabelTemplate.is_active == True)
    if brand:
        q = q.filter(LabelTemplate.brand.ilike(f"%{brand}%"))
    templates = q.order_by(LabelTemplate.brand, LabelTemplate.created_at.desc()).all()
    result = []
    for t in templates:
        result.append(TemplateResponse(
            id=t.id,
            brand=t.brand,
            notes=t.notes,
            has_image=bool(t.sample_image),
            parsed_name=t.parsed_name,
            parsed_size=t.parsed_size,
            parsed_color=t.parsed_color,
            parsed_barcode=t.parsed_barcode,
            parsed_price=t.parsed_price,
            parsed_currency=t.parsed_currency,
        ))
    return result


@router.get("/templates/{template_id}", response_model=TemplateWithImageResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID inválido")
    t = db.query(LabelTemplate).filter(LabelTemplate.id == tid).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    return TemplateWithImageResponse(
        id=t.id, brand=t.brand, notes=t.notes, has_image=bool(t.sample_image),
        sample_image=t.sample_image,
        parsed_name=t.parsed_name, parsed_size=t.parsed_size,
        parsed_color=t.parsed_color, parsed_barcode=t.parsed_barcode,
        parsed_price=t.parsed_price, parsed_currency=t.parsed_currency,
    )


@router.post("/templates", status_code=201)
def save_template(
    request: TemplateSaveRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Save a label example as a training template for a brand."""
    t = LabelTemplate(
        brand=request.brand.strip(),
        notes=request.notes,
        sample_image=request.sample_image,
        parsed_name=request.parsed_name,
        parsed_size=request.parsed_size,
        parsed_color=request.parsed_color,
        parsed_barcode=request.parsed_barcode,
        parsed_price=request.parsed_price,
        parsed_currency=request.parsed_currency,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": str(t.id), "brand": t.brand, "message": "Modelo salvo com sucesso"}


@router.delete("/templates/{template_id}", status_code=200)
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID inválido")
    t = db.query(LabelTemplate).filter(LabelTemplate.id == tid).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    t.is_active = False
    db.commit()
    return {"message": "Template removido"}
