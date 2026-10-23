"""Raster artwork shared by the Zebra RAW job and the browser preview.

The ZD220 resident ^A0 font is bold and condensed, so it cannot reproduce the
Arial/Bahnschrift lettering in the supplied ZebraDesigner label. Rendering the
whole 60 × 30 mm label once also prevents preview/print font drift.
"""
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.barcode.qr import QrCodeWidget


WIDTH, HEIGHT = 480, 240  # 60 × 30 mm at the ZD220's 203 dpi
FONT_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'
TEXT_FONT = FONT_DIR / 'Arimo.ttf'
TITLE_FONT = FONT_DIR / 'BarlowSemiCondensed-SemiBold.ttf'


@lru_cache(maxsize=32)
def _font(path, size):
    return ImageFont.truetype(str(path), size)


@lru_cache(maxsize=4)
def _title_font_v4():
    font = ImageFont.truetype(str(TEXT_FONT), 38)
    font.set_variation_by_name('Bold')
    return font


def _fit(draw, value, max_width, sizes=(16, 14, 12)):
    text = ' '.join(str(value or '').split()).upper() or '-'
    for size in sizes:
        font = _font(TEXT_FONT, size)
        if draw.textlength(text, font=font) <= max_width:
            return text, font
    font = _font(TEXT_FONT, sizes[-1])
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if draw.textlength(text[:middle] + '...', font=font) <= max_width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + '...', font


def _draw_centered_ink(draw, x, middle_y, value, font):
    # ZebraDesigner anchors its text objects by the middle-left of the glyph.
    bounds = draw.textbbox((0, 0), value, font=font)
    y = round(middle_y - (bounds[3] - bounds[1]) / 2 - bounds[1])
    draw.text((x, y), value, font=font, fill=0)


def _bitmap_v3(snapshot, price_parts):
    """Keep queued v3 artwork byte-for-byte stable for its recorded SHA-256."""
    image = Image.new('1', (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(image)
    _draw_centered_ink(draw, 159, 24, 'ELEVEN', _font(TITLE_FONT, 36))
    for y, key in ((68, 'name'), (87, 'size'), (113, 'color'), (134, 'code')):
        value, font = _fit(draw, snapshot.get(key), 292)
        _draw_centered_ink(draw, 28, y, value, font)

    # The QR contains only the unique internal code. Its 4-dot modules give a
    # footprint close to the original ZebraDesigner symbol for this short value.
    qr = QrCodeWidget(snapshot['code'], barLevel='M')
    qr.qr.make()
    modules = qr.qr.modules
    if len(modules) != 21:
        raise ValueError('Unexpected internal-code QR size')
    module_size = 4
    active_x, active_y = 359, 73  # 343,57 with a 4-module quiet zone
    for row, bits in enumerate(modules):
        for col, dark in enumerate(bits):
            if dark:
                x = active_x + col * module_size
                y = active_y + row * module_size
                draw.rectangle((x, y, x + module_size - 1, y + module_size - 1), fill=0)

    symbol, amount = price_parts
    if symbol:
        _draw_centered_ink(draw, 28, 204, symbol, _font(TEXT_FONT, 22))
    amount_x = 28 + (34 if len(symbol) > 1 else 15 if symbol else 0)
    _draw_centered_ink(draw, amount_x, 202, amount, _font(TEXT_FONT, 27))
    barcode = ' '.join(str(snapshot.get('barcode') or '').split())
    if barcode:
        value, font = _fit(draw, barcode, 145, (14, 12, 10))
        _draw_centered_ink(draw, 324, 209, value, font)
    return image


def _bitmap_v4(snapshot, price_parts):
    """Match the physically printed 60 × 30 mm ZebraDesigner reference."""
    image = Image.new('1', (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(image)
    # The reference has a broad, bold 149 × 27-dot wordmark, centered on paper.
    title_font = _title_font_v4()
    title_bounds = draw.textbbox((0, 0), 'ELEVEN', font=title_font, stroke_width=1)
    title_y = round(35 - (title_bounds[3] - title_bounds[1]) / 2 - title_bounds[1])
    draw.text((165, title_y), 'ELEVEN', font=title_font, fill=0,
              stroke_width=1, stroke_fill=0)
    for y, key in ((68, 'name'), (95, 'size'), (120, 'color'), (151, 'code')):
        value, font = _fit(draw, snapshot.get(key), 292)
        _draw_centered_ink(draw, 32, y, value, font)

    # The template's QR is denser than the short-code auto-selected v1 symbol.
    # A fixed v3 matrix keeps the internal code alone in an 87-dot square.
    qr = QrCodeWidget(snapshot['code'], barLevel='M', qrVersion=3)
    qr.qr.make()
    modules = qr.qr.modules
    if len(modules) != 29:
        raise ValueError('Unexpected internal-code QR size')
    module_size = 3
    active_x, active_y = 348, 63
    for row, bits in enumerate(modules):
        for col, dark in enumerate(bits):
            if dark:
                x = active_x + col * module_size
                y = active_y + row * module_size
                draw.rectangle((x, y, x + module_size - 1, y + module_size - 1), fill=0)

    symbol, amount = price_parts
    if symbol:
        _draw_centered_ink(draw, 32, 204, symbol, _font(TEXT_FONT, 22))
    amount_x = 32 + (34 if len(symbol) > 1 else 15 if symbol else 0)
    _draw_centered_ink(draw, amount_x, 202, amount, _font(TEXT_FONT, 27))
    barcode = ' '.join(str(snapshot.get('barcode') or '').split())
    if barcode:
        value, font = _fit(draw, barcode, 145, (14, 12, 10))
        _draw_centered_ink(draw, 324, 209, value, font)
    return image


def bitmap(snapshot, price_parts):
    """Return exactly the 1-bit image that will be sent as ^GFA to the printer."""
    if snapshot.get('layout_version') == 5:
        from .product_label_design_artwork import bitmap as design_bitmap
        return design_bitmap(snapshot, price_parts)
    if snapshot.get('layout_version') == 4:
        return _bitmap_v4(snapshot, price_parts)
    return _bitmap_v3(snapshot, price_parts)


def zpl(snapshot, price_parts):
    image = bitmap(snapshot, price_parts)
    # Pillow stores white pixels as 1; ^GFA expects a set bit for a black dot.
    graphic = bytes(pixel ^ 0xFF for pixel in image.tobytes())
    assert len(graphic) == HEIGHT * (WIDTH // 8)
    parts = [
        '^XA^CI28^MNY^MMT^PW480^LL240^LH0,0^LS0^LT0^PON',
        f'^FO0,0^GFA,{len(graphic)},{len(graphic)},{WIDTH // 8},{graphic.hex().upper()}^FS',
        f"^PQ{snapshot['copies']},0,1,N^XZ",
    ]
    return '\n'.join(parts).encode('ascii')


def preview_png(snapshot, price_parts):
    image = bitmap(snapshot, price_parts)
    png = io.BytesIO()
    image.save(png, format='PNG')
    return png.getvalue()
