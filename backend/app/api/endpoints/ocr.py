from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, defer
from typing import List, Optional
from datetime import datetime
import uuid

from ...database import get_db
from ...models.label_template import LabelTemplate
from ...models.usuario import Usuario
from ...dependencies import get_current_active_user
from ...config import settings
from pydantic import BaseModel
from ...schemas.ocr import LabelParseRequest, LabelParseResponse, TemplateSaveRequest
from ...services.ocr_images import prepare_label_image, OcrImageError
from ...services.ocr_service import OcrUnavailable, OcrProviderError
from ...services.ocr_templates import brand_counts, matching_brands, reading_examples
from ...services.inventory_taxonomy import canonical, key
from ...models.inventory import Item

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class TemplateResponse(BaseModel):
    id: uuid.UUID
    brand: str
    notes: Optional[str] = None
    has_image: bool
    created_at: Optional[datetime] = None
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

@router.post("/parse", response_model=LabelParseResponse)
def parse_label(
    request: LabelParseRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Read a label with reviewed examples for the chosen brand, without saving products."""
    try:
        image = prepare_label_image(request.image)
    except OcrImageError as error:
        raise HTTPException(422, str(error)) from None
    templates = reading_examples(db, request.brand)
    try:
        from ...services.ocr_service import parse_label_image
        result = parse_label_image(image, request.brand, templates)
    except OcrUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except OcrProviderError as error:
        raise HTTPException(502, str(error)) from None
    if result.get('codigo_barras'):
        matches = db.query(Item).filter(Item.barcode == result['codigo_barras'], Item.is_active == True, Item.deleted_at.is_(None))
        result['matches_total'] = matches.count()
        result['matches'] = [{'id': str(row.id), 'name': row.name, 'sku_internal': row.sku_internal}
                             for row in matches.order_by(Item.name, Item.id).limit(5).all()]
        if result['matches_total']:
            result['avisos'].append('barcode_exists')
    return result


@router.get("/brands")
def get_brands(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """List brands that have saved templates with counts."""
    return brand_counts(db)


@router.get("/templates", response_model=List[TemplateResponse])
def list_templates(
    brand: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """List saved label templates (without images for performance)."""
    q = db.query(LabelTemplate, func.length(LabelTemplate.sample_image) > 0).options(
        defer(LabelTemplate.sample_image),
    ).filter(LabelTemplate.is_active == True)
    if brand:
        q = q.filter(LabelTemplate.brand.in_(matching_brands(db, brand)))
    templates = q.order_by(LabelTemplate.brand, LabelTemplate.created_at.desc()).all()
    labels = {key(row['brand'], 'brand'): row['brand'] for row in brand_counts(db)}
    result = []
    for t, has_image in templates:
        result.append(TemplateResponse(
            id=t.id,
            brand=labels.get(key(t.brand, 'brand'), canonical(t.brand, 'brand')),
            notes=t.notes,
            has_image=bool(has_image),
            created_at=t.created_at,
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
    labels = {key(row['brand'], 'brand'): row['brand'] for row in brand_counts(db)}
    return TemplateWithImageResponse(
        id=t.id, brand=labels.get(key(t.brand, 'brand'), canonical(t.brand, 'brand')), notes=t.notes, has_image=bool(t.sample_image),
        created_at=t.created_at,
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
    """Save an explicitly reviewed example for future readings; no model training."""
    try:
        image = prepare_label_image(request.sample_image)
    except OcrImageError as error:
        raise HTTPException(422, str(error)) from None
    t = LabelTemplate(
        brand=canonical(request.brand, 'brand'),
        notes=request.notes,
        sample_image=image.data_url,
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
