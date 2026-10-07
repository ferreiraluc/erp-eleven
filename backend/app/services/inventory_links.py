"""Exact product links shared by history and deletion; barcodes are not identity."""
from sqlalchemy import and_, or_
from ..models.pdv import PdvSaleItem


def product_sale_link(item):
    return or_(PdvSaleItem.item_id == item.id,
               and_(PdvSaleItem.item_id.is_(None), PdvSaleItem.item_sku == item.sku_internal))
