"""Validate product-label images and strip metadata in memory before external OCR."""
import base64
import binascii
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ENCODED_LENGTH = ((MAX_IMAGE_BYTES + 2) // 3) * 4 + 64
MAX_PIXELS = 16_000_000
MAX_EDGE = 4096
FORMATS = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}


class OcrImageError(ValueError):
    pass


@dataclass(frozen=True)
class LabelImage:
    data: str
    width: int
    height: int
    media_type: str = 'image/jpeg'

    @property
    def data_url(self):
        return f'data:{self.media_type};base64,{self.data}'


def prepare_label_image(value: str) -> LabelImage:
    if not isinstance(value, str) or not value or len(value) > MAX_ENCODED_LENGTH:
        raise OcrImageError('Envie uma imagem JPEG, PNG ou WebP de até 5 MB.')
    claimed = None
    if value.startswith('data:'):
        header, separator, value = value.partition(',')
        if not separator or not header.endswith(';base64'):
            raise OcrImageError('Imagem base64 inválida.')
        claimed = header[5:-7]
        if claimed not in FORMATS.values():
            raise OcrImageError('Formato não aceito. Use JPEG, PNG ou WebP estático.')
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise OcrImageError('Imagem base64 inválida.') from None
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise OcrImageError('A imagem deve ter até 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in FORMATS or getattr(source, 'n_frames', 1) != 1:
                    raise OcrImageError('Formato não aceito. Use JPEG, PNG ou WebP estático.')
                if claimed and FORMATS[source.format] != claimed:
                    raise OcrImageError('O tipo declarado não corresponde ao conteúdo da imagem.')
                width, height = source.size
                if min(width, height) < 64 or max(width, height) > MAX_EDGE or width * height > MAX_PIXELS:
                    raise OcrImageError('Use uma imagem entre 64 e 4096 pixels por lado, com até 16 megapixels.')
                source.verify()
            with Image.open(io.BytesIO(raw)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                clean = Image.new('RGB', oriented.size, 'white')
                if 'A' in oriented.getbands():
                    clean.paste(oriented, mask=oriented.getchannel('A'))
                else:
                    clean.paste(oriented.convert('RGB'))
                clean.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                # Fresh encoding drops EXIF, filenames and other metadata. No disk writes.
                clean.save(output, format='JPEG', quality=92, optimize=True)
                return LabelImage(base64.b64encode(output.getvalue()).decode('ascii'), clean.width, clean.height)
    except OcrImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise OcrImageError('Não foi possível decodificar a imagem. Envie outra foto da etiqueta.') from None
