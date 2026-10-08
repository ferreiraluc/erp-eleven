import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).parents[2] / 'tools/operations/recovery.py'
spec = importlib.util.spec_from_file_location('recovery', path)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def test_restore_refuses_remote_even_with_local_database_name():
    with pytest.raises(ValueError):
        recovery.connection_env('postgresql://u:p@production.example/sre_restore_test', local_only=True)


def test_environment_cannot_redirect_local_restore(monkeypatch):
    monkeypatch.setenv('PGHOSTADDR', '203.0.113.10')
    monkeypatch.setenv('PGSERVICE', 'production')
    env = recovery.connection_env('postgresql://u:p@127.0.0.1:55439/postgres?hostaddr=203.0.113.10', local_only=True)
    assert env['PGHOST']=='127.0.0.1' and env['PGPORT']=='55439'
    assert 'PGHOSTADDR' not in env and 'PGSERVICE' not in env


def test_remote_backup_requires_verified_tls():
    env = recovery.connection_env('postgresql://u:p@remote.example/erp?sslmode=disable')
    assert env['PGSSLMODE']=='verify-full' and env['PGSSLROOTCERT']=='system'


def test_backups_reject_public_directory(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError): recovery.private_directory(tmp_path)
