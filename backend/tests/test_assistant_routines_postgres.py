"""Default revisions serialize both first publication and later updates on PostgreSQL."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from test_assistant_routines import DEFAULTS
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.access import AuditEvent
from app.models.assistant import AssistantKnowledge
from app.models.usuario import UsuarioRole
from app.services import assistant_routines as routines


@pytest.mark.parametrize('initial_revision', [0, 1])
def test_competing_saves_cannot_overwrite_another_confirmed_revision(pg, initial_revision):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in
                             (Usuario, Vendedor, AssistantKnowledge, AuditEvent)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    user_id = uuid.uuid4()
    inserted, release, competing = Event(), Event(), Event()
    with factory() as db:
        db.add(Usuario(id=user_id, nome='Owner fixture', email='lucas@eleven.com',
                       senha_hash='unused', role=UsuarioRole.ADMIN))
        db.flush()
        if initial_revision:
            routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=0)
        db.commit()

    def first():
        with factory() as db:
            routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=initial_revision)
            inserted.set()
            assert release.wait(timeout=10)
            db.commit()

    def second():
        competing.set()
        with factory() as db:
            with pytest.raises(HTTPException) as conflict:
                routines.save_routine(db, {'active': False}, user_id=user_id,
                                      expected_revision=initial_revision)
            assert conflict.value.status_code == 409
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
            saved = routines.get_routine(db)
            assert saved['revision'] == initial_revision + 1 and saved['active'] is True
            assert db.query(AssistantKnowledge).count() == 1
            assert db.query(AuditEvent).count() == initial_revision + 1
    finally:
        release.set()
        isolated.dispose()
