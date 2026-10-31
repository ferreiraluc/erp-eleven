"""The reviewed historical freight plan also executes on PostgreSQL."""
from test_access_postgres import pg
from test_superfrete_tracking_concurrency_postgres import shipping_pg
from app.database import Base
from app.models import Cliente, Rastreamento, Usuario
from app.models.access import AuditEvent
from app.services.customer_reconciliation import preview_customer_links, apply_customer_links


def test_freight_history_confirmation_is_atomic_and_idempotent_on_postgres(shipping_pg):
    factory, engine, ids = shipping_pg
    uid, cid, _, rid, _ = ids
    Base.metadata.create_all(engine, tables=[AuditEvent.__table__])
    with factory() as db:
        customer, actor = db.get(Cliente, cid), db.get(Usuario, uid)
        before = db.get(Rastreamento, rid).destinatario
        preview = preview_customer_links(db, customer)
        assert preview['counts']['tracking'] == 1
        assert preview['items'][0]['reason'] == 'explicit_freight_customer'
        assert db.get(Rastreamento, rid).cliente_id is None
        applied = apply_customer_links(db, customer, preview['token'], actor)
        db.commit()
        assert applied['linked']['tracking'] == 1
        assert db.get(Rastreamento, rid).cliente_id == cid
        assert db.get(Rastreamento, rid).destinatario == before
        again = apply_customer_links(db, customer, preview['token'], actor)
        assert again['already_applied']
        assert db.query(AuditEvent).filter_by(action='customer_history_reconciled').count() == 1
