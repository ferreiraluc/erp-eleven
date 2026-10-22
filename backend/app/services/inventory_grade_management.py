"""Explicit inventory grade membership and bounded, read-only model suggestions.

A shared barcode is never evidence of a shared product model. Suggestions compare
the full model name (removing only the item's own size suffix) and its facets;
only an authenticated manager's separate write changes ``group_key``.
"""
import hashlib

from fastapi import HTTPException
from sqlalchemy import func, or_, text
from sqlalchemy.orm import defer

from ..models.inventory import Item
from ..services.inventory_images import catalog_query, catalog_response
from ..services.inventory_search import normalizer, text_key as search_key
from ..services.inventory_taxonomy import canonical_size, key as facet_key

LEGACY_NAME_SIZES = frozenset({'P', 'S', 'M', 'G', 'L', 'GG', 'XL', 'XXL'})


def display_model_name(name: str | None, size: str | None) -> str:
    """Mirror the UI title: remove only the exact size stored on this item."""
    clean = ' '.join((name or '').split())
    suffix = f' {size.strip()}' if size and size.strip() else ''
    if suffix and len(clean) > len(suffix) and clean.casefold().endswith(suffix.casefold()):
        return clean[:-len(suffix)]
    return clean


def model_name(name: str | None, size: str | None, color: str | None) -> str:
    """Compare variants across colors without erasing a model's numeric code."""
    clean = ' '.join((name or '').split())
    # Either "Modelo Azul M" or "Modelo M Azul" occurs in historical rows.
    # Strip only whole suffixes backed by the item's own structured fields.
    for _ in range(2):
        for value in (size, color):
            suffix = f' {value.strip()}' if value and value.strip() else ''
            if suffix and len(clean) > len(suffix) and clean.casefold().endswith(suffix.casefold()):
                clean = clean[:-len(suffix)].rstrip()
    if not size:
        # Old rows may carry shirt sizes only in the name. Numeric suffixes
        # stay untouched: they are frequently the distinguishing model code.
        stem, separator, suffix = clean.rpartition(' ')
        if separator and suffix.upper() in LEGACY_NAME_SIZES:
            clean = stem
    return clean


def same_model(source, other) -> bool:
    if search_key(model_name(source.name, source.size, source.color)) != search_key(
            model_name(other.name, other.size, other.color)):
        return False
    return (facet_key(source.brand, 'brand') == facet_key(other.brand, 'brand')
            and facet_key(source.category, 'category') == facet_key(other.category, 'category')
            and search_key(source.unit) == search_key(other.unit))


def variant_identity(size: str | None, color: str | None) -> tuple[str, str]:
    return (canonical_size(size or '').casefold(), facet_key(color, 'color'))


def _escape_like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _base_prefix(db, source):
    base = search_key(model_name(source.name, source.size, source.color))
    if len(base) < 3:
        return None
    # This expression is the existing indexed catalog-search normalizer.
    return normalizer(db)(Item.name).like(_escape_like(base) + '%', escape='\\')


def _candidates(query, source, cap):
    """Prioritize exact facets without sorting a broad model-name prefix.

    The second, bounded query admits taxonomy aliases. The picker is advisory;
    manual directory/search remains available beyond these finite samples.
    """
    exact = query.filter(Item.brand == source.brand,
                         Item.category == source.category,
                         Item.unit == source.unit).limit(cap).all()
    fallback = query.limit(cap).all()
    return list({(row.id if isinstance(row, Item) else row[0].id): row
                 for row in [*exact, *fallback]}.values())


def _representatives(db, keys):
    if not keys:
        return {}
    ranked = db.query(
        Item.group_key.label('group_key'), Item.name.label('name'),
        Item.size.label('size'), Item.color.label('color'), Item.created_at.label('created_at'),
        func.row_number().over(partition_by=Item.group_key,
                               order_by=(Item.created_at, Item.id)).label('rank'),
    ).filter(Item.deleted_at.is_(None), Item.is_active.is_(True), Item.group_key.in_(keys)).subquery()
    return {row.group_key: row for row in db.query(ranked).filter(ranked.c.rank == 1).all()}


def _summaries(db, keys):
    if not keys:
        return []
    counts = dict(db.query(Item.group_key, func.count(Item.id)).filter(
        Item.deleted_at.is_(None), Item.is_active.is_(True),
        Item.group_key.in_(keys)).group_by(Item.group_key).all())
    representatives = _representatives(db, keys)
    colors = {}
    for group_key, color in db.query(Item.group_key, Item.color).filter(
            Item.deleted_at.is_(None), Item.is_active.is_(True), Item.group_key.in_(keys)).distinct().all():
        if color and color.strip():
            colors.setdefault(group_key, set()).add(color.strip().casefold())
    summaries = []
    for key in keys:
        source = representatives.get(key)
        if source is None:
            continue
        # Human-authored labels remain authoritative; automatic UUID keys use
        # the oldest member's model name, just like the inventory UI.
        import re
        automatic = re.fullmatch(
            r'(?:grade-)?(?:[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}|[\da-f]{32})',
            key.strip(), re.I)
        title = display_model_name(source.name, source.size)
        multicolor = len(colors.get(key, set())) > 1
        base = model_name(source.name, source.size, source.color)
        generated_color_key = (multicolor and any(
            key.strip().casefold() == f'{base} {color}'.casefold()
            for color in colors.get(key, set())))
        summaries.append({'group_key': key,
                          'display_name': (base if multicolor else title) if automatic else
                                          base if generated_color_key else key,
                          'member_count': counts[key]})
    return summaries


def group_directory(db, search: str = '', limit: int = 20):
    # DISTINCT on the existing group_key B-tree can stop after `limit` when no
    # term was entered; opening the picker must not aggregate the full catalog.
    query = db.query(Item.group_key).filter(
        Item.deleted_at.is_(None), Item.is_active.is_(True),
        Item.group_key.isnot(None), Item.group_key != '')
    term = search_key(search.strip())
    if term:
        pattern = f'%{_escape_like(term)}%'
        normalize = normalizer(db)
        query = query.filter(or_(normalize(Item.name).like(pattern, escape='\\'),
                                 normalize(Item.group_key).like(pattern, escape='\\')))
    keys = [row.group_key for row in query.distinct()
            .order_by(Item.group_key).limit(limit).all()]
    return {'groups': _summaries(db, keys)}


def item_grade_suggestions(db, item_id, limit: int = 8):
    source = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.id == item_id, Item.deleted_at.is_(None)).first()
    if source is None:
        raise HTTPException(404, 'Produto não encontrado.')
    prefix = _base_prefix(db, source)
    if prefix is None:
        return {'groups': []}
    # Limit DB/Python work even when thousands of unrelated products share a
    # prefix. Directory search remains available for a manually chosen grade.
    rows = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.deleted_at.is_(None), Item.is_active.is_(True),
        Item.group_key.isnot(None), Item.group_key != '', prefix)
    if source.group_key:
        rows = rows.filter(Item.group_key != source.group_key)
    candidates = _candidates(rows, source, max(200, limit * 50))
    keys = list(dict.fromkeys(row.group_key for row in candidates if same_model(source, row)))[:max(20, limit * 3)]
    if keys:
        wanted = variant_identity(source.size, source.color)
        occupied = {row.group_key for row in db.query(Item.group_key, Item.size, Item.color).filter(
            Item.deleted_at.is_(None), Item.group_key.in_(keys)).all()
            if variant_identity(row.size, row.color) == wanted}
        keys = [key for key in keys if key not in occupied][:limit]
    return {'groups': [dict(group, match_reason='Mesmo modelo, marca, categoria e unidade')
                       for group in _summaries(db, keys)]}


def ungrouped_grade_suggestions(db, group_key: str, limit: int = 12):
    source = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.deleted_at.is_(None), Item.is_active.is_(True), Item.group_key == group_key,
    ).order_by(Item.created_at, Item.id).first()
    if source is None:
        raise HTTPException(404, 'Grade não encontrada.')
    prefix = _base_prefix(db, source)
    if prefix is None:
        return {'items': []}
    occupied = {variant_identity(row.size, row.color)
                for row in db.query(Item.size, Item.color).filter(
                    Item.group_key == group_key, Item.deleted_at.is_(None)).all()}
    rows = catalog_query(db.query(Item).filter(
        Item.deleted_at.is_(None), Item.is_active.is_(True),
        or_(Item.group_key.is_(None), Item.group_key == ''), prefix), False)
    candidates = _candidates(rows, source, max(200, limit * 50))
    return {'items': [catalog_response(item, has_image, False)
                      for item, has_image in candidates
                      if same_model(source, item) and variant_identity(item.size, item.color) not in occupied][:limit]}


def grade_members(db, group_key: str, page: int = 1, limit: int = 100):
    """The full grade, independent of receiving-lot/search filters, without photos."""
    base = db.query(Item).filter(Item.group_key == group_key, Item.deleted_at.is_(None),
                                 Item.is_active.is_(True))
    total = base.count()
    if not total:
        raise HTTPException(404, 'Grade não encontrada.')
    rows = catalog_query(base, False).order_by(Item.created_at, Item.id).offset(
        (page - 1) * limit).limit(limit).all()
    return {'items': [catalog_response(item, has_image, False) for item, has_image in rows],
            'total': total, 'page': page, 'limit': limit}


def lock_grade(db, group_key: str | None):
    """Serialize writes with ``create_variants`` on PostgreSQL; no-op on SQLite."""
    if group_key and db.bind.dialect.name == 'postgresql':
        lock = int.from_bytes(hashlib.sha256(f'inventory-variants:{group_key}'.encode()).digest()[:8],
                              'big', signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})


def attach_existing_grade(db, item_id, group_key: str, expected_group_key: str | None):
    # A pre-read is only to determine which grade locks to acquire. Re-read the
    # item under its row lock afterwards to reject stale concurrent requests.
    source_key = (db.query(Item.group_key).filter(Item.id == item_id,
        Item.deleted_at.is_(None)).scalar() or None)
    for key in sorted({key for key in (source_key, group_key) if key}):
        lock_grade(db, key)
    item = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.id == item_id, Item.deleted_at.is_(None)).with_for_update().populate_existing().first()
    if item is None:
        raise HTTPException(404, 'Produto não encontrado.')
    if not item.is_active:
        raise HTTPException(409, 'Ative o produto antes de vinculá-lo a uma grade.')
    if item.group_key == group_key:
        return {'item_id': item.id, 'group_key': group_key,
                'previous_group_key': group_key}
    # Historical rows can store an empty string for "no grade". Treat it as
    # ungrouped when comparing the client's explicit null precondition.
    current_key = item.group_key or None
    if current_key != source_key or current_key != expected_group_key:
        raise HTTPException(409, 'A grade do produto mudou. Atualize a listagem e tente novamente.')

    members = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.group_key == group_key, Item.deleted_at.is_(None)
    ).order_by(Item.id).with_for_update().all()
    if not any(row.is_active for row in members):
        raise HTTPException(404, 'Grade de destino não encontrada.')
    wanted = variant_identity(item.size, item.color)
    if any(variant_identity(row.size, row.color) == wanted for row in members):
        raise HTTPException(409, 'A grade já contém esta combinação de tamanho e cor.')
    previous = current_key
    item.group_key = group_key
    db.commit()
    return {'item_id': item.id, 'group_key': group_key,
            'previous_group_key': previous}


def detach_grade(db, item_id, expected_group_key: str | None = None):
    source_key = db.query(Item.group_key).filter(Item.id == item_id,
        Item.deleted_at.is_(None)).scalar()
    lock_grade(db, source_key)
    item = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.id == item_id, Item.deleted_at.is_(None)).with_for_update().populate_existing().first()
    if item is None:
        raise HTTPException(404, 'Produto não encontrado.')
    if expected_group_key is not None and item.group_key != expected_group_key:
        raise HTTPException(409, 'A grade do produto mudou. Atualize a listagem e tente novamente.')
    if item.group_key != source_key:
        raise HTTPException(409, 'A grade do produto mudou. Atualize a listagem e tente novamente.')
    if not item.group_key:
        raise HTTPException(400, 'Produto não pertence a nenhuma grade.')
    previous = item.group_key
    item.group_key = None
    db.commit()
    return {'item_id': item.id, 'group_key': None,
            'previous_group_key': previous}
