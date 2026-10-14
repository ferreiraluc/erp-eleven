"""Order directory queries all records, but only materializes one page."""
from datetime import datetime, timezone, timedelta

from test_assistant import setup
from test_customer_links import logistics
from app.models import Pedido, Cliente
from app.models.pedido import PedidoStatus
from app.models.pedido_tag import TagStatus


def seed(factory, user_id, count=125):
    with factory() as db:
        customer = Cliente(nome='Cliente QA', ativo=True)
        tag = TagStatus(nome='Conferir', cor='#000000', ativo=True)
        db.add_all([customer, tag]); db.flush()
        tag_id = str(tag.id)
        for i in range(count):
            row = Pedido(
                numero_pedido=f'QA-{i:03}', descricao='Pedido de teste', valor_total=10,
                cliente_nome=f'Cliente {i:03}', cliente_id=customer.id, created_by=user_id,
                endereco_entrega='Cidade QA', status=PedidoStatus.PENDENTE,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
            )
            if i == 0:
                row.cliente_nome = 'Pessoa 100%_QA'
                row.codigo_rastreio = 'QA123456789BR'
                row.tags = [tag]
            db.add(row)
        db.commit()
    return tag_id


def test_pages_and_search_cover_orders_beyond_old_first_hundred(logistics):
    factory, client, user_id = logistics
    seed(factory, user_id)
    first = client.get('/api/pedidos/pagina').json()
    second = client.get('/api/pedidos/pagina', params={'page': 2}).json()
    assert first['total'] == second['total'] == 125
    assert len(first['items']) == len(second['items']) == 20
    assert {x['id'] for x in first['items']}.isdisjoint(x['id'] for x in second['items'])
    last = client.get('/api/pedidos/pagina', params={'page': 7}).json()
    assert len(last['items']) == 5
    assert last['items'][-1]['numero_pedido'] == 'QA-000'
    for search in ('QA-000', 'qa123456789br', '100%_QA'):
        found = client.get('/api/pedidos/pagina', params={'search': search}).json()
        assert found['total'] == 1
        assert found['items'][0]['numero_pedido'] == 'QA-000'
        assert found['items'][0]['cliente']['nome'] == 'Cliente QA'


def test_order_filters_count_same_set_and_escape_wildcards(logistics):
    factory, client, user_id = logistics
    tag_id = seed(factory, user_id, 3)
    result = client.get('/api/pedidos/pagina', params={
        'tag_id': tag_id, 'status': 'PENDENTE', 'search': 'Cidade QA',
    }).json()
    assert result['total'] == 1
    assert result['items'][0]['tags'][0]['id'] == tag_id
    assert client.get('/api/pedidos/pagina', params={'search': '%'}).json()['total'] == 1
    assert client.get('/api/pedidos/pagina', params={'search': "' OR 1=1 --"}).json()['total'] == 0
    assert client.get('/api/pedidos/pagina', params={'status': 'ENTREGUE'}).json()['total'] == 0
    # Existing consumers keep the original list response.
    assert isinstance(client.get('/api/pedidos/').json(), list)


def test_order_page_validation_and_auth(logistics):
    _, client, _ = logistics
    for params in ({'page': 0}, {'page_size': 101}, {'search': 'x' * 201}, {'status': 'INVALID'}):
        assert client.get('/api/pedidos/pagina', params=params).status_code == 422
    client.app.dependency_overrides.clear()
    assert client.get('/api/pedidos/pagina').status_code in (401, 403)
