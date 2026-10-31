"""A coincident code does not override incompatible recipient/order identities."""
import pytest

from test_assistant import setup
from test_customer_links import logistics
from test_customer_shipping_integration import shipping_env, ADDRESS, stored_freight
from app.models import Cliente, Pedido, Rastreamento
from app.services.address_book import save_or_reuse
from app.services.superfrete import sync_tracking


@pytest.mark.parametrize(('recipient', 'order_name', 'expected_link'), [
    ('Outra Pessoa Sintética', None, False),
    (ADDRESS['nome'].upper(), 'Outra Pessoa Sintética', False),
    (ADDRESS['nome'].upper(), ADDRESS['nome'].upper(), True),
    ('', None, True),
])
def test_missing_customer_is_filled_only_when_historical_names_are_compatible(
        shipping_env, recipient, order_name, expected_link):
    factory, _, user_id = shipping_env
    with factory() as db:
        customer = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'])
        db.add(customer); db.flush()
        address, _ = save_or_reuse(db, ADDRESS.copy(), user_id, cliente_id=customer.id)
        freight = stored_freight(db, address, user_id, 'QA555555555BR')
        row = Rastreamento(codigo_rastreio=freight.tracking, destinatario=recipient,
            destino='Destino original preservado')
        parent = None
        if order_name:
            parent = Pedido(numero_pedido='QA-IDENTITY-GUARD', cliente_nome=order_name,
                descricao='Pedido preservado', valor_total=10)
            db.add(parent); db.flush(); row.pedido_id = parent.id
        db.add(row); db.flush()
        sync_tracking(db, freight)
        sync_tracking(db, freight)
        assert row.cliente_id == (customer.id if expected_link else None)
        assert row.destinatario == recipient and row.destino == 'Destino original preservado'
        assert db.query(Rastreamento).count() == 1
        if parent:
            assert parent.cliente_id is None and parent.cliente_nome == order_name


def test_original_freight_name_remains_valid_after_customer_name_changes(shipping_env):
    factory, _, user_id = shipping_env
    with factory() as db:
        customer = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'])
        db.add(customer); db.flush()
        address, _ = save_or_reuse(db, ADDRESS.copy(), user_id, cliente_id=customer.id)
        freight = stored_freight(db, address, user_id, 'QA666666666BR')
        freight.payload = {**freight.payload, '_customer_id': str(customer.id)}
        customer.nome = 'Nome Atual Sintético'
        row = Rastreamento(codigo_rastreio=freight.tracking, destinatario=ADDRESS['nome'].upper())
        db.add(row); db.flush()
        sync_tracking(db, freight)
        assert row.cliente_id == customer.id and row.destinatario == ADDRESS['nome'].upper()
