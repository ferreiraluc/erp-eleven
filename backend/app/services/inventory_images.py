"""Small catalog previews. Original photos are read one at a time, never by a catalog scan."""
import base64
import io
import threading
from collections import OrderedDict

from fastapi import HTTPException
from PIL import Image, ImageOps
from sqlalchemy.orm import defer

from ..models.inventory import Item
from ..schemas.inventory import ItemResponse

_thumbnail_lock = threading.Lock()
_thumbnails = OrderedDict()
MAX_CACHE = 64  # At most ~3 MB of encoded 256px previews.
MAX_ENCODED = 7 * 1024 * 1024


def catalog_query(query, include_images):
    if not include_images:
        query = query.options(defer(Item.image_data, raiseload=True))
    return query.add_columns((Item.image_data.isnot(None) & (Item.image_data != '')).label('has_image'))


def catalog_response(item, has_image, include_images):
    if include_images:
        response = ItemResponse.model_validate(item)
        response.has_image = has_image
        return response
    data = {name: getattr(item, name) for name in ItemResponse.model_fields
            if name not in ('image_data', 'has_image', 'alert_level')}
    return ItemResponse(**data, has_image=has_image, image_data=None)


def _thumbnail(data):
    if not data or len(data) > MAX_ENCODED or not data.startswith('data:image/'):
        return None
    try:
        raw = base64.b64decode(data.split(',', 1)[1], validate=True)
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > 16_000_000:
                return None
            # JPEG draft decoding reduces the input buffer before raster expansion.
            source.draft('RGB', (256, 256))
            source.thumbnail((256, 256), Image.Resampling.LANCZOS)
            with ImageOps.exif_transpose(source) as oriented, Image.new('RGB', oriented.size, 'white') as clean:
                clean.paste(oriented, mask=oriented.getchannel('A') if 'A' in oriented.getbands() else None)
                out = io.BytesIO()
                clean.save(out, format='JPEG', quality=72)
                result = 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
                return result if len(result) <= 48 * 1024 else None
    except (ValueError, IndexError, OSError, Image.DecompressionBombError):
        return None


def product_thumbnail(db, item_id):
    # Read-only endpoint: release the authentication transaction before waiting.
    # Otherwise every waiting thumbnail holds a connection needed by API/workers.
    db.close()
    if not _thumbnail_lock.acquire(timeout=0.5):
        raise HTTPException(503, 'Miniatura ocupada. Tente novamente.', headers={'Retry-After': '2'})
    try:
        try:
            row = db.query(Item.id, Item.updated_at).filter(Item.id == item_id, Item.deleted_at.is_(None)).first()
            if row is None:
                raise HTTPException(404, 'Produto não encontrado')
            key = (row.id, row.updated_at)
            cached = key in _thumbnails
            data = None if cached else db.query(Item.image_data).filter(Item.id == item_id, Item.deleted_at.is_(None)).scalar()
        finally:
            # Decoding can be slow; it must not keep a database connection open.
            db.close()
        if not cached:
            _thumbnails[key] = _thumbnail(data)
            while len(_thumbnails) > MAX_CACHE:
                _thumbnails.popitem(last=False)
        _thumbnails.move_to_end(key)
        return {'image_data': _thumbnails[key]}
    finally:
        _thumbnail_lock.release()
