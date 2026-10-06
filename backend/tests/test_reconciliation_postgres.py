"""Disposable PostgreSQL proves migration constraints and cross-channel serialization."""
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from test_access_postgres import pg, upgrade


def test_identity_migration_preserves_old_records(pg):
    engine,schema=pg
    vendor,address=uuid.uuid4(),uuid.uuid4()
    with engine.begin() as c:
        c.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        c.exec_driver_sql('CREATE TABLE vendedores(id uuid PRIMARY KEY,nome text)')
        c.exec_driver_sql('CREATE TABLE saved_addresses(id uuid PRIMARY KEY,data jsonb)')
        c.execute(sa.text('INSERT INTO vendedores VALUES (:id,\'Teste\')'),{'id':vendor})
        c.execute(sa.text('INSERT INTO saved_addresses VALUES (:id,\'{"nome":"Teste"}\')'),{'id':address})
        upgrade(c,'d0e1f2a3b4c5_customer_vendor_identity.py')
        assert c.execute(sa.text('SELECT id,data,customer_link_review,customer_link_reason FROM saved_addresses')).one()==(address,{'nome':'Teste'},False,None)
        c.execute(sa.text("UPDATE vendedores SET sales_seller='Junior'"))
    import pytest
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as c:
            c.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
            c.execute(sa.text("INSERT INTO vendedores VALUES (:id,'Duplicate','Junior')"),{'id':uuid.uuid4()})


def test_concurrent_addresses_share_one_new_customer(pg,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.config import settings
    from app.database import Base
    from app.models import Usuario,Vendedor,Cliente
    from app.models.pdv import PdvCliente
    from app.models.address_book import SavedAddress
    from app.services.address_book import save_or_reuse
    monkeypatch.setattr(settings,'ASSISTANT_ENABLED',False)
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Cliente,PdvCliente,SavedAddress)])
    factory=sessionmaker(bind=isolated,autoflush=False)
    uid=uuid.uuid4()
    with factory() as db:
        db.add(Usuario(id=uid,nome='Fixture',email='fixture@example.test',senha_hash='unused'));db.commit()
    barrier=Barrier(2)
    def create(city):
        with factory() as db:
            barrier.wait(timeout=10)
            row,_=save_or_reuse(db,{'pais':'PY','nome':'Mesmo Cliente','cidade':city},uid)
            cid=row.cliente_id;db.commit();return cid
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids=list(pool.map(create,['Asunción','Encarnación']))
        assert ids[0]==ids[1]
        with factory() as db:
            assert db.query(Cliente).count()==1 and db.query(SavedAddress).count()==2
    finally: isolated.dispose()
