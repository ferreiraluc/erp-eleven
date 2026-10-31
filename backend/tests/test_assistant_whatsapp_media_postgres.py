"""Aggregate media quotas must hold across concurrent PostgreSQL transactions."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from test_assistant_workflows import pdf_bytes
from app.database import Base
from app.models.usuario import Usuario
from app.models.vendedor import Vendedor
from app.models.assistant_whatsapp_media import WhatsAppMedia
from app.services import assistant_whatsapp_media as media


@pytest.mark.parametrize("quota", ["USER_BYTES", "GLOBAL_BYTES"])
def test_quota_serializes_competing_media_ingestion(pg, monkeypatch, quota):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, WhatsAppMedia)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    first_user, second_user = uuid.uuid4(), uuid.uuid4()
    payload = pdf_bytes()
    monkeypatch.setattr(media, quota, len(payload))
    inserted, release, competing = Event(), Event(), Event()
    with factory() as db:
        db.add_all([Usuario(id=user, nome="Fixture", email=f"{user}@example.test", senha_hash="unused")
                    for user in (first_user, second_user)])
        db.commit()

    def first():
        with factory() as db:
            media.ingest_media(db, user_id=first_user, conversation_id="120363000000001@g.us",
                message_external_id="first", content=payload, mime_type="application/pdf")
            inserted.set()
            assert release.wait(timeout=10)
            db.commit()

    def second():
        competing.set()
        with factory() as db:
            with pytest.raises(ValueError, match="Limite temporário"):
                media.ingest_media(db, user_id=first_user if quota == "USER_BYTES" else second_user,
                    conversation_id="120363000000001@g.us", message_external_id="second",
                    content=payload, mime_type="application/pdf")
            db.rollback()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            original = executor.submit(first)
            assert inserted.wait(timeout=5)
            contender = executor.submit(second)
            assert competing.wait(timeout=5)
            try:
                assert not contender.done()
            finally:
                release.set()
            original.result(timeout=10)
            contender.result(timeout=10)
        with factory() as db:
            assert db.query(WhatsAppMedia).count() == 1
            assert db.query(sa.func.sum(WhatsAppMedia.byte_size)).scalar() == len(payload)
    finally:
        release.set()
        isolated.dispose()
