"""Reuse reviewed label examples through the same brand aliases as the catalog."""
from sqlalchemy import func

from ..models.label_template import LabelTemplate
from .inventory_taxonomy import key, vocabulary

MAX_TEMPLATE_CANDIDATES = 12
MAX_READING_EXAMPLES = 3


def brand_counts(db):
    # Read only the small vocabulary, never the saved photos for a selector.
    rows = db.query(LabelTemplate.brand, func.count(LabelTemplate.id)).filter(
        LabelTemplate.is_active.is_(True),
    ).group_by(LabelTemplate.brand).all()
    labels = vocabulary([brand for brand, _ in rows], 'brand')
    counts = {}
    for brand, count in rows:
        identity = key(brand, 'brand')
        if identity:
            counts[identity] = counts.get(identity, 0) + count
    return [{'brand': labels[identity], 'count': counts[identity]}
            for identity in sorted(counts)]


def matching_brands(db, brand):
    wanted = key(brand, 'brand')
    if not wanted:
        return []
    # Match identities, never SQL wildcards or substring/fuzzy matches to another brand.
    rows = db.query(LabelTemplate.brand).filter(LabelTemplate.is_active.is_(True)).distinct()
    return [raw for (raw,) in rows if key(raw, 'brand') == wanted]


def reading_examples(db, brand):
    if not brand:
        return ()
    return db.query(LabelTemplate).filter(
        LabelTemplate.is_active.is_(True),
        LabelTemplate.brand.in_(matching_brands(db, brand)),
    ).order_by(LabelTemplate.created_at.desc(), LabelTemplate.id.desc()).limit(
        MAX_TEMPLATE_CANDIDATES,
    ).yield_per(1)
