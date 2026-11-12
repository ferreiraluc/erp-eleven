"""Real PostgreSQL transaction/visibility checks using disposable schemas only."""
from app.models.notification import Notification, NotificationRecipient, NotificationRule
from app.models.usuario import Usuario
from app.services import notifications
from app.services.notification_context import inbox_sale_visibility
from test_access_postgres import pg
from test_notification_events import factory, sale, users


def test_reseller_summaries_follow_sale_commit_and_rollback_and_sql_scope(factory):
    with factory() as db:
        ids = users(db)
        reseller = db.get(Usuario, ids['Other'])
        reseller.access_profile = 'reseller'
        notifications.ensure_defaults(db)
        db.get(NotificationRule, 'sale_completed').user_ids = [str(ids['Lucas']), str(ids['Other'])]
        db.commit()

        sale(db)
        db.rollback()
        assert db.query(Notification).count() == 0
        row = sale(db)
        row.total_gs, row.usd_rate_gs = 480000, 6000
        db.commit()
        assert db.query(Notification).count() == 2
        summary = db.query(Notification).filter(inbox_sale_visibility(db, reseller)).one()
        assert summary.entity_type == 'pdv_sale_summary'
        assert summary.title == 'Venda U$ 80 concluída'
        assert summary.action_path is None
        assert db.query(NotificationRecipient).filter_by(notification_id=summary.id).one().user_id == reseller.id
        assert db.query(Notification).filter_by(entity_type='pdv_sale').one().action_path == f'/vendas-pdv?sale_id={row.id}'

        notifications.emit_event(db, 'sale_completed', context={}, user_ids=[ids['Lucas']],
            dedupe_key=f'sale-completed:{row.id}', entity_type='pdv_sale', entity_id=row.id)
        db.commit()
        assert db.query(Notification).count() == 2
        reseller.access_profile = 'standard'
        db.commit()
        assert db.query(Notification).filter(inbox_sale_visibility(db, reseller)).count() == 0
