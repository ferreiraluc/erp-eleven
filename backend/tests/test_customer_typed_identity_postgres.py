"""Real PostgreSQL validates additive migration and identity serialization."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from test_access_postgres import pg, upgrade


def test_typed_documents_migration_preserves_legacy_and_untyped_pdv_values(pg):
    engine, schema = pg
    customer, account = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        connection.exec_driver_sql('CREATE TABLE clientes(id uuid PRIMARY KEY, nome text, cpf text)')
        connection.exec_driver_sql('CREATE TABLE pdv_clientes(id uuid PRIMARY KEY, doc text, saldo_fiado_gs numeric)')
        connection.execute(sa.text("INSERT INTO clientes VALUES (:id,'Nome original','12345678909')"), {'id': customer})
        connection.execute(sa.text("INSERT INTO pdv_clientes VALUES (:id,'80012345-6',777)"), {'id': account})
        upgrade(connection, 's1b2c3d4e5f6_customer_documents.py')
        assert connection.execute(sa.text('SELECT nome,cpf,documentos FROM clientes')).one() == ('Nome original', '12345678909', [])
        assert connection.execute(sa.text('SELECT doc,saldo_fiado_gs,doc_tipo,doc_pais FROM pdv_clientes')).one() == ('80012345-6', 777, None, None)
        connection.execute(sa.text("INSERT INTO clientes(id,nome) VALUES (:id,'Sem documento')"), {'id': uuid.uuid4()})
        assert connection.execute(sa.text('SELECT documentos FROM clientes WHERE cpf IS NULL')).scalar() == []


def _isolated_identity_schema(pg, monkeypatch):
    from app.config import settings
    from app.database import Base
    from app.models import Usuario, Vendedor, Cliente
    from app.models.pdv import PdvCliente
    from app.models.address_book import SavedAddress
    monkeypatch.setattr(settings, 'ASSISTANT_ENABLED', False)
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in (Usuario, Vendedor, Cliente, PdvCliente, SavedAddress)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    uid = uuid.uuid4()
    with factory() as db:
        db.add(Usuario(id=uid, nome='Fixture local', email='fixture-local@example.test', senha_hash='unused'))
        db.commit()
    return isolated, factory, uid


def test_concurrent_address_and_pdv_account_share_typed_ci_customer(pg, monkeypatch):
    from app.models import Cliente
    from app.models.pdv import PdvCliente
    from app.services.address_book import save_or_reuse, lock_addresses
    from app.services.customer_identity import ensure_pdv_customer
    isolated, factory, uid = _isolated_identity_schema(pg, monkeypatch)
    barrier = Barrier(2)
    def create(source):
        with factory() as db:
            barrier.wait(timeout=10)
            if source == 'address':
                row, _ = save_or_reuse(db, {'pais': 'PY', 'nome': 'Maria Elena Lopez', 'cpf': '3.456.789',
                    'documento_tipo': 'CI', 'cidade': 'Asunción'}, uid)
                customer_id = row.cliente_id
            else:
                lock_addresses(db)
                row = PdvCliente(nome='Maria Lopez', doc='3456789', doc_tipo='CI', doc_pais='PY', saldo_fiado_gs=777)
                db.add(row); db.flush()
                ensure_pdv_customer(db, row)
                customer_id = row.cadastro_cliente_id
            db.commit()
            return customer_id
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(create, ['address', 'pdv']))
        assert ids[0] and ids[0] == ids[1]
        with factory() as db:
            assert db.query(Cliente).count() == 1
            assert db.query(PdvCliente).one().saldo_fiado_gs == 777
    finally:
        isolated.dispose()


def test_concurrent_name_only_entries_stay_pending_without_new_duplicate(pg, monkeypatch):
    from app.models import Cliente
    from app.models.address_book import SavedAddress
    from app.services.address_book import save_or_reuse
    isolated, factory, uid = _isolated_identity_schema(pg, monkeypatch)
    barrier = Barrier(2)
    def create(city):
        with factory() as db:
            barrier.wait(timeout=10)
            row, _ = save_or_reuse(db, {'pais': 'PY', 'nome': 'Mesmo Cliente', 'cidade': city}, uid)
            result = row.cliente_id
            db.commit()
            return result
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(create, ['Asunción', 'Encarnación']))
        assert sum(customer_id is not None for customer_id in ids) == 1
        with factory() as db:
            assert db.query(Cliente).count() == 1
            assert db.query(SavedAddress).count() == 2
            assert db.query(SavedAddress).filter_by(customer_link_review=True, cliente_id=None).count() == 1
    finally:
        isolated.dispose()
