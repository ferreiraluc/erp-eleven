"""Five monochrome A4 presentations. Rotation is resolved once, before confirmation."""
import hashlib
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

TEMPLATES = {
    'classic': 'Clássico',
    'table': 'Tabela',
    'cards': 'Blocos',
    'columns': 'Colunas',
    'compact': 'Ficha compacta',
}


def select_layout(config, request_key):
    result = dict(config)
    if result.get('rotate_templates', True):
        seed = hashlib.sha256(str(request_key).encode()).digest()
        result['template'] = list(TEMPLATES)[int.from_bytes(seed[:4], 'big') % len(TEMPLATES)]
    result['rotate_templates'] = False  # An immutable snapshot, never re-roll on render/retry.
    return result


def presentation(layout, fields, sender, width):
    """Keep sender lines verbatim; never infer missing identity/address fields."""
    narrow = layout.template in ('table', 'columns') and sender
    font_size = min(layout.font_size, 15) if narrow else layout.font_size
    body = ParagraphStyle('layout_body', fontName='Helvetica-Bold' if layout.bold else 'Helvetica',
                          fontSize=font_size, leading=font_size + 4, wordWrap='LTR')
    small = ParagraphStyle('layout_sender', fontName='Helvetica',
                           fontSize=min(layout.sender_font_size, 14) if narrow else layout.sender_font_size,
                           leading=min(layout.sender_font_size, 14) + 4 if narrow else layout.sender_font_size + 4)
    heading = ParagraphStyle('layout_heading', fontName='Helvetica-Bold', fontSize=11, leading=15)
    labels = {'nome': 'NOME', 'endereco': 'ENDEREÇO', 'cidade': 'CIDADE / UF',
              'cep': 'CEP', 'pais': 'PAÍS', 'telefone': 'TELEFONE', 'cpf': 'DOCUMENTO'}
    def para(text, style=body):
        return Paragraph(escape(text).replace('\n', '<br/>'), style)
    recipient = [para(fields[key]) for key in layout.fields if fields[key]]
    send = [para(line, small) for line in (sender or {}).get('linhas', []) if line]
    base = [('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]
    def table(rows, widths, extra=()):
        return Table(rows, colWidths=widths, style=TableStyle(base + list(extra)), hAlign='LEFT')
    border = [('BOX', (0, 0), (-1, -1), 1, colors.black)]
    if layout.template == 'table':
        left = [para('REMETENTE', heading), *send] if sender else []
        right = [para(layout.title, heading), *recipient]
        rows = [[left[i] if i < len(left) else '', right[i] if i < len(right) else '']
                for i in range(max(len(left), len(right)))] if sender else [[cell] for cell in right]
        return [table(rows, [width / 2] * 2 if sender else [width],
                      [('GRID', (0, 0), (-1, -1), .8, colors.black),
                       ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee'))])]
    if layout.template == 'columns':
        cells = [[para('REMETENTE', heading), *send], [para(layout.title, heading), *recipient]] if sender else [[para(layout.title, heading), *recipient]]
        return [table([cells], [width * .42, width * .58] if sender else [width],
                      [('LINEBEFORE', (-1, 0), (-1, -1), 2, colors.black),
                       ('LINEABOVE', (0, 0), (-1, 0), 1, colors.black)])]
    if layout.template == 'cards':
        story = [table([[[para(layout.title, heading), Spacer(1, 8), *recipient]]], [width], border)]
        if sender:
            story += [Spacer(1, layout.sender_gap), table([[[para('REMETENTE', heading), Spacer(1, 6), *send]]], [width], border)]
        return story
    # Compact form: field names in a small left column, content in the right.
    rows = [[para(labels[key], heading), para(fields[key])] for key in layout.fields if fields[key]]
    story = [para(layout.title, heading), Spacer(1, 10)]
    if rows:
        story.append(table(rows, [108, width - 108], [('LINEBELOW', (0, 0), (-1, -1), .4, colors.HexColor('#999999'))]))
    if sender:
        story += [Spacer(1, layout.sender_gap), para('REMETENTE', heading), Spacer(1, 6), *send]
    return story
