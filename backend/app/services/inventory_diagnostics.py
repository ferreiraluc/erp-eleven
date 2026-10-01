"""SQL-backed read-only checks, without fetching images or modifying stock."""
from sqlalchemy import BigInteger, and_, case, cast, func, or_, select

from ..config import settings
from ..models.inventory import Item


def barcode_key(column):
    # Keep case, punctuation and leading zeros: Code 128 is not necessarily a GTIN.
    value = func.coalesce(column, '')
    for whitespace in (' ', '\t', '\r', '\n', '\u00a0'):
        value = func.replace(value, whitespace, '')
    return value


def diagnose_inventory(db, *, issue='all', q='', page=1, page_size=25):
    keys = ('negative_stock', 'missing_stock', 'stock_mismatch', 'duplicate_barcode')
    if issue not in ('all', *keys) or not 1 <= page_size <= 100 or page < 1:
        raise ValueError('Invalid diagnostic filter')
    expected = cast(Item.stock_loja, BigInteger) + cast(Item.stock_deposito, BigInteger)
    base = select(
        Item.id, Item.name, Item.sku_internal, Item.barcode, Item.brand, Item.size,
        Item.color, Item.current_stock, Item.stock_loja, Item.stock_deposito,
        barcode_key(Item.barcode).label('normalized_barcode'),
        expected.label('expected_stock'),
        (cast(Item.current_stock, BigInteger) - expected).label('delta'),
        or_(Item.current_stock.is_(None), Item.stock_loja.is_(None), Item.stock_deposito.is_(None)).label('missing_stock'),
        func.coalesce(or_(Item.current_stock < 0, Item.stock_loja < 0, Item.stock_deposito < 0), False).label('negative_stock'),
        func.coalesce(Item.current_stock != expected, False).label('stock_mismatch'),
    ).where(Item.is_active.is_(True)).cte('active_inventory')
    duplicates = select(
        base.c.normalized_barcode, func.count().label('duplicate_count'),
    ).where(base.c.normalized_barcode != '').group_by(base.c.normalized_barcode).having(func.count() > 1).cte('duplicate_codes')
    findings = select(
        base, func.coalesce(duplicates.c.duplicate_count, 0).label('duplicate_count'),
        duplicates.c.duplicate_count.is_not(None).label('duplicate_barcode'),
    ).select_from(base.outerjoin(duplicates, base.c.normalized_barcode == duplicates.c.normalized_barcode)).cte('inventory_findings')
    affected = or_(*(findings.c[key] for key in keys))
    aggregate = db.execute(select(
        func.count().label('total_active_items'),
        func.coalesce(func.sum(case((affected, 1), else_=0)), 0).label('affected_items'),
        *(func.coalesce(func.sum(case((findings.c[key], 1), else_=0)), 0).label(key) for key in keys),
    ).select_from(findings)).mappings().one()
    group_count = db.execute(select(func.count()).select_from(duplicates)).scalar_one()
    filters = [affected if issue == 'all' else findings.c[issue]]
    search = q.strip()
    if search:
        # Literal substring, not a user-controlled SQL wildcard expression.
        escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        pattern = '%' + escaped + '%'
        filters.append(or_(*(findings.c[key].ilike(pattern, escape='\\') for key in
                             ('name', 'sku_internal', 'barcode', 'normalized_barcode', 'brand'))))
    matching = and_(*filters)
    total = db.execute(select(func.count()).select_from(findings).where(matching)).scalar_one()
    rows = db.execute(select(findings).where(matching).order_by(
        findings.c.negative_stock.desc(), findings.c.missing_stock.desc(),
        findings.c.stock_mismatch.desc(), func.lower(findings.c.name), findings.c.id,
    ).offset((page - 1) * page_size).limit(page_size)).mappings()
    items = []
    for result in rows:
        row = dict(result)
        row['issues'] = [key for key in keys if row.pop(key)]
        items.append(row)
    return {
        'checked_at': settings.now(), 'total_active_items': aggregate['total_active_items'],
        'affected_items': aggregate['affected_items'],
        'counts': {**{key: aggregate[key] for key in keys}, 'duplicate_barcode_groups': group_count},
        'total_items': total, 'page': page, 'page_size': page_size, 'items': items,
    }
