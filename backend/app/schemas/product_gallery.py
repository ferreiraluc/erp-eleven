"""Bounded, optional gallery input; legacy primary-photo contracts stay intact."""
import base64
import binascii
import io

from PIL import Image
from pydantic import BaseModel, Field, field_validator


class GalleryInput(BaseModel):
    additional_images: list[str] | None = Field(default=None, max_length=4)

    @field_validator('additional_images')
    @classmethod
    def valid_photos(cls, photos):
        if photos is None:
            return photos
        for photo in photos:
            if len(photo) > 340000:
                raise ValueError('Cada foto adicional deve ter até 250 KB após a compressão.')
            try:
                prefix, encoded = photo.split(',', 1)
                formats = {'data:image/jpeg;base64': 'JPEG', 'data:image/png;base64': 'PNG',
                           'data:image/webp;base64': 'WEBP'}
                if prefix not in formats:
                    raise ValueError()
                raw = base64.b64decode(encoded, validate=True)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != formats[prefix] or max(image.size) > 1200 or min(image.size) < 1 or getattr(image, 'n_frames', 1) != 1:
                        raise ValueError()
                    image.verify()
            except (ValueError, binascii.Error, OSError, Image.DecompressionBombError) as exc:
                raise ValueError('Foto adicional inválida. Use JPEG, PNG ou WebP de até 1200 px.') from exc
        return photos
