"""Real PostgreSQL migration/transaction checks in isolated local/CI schemas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.notification import Notification, NotificationRecipient, NotificationRevision, NotificationRule
from app.models.notification_push import NotificationPushDelivery
from app.models.usuario import Usuario, UsuarioRole
from app.services import notifications as service
from test_access_postgres import pg, upgrade
from test_notifications import MODELS


@pytest.fixture
def factory(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in MODELS])
    try:
        yield sessionmaker(bind=isolated, autoflush=False, expire_on_commit=False)
    finally:
        isolated.dispose()


def user(db):
    value = Usuario(id=uuid.uuid4(), nome='Local fixture', email=f'{uuid.uuid4().hex}@fixture.local',
        senha_hash='unused', ativo=True, role=UsuarioRole.GERENTE, sales_scope='own')
    db.add(value)
    db.commit()
    return value.id


def test_migration_preserves_accounts_and_adds_unique_outbox_and_receipts(pg):
    engine, schema = pg
    uid = uuid.uuid4()
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE usuarios(id uuid PRIMARY KEY,email varchar(100) NOT NULL)')
        conn.exec_driver_sql('CREATE TABLE auth_sessions(id uuid PRIMARY KEY,user_id uuid REFERENCES usuarios(id))')
        conn.execute(sa.text('INSERT INTO usuarios VALUES(:id,:email)'), {'id': uid, 'email': 'fixture@local'})
        upgrade(conn, 'o7d8e9f0a1b2_notification_center.py')
        assert conn.execute(sa.text('SELECT id,email FROM usuarios')).one() == (uid, 'fixture@local')
        inspector = sa.inspect(conn)
        assert {'notifications', 'notification_recipients', 'notification_push_deliveries', 'notification_revisions'} <= set(inspector.get_table_names(schema=schema))
        uniques = inspector.get_unique_constraints('notification_push_deliveries', schema=schema)
        assert any(set(row['column_names']) == {'notification_id', 'subscription_id'} for row in uniques)
        recipient_uniques = inspector.get_unique_constraints('notification_recipients', schema=schema)
        assert any(set(row['column_names']) == {'notification_id', 'user_id'} for row in recipient_uniques)
        assert len(inspector.get_foreign_keys('notification_push_deliveries', schema=schema)) == 3


def test_concurrent_replayed_events_create_one_message_and_outer_rollback_is_atomic(factory):
    with factory() as db:
        uid = user(db)
    ready = Barrier(2)
    def emit(_):
        with factory() as db:
            ready.wait(timeout=10)
            notice = service.emit_notification(db, title='Fixture', body='Local only', user_ids=[uid], dedupe_key='concurrent:sale:review')
            db.commit()
            return notice.id
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(emit, range(2)))
    assert ids[0] == ids[1]
    with factory() as db:
        assert db.query(Notification).count() == db.query(NotificationRecipient).count() == db.query(NotificationRevision).count() == 1
        service.emit_notification(db, title='Rollback fixture', body='Never deliver', user_ids=[uid], dedupe_key='rollback:fixture')
        db.rollback()
        assert db.query(Notification).count() == 1
        assert db.query(NotificationPushDelivery).count() == 0


def test_overlapping_workers_seed_and_run_daily_rules_once(factory):
    with factory() as db:
        user(db)
    ready = Barrier(2)
    moment = datetime(2026, 10, 27, 12, 1, tzinfo=timezone.utc)
    def cycle(_):
        with factory() as db:
            ready.wait(timeout=10)
            service.run_notification_rules(db, moment)
            db.commit()
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(cycle, range(2)))
    with factory() as db:
        assert db.query(NotificationRule).count() == len(service.DEFAULTS)
        assert db.query(Notification).count() == 1
        assert db.query(NotificationRecipient).count() == 1
        assert db.query(NotificationRevision).count() == 1


def test_scheduled_publication_claim_is_once_across_deploys(factory):
    with factory() as db:
        uid = user(db)
        due = service.utcnow() + timedelta(minutes=1)
        notice = service.emit_notification(db, title='Future', body='Local only', user_ids=[uid], scheduled_at=due)
        notice_id = notice.id
        db.commit()
    ready = Barrier(2)
    def publish(_):
        with factory() as db:
            ready.wait(timeout=10)
            result = service.publish_due_notifications(db, due + timedelta(seconds=1))
            db.commit()
            return result
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(publish, range(2)))
    assert sum(results) == 1
    with factory() as db:
        assert db.get(Notification, notice_id).published_at
        assert db.query(NotificationRecipient).count() == 1


def test_concurrent_owner_edits_reject_stale_version_without_lost_update(factory):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.api.endpoints.notifications import edit
    from app.schemas.notification import NotificationUpdate
    with factory() as db:
        uid = user(db)
        notice = service.emit_notification(db, title='Original', body='Local only', user_ids=[uid])
        notice_id = notice.id
        db.commit()
    ready = Barrier(2)
    def change(title):
        with factory() as db:
            ready.wait(timeout=10)
            try:
                result = edit(notice_id, NotificationUpdate(title=title, body='Changed locally', user_ids=[uid], expected_version=1),
                              owner=SimpleNamespace(id=uid), db=db)
                return result['version']
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(change, ['First editor', 'Second editor']))
    assert sorted(results) == [2, 409]
    with factory() as db:
        notice = db.get(Notification, notice_id)
        assert notice.version == 2 and notice.title in {'First editor', 'Second editor'}
        assert db.query(NotificationRevision).filter_by(notification_id=notice_id).count() == 2


def test_concurrent_request_id_with_different_body_does_not_claim_other_message(factory):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.api.endpoints.notifications import create
    from app.schemas.notification import NotificationCreate
    with factory() as db:
        uid = user(db)
    request_id = uuid.uuid4()
    ready = Barrier(2)
    def submit(text):
        with factory() as db:
            ready.wait(timeout=10)
            try:
                result = create(NotificationCreate(request_id=request_id, title='Fixture', body=text, user_ids=[uid]),
                                owner=SimpleNamespace(id=uid), db=db)
                return result['body']
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, ['Message A', 'Message B']))
    assert 409 in results and sum(isinstance(result, str) for result in results) == 1
    with factory() as db:
        assert db.query(Notification).count() == db.query(NotificationRecipient).count() == 1


def test_owner_template_unavailable_variable_does_not_block_sale_commit(factory):
    from types import SimpleNamespace
    from app.api.endpoints.notifications import edit_template
    from app.models.notification import NotificationTemplate
    from app.models.pdv import PdvSale
    from app.schemas.notification import TemplateUpdate
    from app.services import notification_events
    with factory() as db:
        # Use a real owner identity so the operational event has its actual audience.
        owner = Usuario(id=uuid.uuid4(), nome='Lucas fixture', email='lucas@eleven.com', senha_hash='unused',
            ativo=True, role=UsuarioRole.ADMIN, sales_scope='all')
        db.add(owner)
        service.ensure_defaults(db)
        db.commit()
        uid = owner.id
        template = db.get(NotificationTemplate, db.get(NotificationRule, 'sale_completed').template_id)
        edit_template(template.id, TemplateUpdate(name=template.name, title='{tracking_code}', body='{status}',
            category='sales', severity='success', expected_version=template.version), owner=SimpleNamespace(id=uid), db=db)
    # The fixture normally creates notification/access tables only. Add the
    # sale's prerequisite tables in the same isolated schema, never production.
    from app.models.cliente import Cliente
    from app.models.pdv import PdvCliente, PdvSaleItem
    from app.models.inventory import Item, Supplier
    Base.metadata.create_all(factory.kw['bind'], tables=[m.__table__ for m in (Cliente, PdvCliente, Supplier, Item, PdvSale, PdvSaleItem)])
    with factory(info={'notification_events': True}) as db:
        sale = PdvSale(id=uuid.uuid4(), vendedor_id=uid, status='completed', notas='Local fixture only')
        db.add(sale)
        db.commit()
        assert db.get(PdvSale, sale.id)
        notice = db.query(Notification).one()
        assert notice.title.startswith('Venda #') and notice.title.endswith(' concluída')
        assert notice.body == 'Lucas fixture concluiu uma venda. Abra o sistema para conferir.'
