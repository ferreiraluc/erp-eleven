"""Customer association through real HTTP routes, using synthetic data only."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa

from test_pdv_unknown_stock import pdv_app, sale_payload
from test_pdv_stock_postgres import pdv_pg
from test_access_postgres import pg, upgrade
from app.models import Cliente, Usuario
from app.models.address_book import SavedAddress
from app.models.pdv import PdvCliente, PdvSale
from app.services import pdv_customers
from app.schemas.pdv import PdvCustomerSelection


def seed(factory):
    with factory() as db:
        user = db.query(Usuario).first()
        main = Cliente(nome='João Ávila', cpf='123.456.789-09', telefone='+595 972 123456')
        other = Cliente(nome='João Martins', cpf='98765432100')
        pdv = PdvCliente(nome='Maria Souza', doc='3.456.789-1', telefone='+55 (45) 99999-1234')
        db.add_all([main, other, pdv]); db.flush()
        db.add_all([
            SavedAddress(label='Casa', cliente_id=main.id, created_by=user.id,
                data={'pais':'BR','nome':main.nome,'cidade':'Foz do Iguaçu','cep':'85865-310'}),
            SavedAddress(label='Empresa', cliente_id=other.id, created_by=user.id,
                data={'pais':'BR','nome':other.nome,'cidade':'Foz do Iguaçu','cep':'85865310'}),
            SavedAddress(label='Maria', pdv_cliente_id=pdv.id, created_by=user.id,
                data={'pais':'BR','nome':pdv.nome,'cep':'85855-000'}),
        ])
        ids = main.id, other.id, pdv.id
        db.commit()
        return ids


@pytest.mark.parametrize('query,expected', [('joao avila', 0), ('JOÃO ÁVILA', 0), ('595972123456', 0),
    ('+595 (972) 123-456', 0), ('0972123456', 0), ('12345678909', 0), ('123.456.789-09', 0), ('85865310', 0),
    ('85865-310', 0), ('MARIA', 2), ('34567891', 2), ('45999991234', 2), ('85855000', 2)])
def test_lookup_normalizes_names_phone_document_and_postal_code(pdv_app, query, expected):
    factory, client, _ = pdv_app
    ids = seed(factory)
    before = None
    with factory() as db: before = db.query(PdvCliente).count()
    response = client.get('/api/pdv/clients/search', params={'q':query})
    assert response.status_code == 200, response.text
    rows = response.json()['items']
    assert str(ids[expected]) in [r['id'] for r in rows]
    assert all('saldo_fiado_gs' not in r and 'email' not in r for r in rows)
    with factory() as db: assert db.query(PdvCliente).count() == before


def test_shared_cep_lists_both_people_without_guessing_and_rejects_wildcards(pdv_app):
    factory, client, _ = pdv_app
    seed(factory)
    result = client.get('/api/pdv/clients/search', params={'q':'85865-310'}).json()
    assert len(result['items']) == 2
    for query in ('', 'a', '%%', '__', "' OR 1=1 --"):
        assert client.get('/api/pdv/clients/search', params={'q':query}).json()['items'] == []
    assert client.get('/api/pdv/clients/search', params={'q':'João','limit':1}).json()['has_more']


def test_select_directory_customer_reuses_link_and_sale_uses_authoritative_name(pdv_app):
    factory, client, _ = pdv_app
    main, _, _ = seed(factory)
    body = {'source':'cadastro','id':str(main)}
    response = client.post('/api/pdv/clients/select', json=body)
    assert response.status_code == 200, response.text
    customer_id = response.json()['id']
    assert response.json()['cadastro_cliente_id'] == str(main)
    assert client.post('/api/pdv/clients/select', json=body).json()['id'] == customer_id
    rows = client.get('/api/pdv/clients/search', params={'q':'85865310'}).json()['items']
    assert (customer_id, 'pdv') in [(r['id'],r['source']) for r in rows]
    assert str(main) not in [r['id'] for r in rows]
    payload = sale_payload([None], customer_id, avulso=True)
    payload['cliente_nome'] = 'Incorrect supplied name'
    sale = client.post('/api/pdv/sales', json=payload)
    assert sale.status_code == 201, sale.text
    assert sale.json()['cliente_id'] == customer_id and sale.json()['cliente_nome'] == 'João Ávila'
    with factory() as db:
        assert db.query(PdvCliente).filter_by(cadastro_cliente_id=main).count() == 1


def test_existing_document_and_full_name_reuse_pdv_without_resetting_financials(pdv_app):
    factory, client, _ = pdv_app
    main, _, _ = seed(factory)
    with factory() as db:
        customer = PdvCliente(nome='JOAO AVILA', doc='12345678909', saldo_fiado_gs=777, limite_fiado_gs=999)
        db.add(customer); db.flush(); cid = customer.id; db.commit()
    response = client.post('/api/pdv/clients/select', json={'source':'cadastro','id':str(main)})
    assert response.status_code == 200, response.text
    assert response.json()['id'] == str(cid) and response.json()['saldo_fiado_gs'] == 777
    assert response.json()['limite_fiado_gs'] == 999


def test_conflicting_identity_inactive_and_stale_customer_are_rejected(pdv_app):
    factory, client, _ = pdv_app
    main, _, pdv = seed(factory)
    with factory() as db:
        db.add(PdvCliente(nome='Outra Pessoa', doc='12345678909'))
        db.get(PdvCliente, pdv).ativo = False
        db.commit()
    for source, cid in [('cadastro', main), ('pdv', pdv), ('cadastro', uuid.uuid4())]:
        assert client.post('/api/pdv/clients/select', json={'source':source,'id':str(cid)}).status_code == 409
    response = client.post('/api/pdv/sales', json=sale_payload([None], pdv, avulso=True))
    assert response.status_code == 409
    with factory() as db: assert db.query(PdvSale).count() == 0


def test_search_ignores_inactive_merged_and_unreviewed_addresses(pdv_app):
    factory, client, _ = pdv_app
    main, other, _ = seed(factory)
    with factory() as db:
        db.get(Cliente, other).ativo = False
        db.query(SavedAddress).filter_by(cliente_id=main).one().customer_link_review = True
        db.commit()
    assert client.get('/api/pdv/clients/search', params={'q':'85865310'}).json()['items'] == []
    assert client.get('/api/pdv/clients/search', params={'q':'João Martins'}).json()['items'] == []


def test_cep_in_legacy_customer_address_and_employee_balance_privacy(pdv_app):
    factory, client, cid = pdv_app
    with factory() as db:
        main = Cliente(nome='Cliente antigo', endereco='Rua Exemplo, 55, Foz, PR, CEP 85855-123')
        db.add(main); db.query(Usuario).first().sales_scope = 'own'; db.commit()
    assert client.get('/api/pdv/clients/search', params={'q':'85855123'}).json()['items'][0]['nome'] == 'Cliente antigo'
    result = client.post('/api/pdv/clients/select', json={'source':'pdv','id':str(cid)})
    assert result.status_code == 200 and result.json()['saldo_fiado_gs'] is None


def test_search_requires_authentication():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.endpoints import pdv
    app = FastAPI(); app.include_router(pdv.router, prefix='/pdv')
    with TestClient(app) as client:
        assert client.get('/pdv/clients/search?q=joao').status_code in (401,403)
        assert client.post('/pdv/clients/select', json={'source':'pdv','id':str(uuid.uuid4())}).status_code in (401,403)


def test_postgres_normalization_and_concurrent_selection_do_not_duplicate(pdv_pg):
    factory, _, _, _, _ = pdv_pg
    main, _, _ = seed(factory)
    with factory() as db:
        assert pdv_customers.search(db, 'joao avila')['items'][0]['id'] == main
        assert len(pdv_customers.search(db, '85865310')['items']) == 2
    barrier = Barrier(2)
    def choose(_):
        with factory() as db:
            user = db.query(Usuario).first()
            barrier.wait(timeout=5)
            row = pdv_customers.select(db, PdvCustomerSelection(source='cadastro', id=main), user)
            uid = row.id; db.commit(); return uid
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(choose, range(2)))
    assert ids[0] == ids[1]
    with factory() as db: assert db.query(PdvCliente).filter_by(cadastro_cliente_id=main).count() == 1


def test_postgres_migration_preserves_existing_customers_and_rejects_dangling_link(pg):
    engine, schema = pg
    cid = uuid.uuid4()
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE clientes(id uuid PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE pdv_clientes(id uuid PRIMARY KEY, nome text, saldo_fiado_gs numeric)')
        conn.execute(sa.text("INSERT INTO pdv_clientes VALUES(:id,'Original',777)"), {'id':cid})
        upgrade(conn, 'c5d6e7f8a9b0_pdv_customer_link.py')
        assert conn.execute(sa.text('SELECT nome, saldo_fiado_gs, cadastro_cliente_id FROM pdv_clientes')).one() == ('Original',777,None)
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
            conn.execute(sa.text('UPDATE pdv_clientes SET cadastro_cliente_id=:id'), {'id':uuid.uuid4()})
