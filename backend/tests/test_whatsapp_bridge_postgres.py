"""Schema preservation and competing bridge claims on isolated PostgreSQL only."""
import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg, upgrade
from app.config import settings
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.usuario import UsuarioRole
from app.models.assistant import AssistantWhatsAppBridge, AssistantIdentity, AssistantMessage, AssistantDelivery
from app.services import assistant_whatsapp_bridge as bridge


def test_upgrade_preserves_existing_providers_and_no_account_is_enabled(pg):
    engine, schema = pg
    delivery_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.exec_driver_sql(f"SET LOCAL search_path TO {schema}")
        conn.exec_driver_sql("CREATE TABLE usuarios(id uuid PRIMARY KEY)")
        conn.exec_driver_sql("CREATE TABLE assistant_deliveries(id uuid PRIMARY KEY, channel varchar(16), status varchar(20), text text)")
        conn.execute(sa.text("INSERT INTO assistant_deliveries VALUES(:id,'telegram','accepted','Existing history')"), {"id": delivery_id})
        upgrade(conn, "y7h8i9j0k1l2_whatsapp_web_bridge.py")
        assert conn.execute(sa.text("SELECT id,channel,status,text,bridge_claim_key,bridge_id FROM assistant_deliveries")).one() == (
            delivery_id, "telegram", "accepted", "Existing history", None, None)
        assert conn.execute(sa.text("SELECT count(*) FROM assistant_whatsapp_bridges")).scalar() == 0
        assert conn.execute(sa.text("SELECT count(*) FROM assistant_whatsapp_media")).scalar() == 0
    file = Path(__file__).parents[1] / "alembic/versions/y7h8i9j0k1l2_whatsapp_web_bridge.py"
    spec = importlib.util.spec_from_file_location("bridge_test_migration", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match="Preserve"):
        module.downgrade()


def test_competing_claims_and_retries_have_one_delivery(pg, monkeypatch):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(isolated, tables=[m.__table__ for m in (
        Usuario, Vendedor, AssistantWhatsAppBridge, AssistantIdentity, AssistantMessage, AssistantDelivery)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    monkeypatch.setattr(settings, "ASSISTANT_ENABLED", True)
    try:
        with factory() as db:
            user = Usuario(nome="Bridge Fixture", email="bridge@example.test", senha_hash="unused", role=UsuarioRole.ADMIN)
            db.add(user)
            db.flush()
            db.add(AssistantWhatsAppBridge(id="primary", enabled=True, state="connected", token_hash="f" * 64))
            db.add(AssistantIdentity(channel="whatsapp_web", external_id="whatsapp:+5511888888888", user_id=user.id))
            source = AssistantMessage(channel="whatsapp_web", external_id="source", sender_id="whatsapp:+5511888888888",
                conversation_id="5511888888888@s.whatsapp.net", user_id=user.id, text="Consulta", status="done")
            db.add(source)
            db.flush()
            db.add(AssistantDelivery(event_key=f"reply:{source.id}", channel=source.channel,
                destination=source.conversation_id, user_id=user.id, text="Resposta"))
            db.commit()
        def claim(key):
            with factory() as db:
                row = bridge.lock_bridge(db, bridge.bridge_config(db))
                result = bridge.claim(db, row, key)
                db.commit()
                return result
        keys = [uuid.uuid4(), uuid.uuid4()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, keys))
        assert sum(result is not None for result in results) == 1
        chosen = next(result for result in results if result)
        assert claim(uuid.UUID(chosen["claim_key"]))["id"] == chosen["id"]
        with factory() as db:
            assert db.query(AssistantDelivery).filter_by(status="claimed").count() == 1
    finally:
        isolated.dispose()
