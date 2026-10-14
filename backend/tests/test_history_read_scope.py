"""Synthetic cross-module history checks never connect to operational data."""
from datetime import datetime, timezone
import uuid

import pytest

from test_assistant import setup
from test_inventory_ocr import stock_app
from test_inventory_history import history_app, sale, get
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.inventory import Item
from app.services.inventory_service import create_movement


@pytest.mark.parametrize(('identity', 'scope', 'owner', 'expected_sales'), [
    ('denis', 'own', False, 1),
    ('wissam', 'all', False, 2),
    ('lucas', 'all', True, 4),
])
@pytest.mark.parametrize('section', ['sales', 'movements'])
def test_deleted_sales_are_owner_only_in_product_history_and_movement_details(
    history_app, identity, scope, owner, expected_sales, section,
):
    factory, client, uid, rid = history_app
    with factory() as db:
        user = db.get(Usuario, uid)
        user.email = f'{identity}@eleven.com'; user.sales_scope = scope
        user.role = UsuarioRole.ADMIN if owner else UsuarioRole.GERENTE
        other = Usuario(nome='Colega sintético', email='other@example.test', senha_hash='unused')
        db.add(other); db.flush()
        row = db.get(Item, rid)
        visible = sale(db, row, uid)
        visible_other = sale(db, row, other.id)
        hidden = sale(db, row, uid)
        hidden_other = sale(db, row, other.id)
        deleted_ids = {str(hidden.id), str(hidden_other.id)}
        for archived in (hidden, hidden_other):
            archived.deleted_at = datetime(2026, 10, 14, tzinfo=timezone.utc)
        create_movement(db, rid, 'exit', 1, uid, reference_type='pdv_sale',
                        reference_id=str(hidden.id), reason='Venda excluída privada', notes='valor privado')
        create_movement(db, rid, 'entry', 1, other.id, reference_type='pdv_sale',
                        reference_id=str(hidden_other.id), reason='Venda excluída privada', notes='valor privado')
        expected_ids = {str(visible.id)}
        if scope == 'all': expected_ids.add(str(visible_other.id))
        if owner: expected_ids |= deleted_ids
        db.commit()
    if section == 'sales':
        found = set()
        for number in range(1, expected_sales + 1):
            result = get(client, rid, 'sales', page=number, page_size=1)
            assert result['total'] == result['totals']['sales'] == expected_sales
            found.update(row['id'] for row in result['rows'])
        assert found == expected_ids
        return
    movements = get(client, rid)
    assert movements['total'] == 2 and movements['product']['current_stock'] == 2
    assert {row['quantity'] for row in movements['rows']} == {1}
    assert {(row['before'], row['after']) for row in movements['rows']} == {(2, 1), (1, 2)}
    for movement in movements['rows']:
        assert movement['restricted'] is not owner
        if owner:
            assert movement['reference_id'] in deleted_ids
            assert movement['reason'] == 'Venda excluída privada'
        else:
            assert all(movement[key] is None for key in ('reference_id', 'actor', 'reason', 'notes'))


def test_legacy_reference_formats_keep_visible_sale_metadata_and_original_reference(history_app):
    factory, client, uid, rid = history_app
    with factory() as db:
        user = db.get(Usuario, uid)
        user.email = 'wissam@eleven.com'; user.sales_scope = 'all'; user.role = UsuarioRole.GERENTE
        visible = sale(db, db.get(Item, rid), uid)
        allowed = {visible.id.hex, str(visible.id).upper()}
        unavailable = {'invalid-reference', uuid.uuid4().hex}
        movement_ids = {}
        for reference in allowed | unavailable:
            row = create_movement(db, rid, 'entry', 1, uid, reference_type='pdv_sale',
                                  reference_id=reference, reason='Motivo sintético', notes='Nota sintética')
            db.flush(); movement_ids[str(row.id)] = reference
        db.commit()
    for movement in get(client, rid)['rows']:
        original = movement_ids[movement['id']]
        assert movement['quantity'] == 1
        if original in allowed:
            assert not movement['restricted']
            assert movement['reference_id'] == original
            assert movement['reason'] == 'Motivo sintético' and movement['notes'] == 'Nota sintética'
            assert movement['actor'] is not None
        else:
            assert movement['restricted']
            assert all(movement[key] is None for key in ('reference_id', 'actor', 'reason', 'notes'))
