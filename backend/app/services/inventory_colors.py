"""Color aliases for comparison only; keep the operator's saved shade/name."""
import re
from .inventory_taxonomy_v1 import text_key

# Shades stay distinct: navy is not plain blue, off-white is not white.
GROUPS = {
    'preto': ('preto', 'preta', 'black', 'negro', 'negra'),
    'branco': ('branco', 'branca', 'white', 'blanco', 'blanca'),
    'azul': ('azul', 'blue'),
    'marinho': ('azul marinho', 'azulmarinho', 'navy blue', 'navy', 'azul marino', 'marino', 'marinho'),
    'cinza': ('cinza', 'grey', 'gray', 'gris'),
    'bege': ('bege', 'beige'),
    'marrom': ('marrom', 'brown', 'marron', 'cafe'),
    'verde': ('verde', 'green'),
    'vermelho': ('vermelho', 'vermelha', 'red', 'rojo', 'roja'),
    'amarelo': ('amarelo', 'amarela', 'yellow', 'amarillo', 'amarilla'),
    'rosa': ('rosa', 'pink', 'rosado', 'rosada'),
    'roxo': ('roxo', 'roxa', 'purple', 'morado', 'morada', 'violeta'),
    'laranja': ('laranja', 'orange', 'naranja'),
    'dourado': ('dourado', 'dourada', 'gold', 'golden', 'dorado', 'dorada'),
    'prata': ('prata', 'silver', 'plateado', 'plateada'),
    'offwhite': ('off white', 'off-white', 'offwhite'),
    'multicolor': ('multicolor', 'multicolour', 'multicolorido', 'multicolorida'),
}
ALIASES = {alias: canonical for canonical, aliases in GROUPS.items() for alias in aliases}
PATTERN = re.compile(r'(?<!\w)(' + '|'.join(re.escape(a) for a in sorted(ALIASES, key=len, reverse=True)) + r')(?!\w)')


def color_terms(value):
    return PATTERN.sub(lambda match: ALIASES[match[0]], text_key(value))


def color_key(value):
    # A composition remains a composition; order/separators don't create colors.
    parts = re.split(r'\s*(?:[+/,;&]|\b(?:e|y|and)\b)\s*', color_terms(value))
    return ' + '.join(sorted(set(part.strip() for part in parts if part.strip())))


def color_search_text(value):
    """Search a shade by its aliases without translating product/brand words."""
    canonical = color_key(value)
    aliases = [alias for color, values in GROUPS.items()
               if re.search(r'(?<!\w)' + color + r'(?!\w)', canonical)
               for alias in values]
    return ' '.join([canonical, text_key(value), *aliases])
