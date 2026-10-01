"""Missing stock remains unknown in read-only assistant queries."""
from test_assistant import setup
from app.models.inventory import Item
from app.services.assistant_queries import query_stock, StockArgs


def add_item(db, name, total, loja, deposito, active=True):
    item = Item(name=name, sku_internal=name, is_active=active)
    db.add(item); db.flush()
    item.current_stock, item.stock_loja, item.stock_deposito = total, loja, deposito
    db.flush()
    return item


def test_partial_stock_totals_report_missing_before_pagination(setup):
    factory, _, _ = setup
    with factory() as db:
        add_item(db, 'A completo', 8, 3, 5)
        add_item(db, 'B incompleto', None, None, 2)
        add_item(db, 'C zerado', 0, 0, 0)
        add_item(db, 'D inativo', None, None, None, False)
        result = query_stock(db, StockArgs(limite=1))
        assert result['total'] == 3 and len(result['resultados']) == 1
        assert result['unidades'] is None
        assert result['saldos_por_local'] == {'total': None, 'loja': None, 'deposito': 7}
        assert result['subtotal_saldos_conhecidos'] == {'total': 8, 'loja': 3, 'deposito': 7}
        assert result['itens_sem_saldo'] == {'total': 1, 'loja': 1, 'deposito': 0}
        second = query_stock(db, StockArgs(limite=1, pagina=2))
        assert second['resultados'][0]['total'] is None
        assert second['resultados'][0]['saldo_incompleto'] is True
        assert second['saldos_por_local'] == result['saldos_por_local']
        assert db.query(Item).filter_by(name='B incompleto').one().stock_loja is None


def test_unknown_filter_is_per_location_and_zero_is_not_unknown(setup):
    factory, _, _ = setup
    with factory() as db:
        add_item(db, 'Legado', 4, None, 2)
        add_item(db, 'Zero', 0, 0, 0)
        unknown = query_stock(db, StockArgs(situacao='nao_informado', local='loja'))
        assert unknown['total'] == 1 and unknown['unidades'] is None
        assert unknown['resultados'][0]['produto'] == 'Legado'
        assert unknown['saldos_por_local']['total'] == 4
        zero = query_stock(db, StockArgs(situacao='zerado', local='loja'))
        assert zero['total'] == 1 and zero['unidades'] == 0
        assert zero['resultados'][0]['produto'] == 'Zero'
        assert query_stock(db, StockArgs(situacao='nao_informado', local='deposito'))['total'] == 0


def test_all_unknown_and_empty_queries_remain_distinct(setup):
    factory, _, _ = setup
    with factory() as db:
        add_item(db, 'Legado', None, None, None)
        unknown = query_stock(db, StockArgs())
        assert unknown['unidades'] is None
        assert unknown['itens_sem_saldo'] == {'total': 1, 'loja': 1, 'deposito': 1}
        empty = query_stock(db, StockArgs(termo='Não existe'))
        assert empty['total'] == 0 and empty['unidades'] == 0
        assert empty['itens_sem_saldo'] == {'total': 0, 'loja': 0, 'deposito': 0}
