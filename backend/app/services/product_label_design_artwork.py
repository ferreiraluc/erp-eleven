"""Render validated design objects to the same bounded 1-bit Zebra bitmap."""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.barcode.qr import QrCodeWidget

from ..schemas.product_label_layout import LabelDesign, element_size
from .product_label_artwork import WIDTH, HEIGHT, TEXT_FONT, TITLE_FONT


@lru_cache(maxsize=256)
def _font(family, size, bold):
    font = ImageFont.truetype(str(TEXT_FONT if family == 'arimo' else TITLE_FONT), size)
    if family == 'arimo' and bold:
        font.set_variation_by_name('Bold')
    return font


def _wrap(draw, value, font, width):
    lines, remaining = [], value
    while remaining:
        low, high = 0, len(remaining)
        while low < high:
            middle = (low + high + 1) // 2
            if draw.textlength(remaining[:middle], font=font) <= width:
                low = middle
            else:
                high = middle - 1
        end = max(1, low)
        if end < len(remaining):
            space = remaining.rfind(' ', 0, end + 1)
            if space > end // 2:
                end = space
        lines.append(remaining[:end].rstrip())
        remaining = remaining[end:].lstrip()
    return lines or ['']


def _text(snapshot, element, price_parts):
    if element.field in ('title', 'text'):
        value = element.text
    elif element.field == 'price':
        value = ' '.join(part for part in price_parts if part)
    else:
        value = str(snapshot.get(element.field) or ('' if element.field == 'barcode' else '-'))
    value = ' '.join(value.split())
    return value.upper() if element.uppercase else value


def _draw_text(image, snapshot, element, price_parts):
    value = _text(snapshot, element, price_parts)
    if not value:
        return
    box = Image.new('1', (element.width, element.height), 1)
    draw = ImageDraw.Draw(box)
    stroke = 1 if element.bold and element.font == 'barlow' else 0
    width = element.width - stroke * 2
    for size in range(element.font_size, 9, -1):
        font = _font(element.font, size, element.bold)
        lines = _wrap(draw, value, font, width)
        ink_height = max(draw.textbbox((0, 0), line or 'Ag', font=font)[3] -
                         draw.textbbox((0, 0), line or 'Ag', font=font)[1] for line in lines)
        line_height = ink_height + 2 + stroke * 2
        if len(lines) <= element.lines and len(lines) * line_height - 2 <= element.height:
            break
    available = min(element.lines, max(1, (element.height + 2) // line_height))
    if element.field == 'code':
        # Manual fallback identity is never abbreviated, wrapped or replaced.
        if len(lines) != 1 or ink_height + stroke * 2 > element.height:
            raise ValueError('Aumente o espaço reservado para o código interno.')
    elif len(lines) > available:
        lines = lines[:available]
        last = lines[-1]
        while last and draw.textlength(last + '...', font=font) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + '...'
    for index, line in enumerate(lines):
        line_width = draw.textlength(line, font=font)
        x = (element.width - line_width) / 2 if element.align == 'center' else (
            element.width - line_width - stroke if element.align == 'right' else stroke)
        bounds = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        draw.text((round(x), index * line_height - bounds[1]), line, font=font,
                  fill=0, stroke_width=stroke, stroke_fill=0)
    image.paste(box, (element.x, element.y))


def bitmap(snapshot, price_parts):
    config = LabelDesign.model_validate(snapshot['layout_config'])
    image = Image.new('1', (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(image)
    for element in config.elements:
        if element.type == 'qr':
            qr = QrCodeWidget(snapshot['code'], barLevel='M', qrVersion=3)
            qr.qr.make()
            size = element.module_size
            for row, bits in enumerate(qr.qr.modules):
                for col, dark in enumerate(bits):
                    if dark:
                        x, y = element.x + (col + 4) * size, element.y + (row + 4) * size
                        draw.rectangle((x, y, x + size - 1, y + size - 1), fill=0)
        elif element.visible:
            if element.type == 'text':
                _draw_text(image, snapshot, element, price_parts)
            else:
                w, h = element_size(element)
                draw.rectangle((element.x, element.y, element.x + w - 1, element.y + h - 1), fill=0)
    return image
