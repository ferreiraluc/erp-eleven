"""Named product designs stored separately from address layouts by a strict namespace."""
import re

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from ..models.address_book import PrintLayout
from ..models.assistant import utcnow
from ..schemas.product_label_layout import LabelDesign

LAYOUT_ID = re.compile(r'^product-[a-f0-9]{20}$')


def default_config():
    def text(id, field, x, y, width, height, font_size=16, **options):
        return dict(id=id, type='text', field=field, x=x, y=y, width=width,
                    height=height, font_size=font_size, **options)
    return LabelDesign.model_validate(dict(elements=[
        text('title', 'title', 165, 20, 152, 32, 38, bold=True, align='center', text='ELEVEN'),
        text('name', 'name', 32, 60, 292, 20),
        text('size', 'size', 32, 87, 292, 20),
        text('color', 'color', 32, 112, 292, 20),
        text('code', 'code', 32, 143, 292, 20),
        dict(id='qr', type='qr', x=336, y=51, module_size=3),
        text('price', 'price', 32, 188, 270, 34, 27, uppercase=False),
        text('barcode', 'barcode', 324, 202, 145, 18, 14),
    ])).model_dump()


def standard():
    return dict(id='standard', name='Padrão ELEVEN', version=0, builtin=True, config=default_config())


def view(row):
    return dict(id=row.id, name=row.name, version=row.version, builtin=False,
                config=LabelDesign.model_validate(row.config).model_dump())


def listing(db):
    return [standard(), *[view(row) for row in db.query(PrintLayout).filter(
        PrintLayout.id.like('product-%')).order_by(PrintLayout.name, PrintLayout.id).all()]]


def find(db, key, version=None, lock=False):
    if not LAYOUT_ID.fullmatch(key):
        raise HTTPException(404, 'Modelo de etiqueta não encontrado.')
    query = db.query(PrintLayout).filter_by(id=key)
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(404, 'Modelo de etiqueta não encontrado.')
    if version is not None and row.version != version:
        raise HTTPException(409, 'O modelo de etiqueta mudou. Atualize os modelos e confira a prévia.')
    return row


def save(db, key, body):
    if not LAYOUT_ID.fullmatch(key):
        raise HTTPException(422, 'Identificação de modelo inválida. Salve uma cópia do padrão.')
    row = db.query(PrintLayout).filter_by(id=key).with_for_update().first()
    if row:
        if row.version != body.version:
            raise HTTPException(409, 'O modelo de etiqueta mudou. Atualize os modelos e confira a prévia.')
    else:
        if body.version != 0:
            raise HTTPException(409, 'Modelo removido. Salve uma nova cópia.')
        row = PrintLayout(id=key, version=0)
        db.add(row)
    row.name, row.config = body.name, body.config.model_dump()
    row.version += 1
    row.updated_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'O modelo de etiqueta mudou. Atualize os modelos e confira a prévia.') from None
    return view(row)


def delete(db, key, version):
    row = find(db, key, version, lock=True)
    db.delete(row)
    db.commit()
    return dict(deleted=True)
