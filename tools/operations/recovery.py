#!/usr/bin/env python3
"""Encrypted PostgreSQL backup; restore only to a new disposable local database.

Uses pg_dump/pg_restore and age. No application imports, workers or provider calls.
Run with backend/venv/bin/python. See docs/OPERACAO.md for key custody and retention.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from dotenv import dotenv_values
import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url


def connection_env(raw_url, *, local_only=False):
    url = make_url(raw_url)
    if url.get_backend_name() not in ('postgres', 'postgresql'):
        raise ValueError('Only PostgreSQL is supported')
    if local_only and url.host not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Restore target must be a disposable localhost server')
    # Discard inherited PG* options: hostaddr/service must not override the target.
    env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
    if not url.host or not url.database or not url.username:
        raise ValueError('Database host, name and user are required')
    env.update(PGHOST=url.host, PGPORT=str(url.port or 5432), PGDATABASE=url.database,
               PGUSER=url.username, PGPASSWORD=url.password or '', PGCONNECT_TIMEOUT='10',
               PGAPPNAME='eleven-recovery')
    if not local_only and url.host not in ('localhost', '127.0.0.1', '::1'):
        # Refuse an unverified remote endpoint, even if the URL says sslmode=require.
        env.update(PGSSLMODE='verify-full', PGSSLROOTCERT='system')
    else:
        env['PGSSLMODE'] = 'disable'
    return env


def connect(env, **kwargs):
    return psycopg2.connect(host=env['PGHOST'], port=env['PGPORT'], dbname=env['PGDATABASE'],
                            user=env['PGUSER'], password=env['PGPASSWORD'],
                            sslmode=env['PGSSLMODE'], connect_timeout=10, **kwargs)


def run(command, **kwargs):
    # Never expose a provider's error text or database content through exceptions.
    result = subprocess.run(command, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{Path(command[0]).name} failed (exit {result.returncode})')
    return result


def private_directory(path):
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_mode & 0o077:
        raise ValueError('Backup directory must have mode 0700')
    return path


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backup(args):
    started = time.monotonic()
    values = dotenv_values(args.env_file)
    env = connection_env(values.get('DATABASE_URL') or '')
    folder = private_directory(args.output_dir)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = folder / f'eleven-{stamp}-{uuid.uuid4().hex[:8]}.dump.age'
    partial = output.with_suffix('.partial')
    try:
        with partial.open('xb') as encrypted, tempfile.TemporaryFile() as errors:
            os.chmod(partial, 0o600)
            dump = subprocess.Popen(['pg_dump', '--format=custom', '--no-owner', '--no-privileges',
                                     '--lock-wait-timeout=10000'], env=env, stdout=subprocess.PIPE, stderr=errors)
            try:
                encrypted_result = subprocess.run(['age', '--encrypt', '--recipient', args.recipient],
                                                  stdin=dump.stdout, stdout=encrypted, stderr=subprocess.PIPE, timeout=1800)
                dump.stdout.close()
                code = dump.wait(timeout=1800)
                if code or encrypted_result.returncode:
                    raise RuntimeError('Backup/encryption failed; no complete backup was published')
            finally:
                if dump.poll() is None:
                    dump.kill()
                    dump.wait()
        if partial.stat().st_size < 100:
            raise RuntimeError('Empty backup')
        partial.rename(output)
    finally:
        partial.unlink(missing_ok=True)
    manifest = dict(archive=output.name, created_at=datetime.now(timezone.utc).isoformat(),
                    bytes=output.stat().st_size, sha256=sha256(output),
                    seconds=round(time.monotonic()-started, 2), encrypted=True, restore_verified=False)
    output.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n')
    os.chmod(output.with_suffix('.json'), 0o600)
    print(json.dumps(dict(path=str(output), **manifest)))


def restore(args):
    started = time.monotonic()
    env = connection_env(os.environ.get('SRE_LOCAL_DATABASE_URL', ''), local_only=True)
    archive = args.archive.expanduser().resolve()
    identity = args.identity.expanduser().resolve()
    if identity.stat().st_mode & 0o077:
        raise ValueError('Private identity must have mode 0600')
    manifest_path = archive.with_suffix('.json')
    manifest = json.loads(manifest_path.read_text())
    if manifest['sha256'] != sha256(archive):
        raise ValueError('Backup checksum mismatch')
    target = 'sre_restore_' + uuid.uuid4().hex
    created = False
    admin = connect(env)
    admin.autocommit = True
    try:
        # Authenticate the entire encrypted file before creating/restoring any DB.
        with tempfile.TemporaryDirectory(prefix='eleven-restore-') as temporary:
            clear = Path(temporary) / 'restore.dump'
            with clear.open('xb') as out:
                os.chmod(clear, 0o600)
                run(['age', '--decrypt', '--identity', str(identity), str(archive)], stdout=out)
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(target)))
                created = True
            target_env = dict(env, PGDATABASE=target)
            run(['pg_restore', '--dbname', target, '--no-owner', '--no-privileges', '--exit-on-error', str(clear)],
                env=target_env, stdout=subprocess.DEVNULL)
            with closing(connect(target_env)) as restored, restored:
                with restored.cursor() as cursor:
                    cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
                    counts = {}
                    for (table,) in cursor.fetchall():
                        cursor.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table)))
                        counts[table] = cursor.fetchone()[0]
                    cursor.execute('SELECT version_num FROM alembic_version')
                    versions = [row[0] for row in cursor.fetchall()]
                    cursor.execute("SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace AND NOT convalidated")
                    unvalidated = cursor.fetchone()[0]
            if not counts or not versions or unvalidated:
                raise RuntimeError('Restoration needs review: schema/constraints incomplete')
            report = dict(restore_verified=True, verified_at=datetime.now(timezone.utc).isoformat(),
                          seconds=round(time.monotonic()-started, 2), tables=len(counts), row_counts=counts,
                          alembic_versions=versions, unvalidated_constraints=unvalidated,
                          target='new disposable localhost database', application_started=False)
            manifest.update(report)
            manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
            print(json.dumps({k:v for k,v in report.items() if k!='row_counts'}))
    finally:
        if created:
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(target)))
        admin.close()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    create = commands.add_parser('backup')
    create.add_argument('--env-file', type=Path, required=True)
    create.add_argument('--recipient', required=True, help='Public age1... recipient, never the private key')
    create.add_argument('--output-dir', type=Path, required=True)
    check = commands.add_parser('verify-restore')
    check.add_argument('--archive', type=Path, required=True)
    check.add_argument('--identity', type=Path, required=True)
    args = parser.parse_args()
    try:
        (backup if args.operation=='backup' else restore)(args)
    except Exception as exc:
        # Exception messages from drivers can contain usernames or database data.
        print(f'Recovery operation failed ({type(exc).__name__}); no success claimed.', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
