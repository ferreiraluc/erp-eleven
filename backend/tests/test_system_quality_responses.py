"""A supplied notification response resolves context without editing the sale."""
import uuid
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.notification import Notification, NotificationRecipient
from app.models.pdv import PdvSale, PdvSaleItem
from app.models.cliente import Cliente
from app.models.address_book import SavedAddress
from app.services import quality_checks
from test_access_postgres import pg
from test_system_quality import MODELS, MOMENT, factory


def check_responses(factory):
    with factory() as db:
        user = db.query(Usuario).first()
        identities = [uuid.uuid4() for _ in range(3)]
        for index, identity in enumerate(identities):
            db.add(PdvSale(id=identity, vendedor_id=user.id, status='completed', notas=None, created_at=MOMENT))
            db.flush()
            db.add(PdvSaleItem(sale_id=identity, item_name='Synthetic manual item', is_avulso=True,
                              quantity=1, unit_price_gs=10, total_gs=10))
            notice = Notification(id=uuid.uuid4(), title='Synthetic context request', body='Private fixture body',
                                  category='sales', severity='warning', requires_response=True,
                                  dedupe_key=('unrelated:' if index == 2 else 'sale-avulso:') + str(identity))
            db.add(notice)
            db.flush()
            db.add(NotificationRecipient(notification_id=notice.id, user_id=user.id, read_at=MOMENT,
                acknowledged_at=MOMENT if index != 1 else None,
                acknowledgement_note='Private reason never sent to AI' if index != 1 else None))
        db.commit()
    report = quality_checks.collect(factory, MOMENT, {'notifications': 'online'})
    assert report['coverage']['sales'] == {'checked': 3, 'complete': True, 'window': 'last_24_hours'}
    assert report['counters']['sale_avulso_without_reason'] == 2
    assert {entry['entity_id'] for entry in report['findings'] if entry['key'] == 'sale_avulso_without_reason'} == {
        str(identities[1]), str(identities[2])}
    assert 'Private' not in str(report)
    with factory() as db:
        assert all(row.notas is None for row in db.query(PdvSale))


def test_supplied_response_resolves_only_its_sale_and_reading_alone_is_not_a_reason(factory):
    check_responses(factory)


def test_supplied_response_is_also_respected_in_postgresql(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in MODELS])
        factory = sessionmaker(bind=isolated, autoflush=False, expire_on_commit=False)
        with factory() as db:
            db.add(Usuario(id=uuid.uuid4(), nome='Synthetic Lucas', email='lucas@eleven.com',
                           senha_hash='unused', role=UsuarioRole.ADMIN))
            db.commit()
        check_responses(factory)
    finally:
        isolated.dispose()


def test_duplicate_probe_caps_are_visible_as_incomplete_coverage(factory):
    with factory() as db:
        for index in range(7):
            db.add(Cliente(nome='Synthetic Full Name', telefone='5550000000',
                           updated_at=MOMENT if index == 0 else MOMENT - timedelta(days=2)))
        for index in range(12):
            db.add(SavedAddress(label='Fixture', created_by=db.query(Usuario.id).first()[0], dedup_key=f'fixture-{index}',
                data={'nome': 'Synthetic Full Name', 'pais': 'PY', 'cidade': 'Fixture', 'endereco': f'Street {index}'},
                updated_at=MOMENT))
        db.commit()
    report = quality_checks.collect(factory, MOMENT, {'notifications': 'online'})
    assert report['coverage']['customers']['checked'] == 1
    assert report['coverage']['customers']['complete'] is False
    assert report['counters']['customer_duplicate_candidate'] == 5
    assert report['coverage']['addresses']['checked'] == 12
    assert report['coverage']['addresses']['complete'] is False
