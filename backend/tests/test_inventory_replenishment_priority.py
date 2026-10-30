"""Replenishment priority follows store movements, not product metadata edits."""
from datetime import datetime, timedelta
import uuid

import pytest
from sqlalchemy import update

from app.models.inventory import Item, MovementType, StockMovement
from app.models.printing import PrintJob
from app.models.usuario import Usuario
from app.services.inventory_service import create_movement
from test_inventory_replenishment import (
    URL, replenishment_env, label_env, tickets, pdv_app,
    request_body, setup_device, confirm,
)
from test_pdv_unknown_stock import make_item
from test_inventory_replenishment_postgres import replenishment_pg, pdv_pg, pg


BASE = datetime(2026, 10, 20, 10, 30)
_UNSET = object()


@pytest.fixture
def priority_env(replenishment_env):
    factory, client, _ = replenishment_env
    with factory() as db:
        db.execute(update(Item).values(is_active=False))
        db.commit()
    return factory, client


def product(db, name, **balances):
    row = make_item(db, **(dict(current_stock=5, stock_loja=0, stock_deposito=5) | balances))
    row.name = name
    db.flush()
    return row


def movement(db, item_id, *, kind='exit', quantity=1, before=6, after=5,
             location_from='loja', location_to=None, at=BASE, reason='Fixture sintética',
             stock_loja_before=_UNSET, stock_loja_after=_UNSET):
    values = dict(item_id=item_id, movement_type=MovementType[kind],
        quantity=quantity, quantity_before=before, quantity_after=after,
        location_from=location_from, location_to=location_to, created_at=at, reason=reason)
    # Legacy records deliberately omit these snapshots; never infer them from totals.
    if stock_loja_before is not _UNSET:
        values['stock_loja_before'] = stock_loja_before
    if stock_loja_after is not _UNSET:
        values['stock_loja_after'] = stock_loja_after
    row = StockMovement(**values)
    db.add(row)
    db.flush()
    return row


def listing(client, **params):
    response = client.get(URL + '/items', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def parsed_exit(row):
    value = row['last_store_exit_at']
    if value is None:
        return None
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert stamp.tzinfo is not None, 'The browser needs an explicit timezone for movement timestamps'
    return stamp


def test_recent_store_exits_precede_known_passage_then_products_without_history(priority_env):
    factory, client = priority_env
    with factory() as db:
        newest = product(db, 'Z — última saída')
        older = product(db, 'A — saída antiga')
        passed = product(db, 'Z — já esteve na loja')
        unknown = product(db, 'A — nunca esteve na loja')
        movement(db, newest.id, at=BASE + timedelta(days=2))
        movement(db, older.id, at=BASE)
        movement(db, passed.id, kind='entry', quantity=2, before=0, after=2,
                 at=BASE + timedelta(days=10))
        ids = [str(row.id) for row in (newest, older, passed, unknown)]
        db.commit()
    data = listing(client)
    assert data['total'] == 4
    assert [row['id'] for row in data['items']] == ids
    assert [row['has_store_history'] for row in data['items']] == [True, True, True, False]
    assert parsed_exit(data['items'][0]).replace(tzinfo=None) == BASE + timedelta(days=2)
    assert parsed_exit(data['items'][1]).replace(tzinfo=None) == BASE
    assert parsed_exit(data['items'][2]) is parsed_exit(data['items'][3]) is None


@pytest.mark.parametrize('changes', [
    dict(kind='exit', quantity=1, location_from='loja'),
    dict(kind='transfer', quantity=1, location_from='loja', location_to='deposito', before=5, after=5),
    # The stock service historically defaults a missing destination to the depot.
    dict(kind='transfer', quantity=1, location_from='loja', location_to=None, before=5, after=5),
    dict(kind='adjustment', quantity=0, location_from='loja', before=7, after=5,
         stock_loja_before=2, stock_loja_after=0),
])
def test_all_real_store_reduction_kinds_can_set_latest_exit(priority_env, changes):
    factory, client = priority_env
    with factory() as db:
        row = product(db, 'Reposição com baixa real')
        movement(db, row.id, at=BASE, **changes)
        db.commit()
    result = listing(client)['items'][0]
    assert result['has_store_history'] is True
    assert parsed_exit(result).replace(tzinfo=None) == BASE


@pytest.mark.parametrize('changes', [
    dict(kind='entry', quantity=3, location_from='loja', before=0, after=3),
    dict(kind='entry', quantity=3, location_from=None, location_to='loja', before=0, after=3),
    dict(kind='transfer', quantity=1, location_from='deposito', location_to='loja', before=5, after=5),
    dict(kind='adjustment', quantity=2, location_from='loja', before=5, after=7),
    dict(kind='adjustment', quantity=2, location_from='loja', before=8, after=7),
    dict(kind='entry', quantity=5, location_from=None, reason='Importação CSV', before=0, after=5),
    dict(kind='entry', quantity=5, location_from=None, reason='Importação NF-e', before=0, after=5),
])
def test_known_store_passage_without_dated_exit_is_not_treated_as_never_stocked(priority_env, changes):
    factory, client = priority_env
    with factory() as db:
        unknown = product(db, 'A — sem histórico')
        passed = product(db, 'Z — passagem conhecida')
        movement(db, passed.id, **changes)
        expected = [str(passed.id), str(unknown.id)]
        db.commit()
    rows = listing(client)['items']
    assert [row['id'] for row in rows] == expected
    assert rows[0]['has_store_history'] is True
    assert parsed_exit(rows[0]) is None
    assert rows[1]['has_store_history'] is False


@pytest.mark.parametrize('changes', [
    dict(kind='exit', quantity=2, location_from='deposito'),
    dict(kind='entry', quantity=2, location_from='deposito', before=3, after=5),
    dict(kind='adjustment', quantity=2, location_from='deposito', before=6, after=5),
    dict(kind='adjustment', quantity=0, location_from='loja', before=5, after=5),
    # A total repair is not evidence that the store had units or sold anything.
    dict(kind='adjustment', quantity=0, location_from='loja', before=7, after=5),
    dict(kind='adjustment', quantity=0, location_from='loja', before=7, after=5,
         stock_loja_before=0, stock_loja_after=0),
    dict(kind='adjustment', quantity=0, location_from='loja', before=7, after=5,
         stock_loja_before=2),
    dict(kind='adjustment', quantity=0, location_from='loja', before=7, after=5,
         stock_loja_after=0),
    dict(kind='exit', quantity=0, location_from='loja', before=5, after=5),
    dict(kind='entry', quantity=0, location_from='loja', before=5, after=5),
    dict(kind='transfer', quantity=0, location_from='loja', location_to='deposito', before=5, after=5),
    dict(kind='entry', quantity=2, location_from=None, before=3, after=5, reason='Cadastro antigo'),
    dict(kind='exit', quantity=2, location_from=None, reason='Venda PDV'),
    dict(kind='entry', quantity=5, location_from='deposito', reason='Importação CSV', before=0, after=5),
    dict(kind='entry', quantity=5, location_from='deposito', reason='Importação NF-e', before=0, after=5),
    dict(kind='entry', quantity=5, location_from=None, location_to='deposito', reason='Importação CSV', before=0, after=5),
    dict(kind='entry', quantity=0, location_from=None, reason='Importação CSV', before=0, after=0),
    dict(kind='entry', quantity=5, location_from=None, reason='Importação CSV manual', before=0, after=5),
])
def test_unrelated_or_zero_movements_do_not_invent_a_store_history(priority_env, changes):
    factory, client = priority_env
    with factory() as db:
        row = product(db, 'Produto sem evidência da loja')
        movement(db, row.id, **changes)
        db.commit()
    result = listing(client)['items'][0]
    assert result['has_store_history'] is False
    assert parsed_exit(result) is None


def test_newer_depot_movement_and_product_edit_do_not_replace_last_store_exit(priority_env):
    factory, client = priority_env
    with factory() as db:
        old = product(db, 'A — antigo editado agora')
        latest = product(db, 'Z — baixa recente')
        movement(db, old.id, at=BASE)
        movement(db, old.id, kind='exit', location_from='deposito', at=BASE + timedelta(days=5))
        movement(db, old.id, kind='adjustment', quantity=0, before=5, after=5, at=BASE + timedelta(days=6))
        movement(db, latest.id, at=BASE + timedelta(days=1))
        old.description = 'Texto alterado após a última venda'
        old.updated_at = BASE + timedelta(days=20)
        expected = [str(latest.id), str(old.id)]
        db.commit()
    rows = listing(client)['items']
    assert [row['id'] for row in rows] == expected
    assert parsed_exit(rows[1]).replace(tzinfo=None) == BASE


def test_priority_is_global_before_pagination_and_stable_for_equal_dates(priority_env):
    factory, client = priority_env
    with factory() as db:
        for index in range(42):
            product(db, f'A sem histórico {index:02}')
        passed = product(db, 'Z passagem sem baixa')
        movement(db, passed.id, kind='entry', quantity=1, before=0, after=1)
        tied = [product(db, 'Z mesma saída') for _ in range(2)]
        for row in tied:
            movement(db, row.id, at=BASE)
        newest = product(db, 'Z saída mais recente')
        movement(db, newest.id, at=BASE + timedelta(days=1))
        expected_front = [str(newest.id), *sorted(str(row.id) for row in tied), str(passed.id)]
        db.commit()
    first = listing(client)
    second = listing(client, page=2)
    assert first['total'] == second['total'] == 46
    assert [row['id'] for row in first['items'][:4]] == expected_front
    assert len(first['items']) == 40 and len(second['items']) == 6
    assert not ({row['id'] for row in first['items']} & {row['id'] for row in second['items']})
    assert listing(client)['items'] == first['items']


def test_literal_search_relevance_precedes_replenishment_recency(priority_env):
    factory, client = priority_env
    with factory() as db:
        exact = product(db, 'Modelo 1HRGZ')
        similar = product(db, 'Modelo 1JRGZ')
        movement(db, similar.id, at=BASE + timedelta(days=10))
        expected = [str(exact.id), str(similar.id)]
        db.commit()
    rows = listing(client, q='1HRGZ')['items']
    assert [row['id'] for row in rows] == expected
    assert rows[0]['last_store_exit_at'] is None
    assert rows[1]['last_store_exit_at'] is not None


def test_replenish_sell_return_and_sell_again_updates_priority_from_real_movements(priority_env):
    factory, client = priority_env
    with factory() as db:
        target = product(db, 'Z item reposto')
        competing = product(db, 'A item vendido ontem')
        movement(db, competing.id, at=BASE + timedelta(days=1))
        target_id, competing_id = str(target.id), str(competing.id)
        user_id = db.query(Usuario).first().id
        db.commit()
    assert [row['id'] for row in listing(client)['items']] == [competing_id, target_id]
    setup_device(client)
    confirm(client, request_body(factory, client, [target_id]))
    assert [row['id'] for row in listing(client)['items']] == [competing_id]
    with factory() as db:
        sold = create_movement(db, uuid.UUID(target_id), 'exit', 1, user_id,
                               reason='Venda sintética', location='loja')
        sold.created_at = BASE
        db.commit()
    rows = listing(client)['items']
    assert [row['id'] for row in rows] == [competing_id, target_id]
    assert rows[1]['current_stock'] == rows[1]['stock_deposito'] == 4
    assert rows[1]['stock_loja'] == 0
    with factory() as db:
        returned = create_movement(db, uuid.UUID(target_id), 'entry', 1, user_id,
                                   reason='Devolução sintética', location='loja')
        returned.created_at = BASE + timedelta(days=2)
        db.commit()
    assert [row['id'] for row in listing(client)['items']] == [competing_id]
    with factory() as db:
        resold = create_movement(db, uuid.UUID(target_id), 'exit', 1, user_id,
                                 reason='Nova venda sintética', location='loja')
        resold.created_at = BASE + timedelta(days=3)
        db.commit()
    rows = listing(client)['items']
    assert [row['id'] for row in rows] == [target_id, competing_id]
    assert parsed_exit(rows[0]).replace(tzinfo=None) == BASE + timedelta(days=3)
    assert rows[0]['has_store_history'] is True
    assert rows[0]['current_stock'] == rows[0]['stock_deposito'] == 4
    with factory() as db:
        # Reordering never prints a second label or changes balances itself.
        assert db.query(PrintJob).count() == 1
        assert db.query(StockMovement).filter_by(item_id=uuid.UUID(target_id)).count() == 4


def test_known_store_exit_without_timestamp_keeps_known_history_tier(priority_env):
    factory, client = priority_env
    with factory() as db:
        unknown = product(db, 'A sem histórico')
        known = product(db, 'Z saída legada sem data')
        recorded = movement(db, known.id)
        db.execute(update(StockMovement).where(StockMovement.id == recorded.id).values(created_at=None))
        expected = [str(known.id), str(unknown.id)]
        db.commit()
    rows = listing(client)['items']
    assert [row['id'] for row in rows] == expected
    assert rows[0]['has_store_history'] is True and rows[0]['last_store_exit_at'] is None


def test_postgres_store_history_aggregation_orders_globally_with_timezone(replenishment_pg):
    factory, client, _, _ = replenishment_pg
    with factory() as db:
        for index in range(41):
            product(db, f'A sem histórico {index:02}')
        oldest = product(db, 'Z antiga')
        newest = product(db, 'Z recente')
        legacy = product(db, 'Z importada')
        movement(db, oldest.id, at=BASE)
        movement(db, oldest.id, location_from='deposito', at=BASE + timedelta(days=20))
        movement(db, newest.id, kind='adjustment', quantity=0, before=7, after=5,
                 stock_loja_before=2, stock_loja_after=0, at=BASE + timedelta(days=1))
        movement(db, legacy.id, kind='entry', quantity=5, location_from=None,
                 reason='Importação NF-e', before=0, after=5)
        expected = [str(newest.id), str(oldest.id), str(legacy.id)]
        db.commit()
    first = listing(client)
    second = listing(client, page=2)
    assert first['total'] == second['total'] == 44
    assert [row['id'] for row in first['items'][:3]] == expected
    assert parsed_exit(first['items'][0]).replace(tzinfo=None) == BASE + timedelta(days=1)
    assert parsed_exit(first['items'][1]).replace(tzinfo=None) == BASE
    assert first['items'][2]['has_store_history'] is True
    assert first['items'][2]['last_store_exit_at'] is None
    assert len(first['items']) == 40 and len(second['items']) == 4


def test_stock_adjustment_snapshots_distinguish_real_depletion_from_total_repair(priority_env):
    factory, client = priority_env
    with factory() as db:
        depleted = product(db, 'Z loja que tinha duas peças', current_stock=7, stock_loja=2, stock_deposito=5)
        repaired = product(db, 'A total incorreto sem peças na loja', current_stock=7, stock_loja=0, stock_deposito=5)
        user_id = db.query(Usuario).first().id
        ids = str(depleted.id), str(repaired.id)
        db.commit()
    with factory() as db:
        actual = create_movement(db, uuid.UUID(ids[0]), 'adjustment', 0, user_id,
                                 reason='Contagem física sintética', location='loja')
        actual.created_at = BASE
        correction = create_movement(db, uuid.UUID(ids[1]), 'adjustment', 0, user_id,
                                     reason='Correção do total sintética', location='loja')
        correction.created_at = BASE + timedelta(days=3)
        db.commit()
        assert (actual.quantity_before, actual.quantity_after) == (7, 5)
        assert (correction.quantity_before, correction.quantity_after) == (7, 5)
        assert (actual.stock_loja_before, actual.stock_loja_after) == (2, 0)
        assert (correction.stock_loja_before, correction.stock_loja_after) == (0, 0)
    rows = listing(client)['items']
    assert [row['id'] for row in rows] == list(ids)
    assert all(row['current_stock'] == row['stock_deposito'] == 5 for row in rows)
    assert rows[0]['has_store_history'] is True
    assert parsed_exit(rows[0]).replace(tzinfo=None) == BASE
    assert rows[1]['has_store_history'] is False
    assert rows[1]['last_store_exit_at'] is None
    assert rows[1]['blocked_reason'] is None


def test_ambiguous_zero_adjustment_never_replaces_an_older_confirmed_store_exit(priority_env):
    factory, client = priority_env
    with factory() as db:
        row = product(db, 'Peça com baixa confirmada e correção legada')
        movement(db, row.id, kind='exit', quantity=1, at=BASE)
        movement(db, row.id, kind='adjustment', quantity=0, before=7, after=5,
                 at=BASE + timedelta(days=7))
        db.commit()
    result = listing(client)['items'][0]
    assert result['has_store_history'] is True
    assert parsed_exit(result).replace(tzinfo=None) == BASE
