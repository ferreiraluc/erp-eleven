"""Provisioning saves the authorized preset through the same validated revision path."""
import json
import sys

import pytest

from test_assistant import setup
from test_assistant_routines import owner, DEFAULTS
from app import assistant_setup, database
from app.models.access import AuditEvent
from app.services.assistant_routines import get_routine


def test_setup_applies_once_with_audited_owner_and_expected_revision(owner, monkeypatch, tmp_path, capsys):
    factory, user_id = owner
    monkeypatch.setattr(database, 'SessionLocal', factory)
    path = tmp_path / 'defaults.json'
    path.write_text(json.dumps(DEFAULTS))
    monkeypatch.setattr(sys, 'argv', ['assistant_setup', 'shipping-defaults-set',
                                     '--defaults-file', str(path), '--expected-revision', '0'])
    assistant_setup.main()
    assert json.loads(capsys.readouterr().out) == {'salvo': True, 'revisao': 1, 'ativo': True}
    with factory() as db:
        assert get_routine(db)['package']['weight'] == 1
        event = db.query(AuditEvent).one()
        assert event.user_id == user_id and event.source == 'cli'
    with pytest.raises(SystemExit, match='padrão mudou'):
        assistant_setup.main()
    with factory() as db:
        assert get_routine(db)['revision'] == 1
        assert db.query(AuditEvent).count() == 1


def test_setup_rejects_quantity_in_shared_preset(owner, monkeypatch, tmp_path):
    factory, _ = owner
    monkeypatch.setattr(database, 'SessionLocal', factory)
    path = tmp_path / 'defaults.json'
    path.write_text(json.dumps({**DEFAULTS, 'quantidade': 3}))
    monkeypatch.setattr(sys, 'argv', ['assistant_setup', 'shipping-defaults-set',
                                     '--defaults-file', str(path), '--expected-revision', '0'])
    with pytest.raises(SystemExit, match='Confira o JSON'):
        assistant_setup.main()
    with factory() as db:
        assert get_routine(db) is None
        assert db.query(AuditEvent).count() == 0
