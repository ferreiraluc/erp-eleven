"""Durable synchronization with a database lease, isolated from assistant requests."""
from datetime import timedelta
from hashlib import sha256
import logging
import uuid
from sqlalchemy import or_
from ..database import SessionLocal
from ..models.assistant import utcnow
from ..models.sales_bi import SalesBIConfig, SalesBIWorkbook
from .sales_bi_onedrive import OneDriveReader, SourceError
from .sales_bi_parser import parse_workbook, WorkbookError, PARSER_VERSION

log = logging.getLogger(__name__)
INTERVAL = timedelta(minutes=15)
LEASE = timedelta(minutes=30)


def claim(session_factory=SessionLocal):
    now, token = utcnow(), str(uuid.uuid4())
    with session_factory() as db:
        updated = db.query(SalesBIConfig).filter(
            SalesBIConfig.id == 1, SalesBIConfig.enabled.is_(True),
            or_(SalesBIConfig.lease_until.is_(None), SalesBIConfig.lease_until < now),
            or_(SalesBIConfig.next_sync_at.is_(None), SalesBIConfig.next_sync_at <= now,
                SalesBIConfig.requested_at > SalesBIConfig.started_at),
        ).update({'lease_token': token, 'lease_until': now + LEASE, 'started_at': now}, synchronize_session=False)
        db.commit()
        if not updated:
            return None
        c = db.get(SalesBIConfig, 1)
        return {k: getattr(c, k) for k in ('current_url', 'archive_url', 'archive_root', 'current_year', 'current_month')} | {'token': token}


def sync_once(session_factory=SessionLocal, reader_factory=OneDriveReader, stop=None):
    config = claim(session_factory)
    if not config:
        return False
    token = config.pop('token')
    errors = []
    reader = None
    def owned(db):
        c = db.query(SalesBIConfig).filter_by(id=1, lease_token=token).with_for_update().first()
        if not c:
            raise SourceError('Sincronização substituída por outra execução.')
        c.lease_until = utcnow() + LEASE
        return c

    def ingest(key, kind, filename, version, download, year=None, month=None):
        now = utcnow()
        with session_factory() as db:
            owned(db)
            row = db.get(SalesBIWorkbook, key)
            if not row:
                row = SalesBIWorkbook(id=key, kind=kind, filename=filename)
                db.add(row)
            row.filename = filename
            row.active = True
            row.checked_at = now
            if kind == 'archive' and row.snapshot and not row.error and row.remote_version == version and row.parser_version == PARSER_VERSION:
                db.commit()
                return
            db.commit()
        try:
            data = download()
            snapshot = parse_workbook(data, year=year, month=month, current=kind == 'current')
            digest = sha256(data).hexdigest()
        except Exception as exc:
            message = str(exc) if isinstance(exc, WorkbookError) else 'Falha ao ler a planilha. A última leitura válida foi preservada.'
            with session_factory() as db:
                owned(db)
                row = db.get(SalesBIWorkbook, key)
                row.error = message[:500]
                db.commit()
            errors.append(f'{filename}: {message}')
            return
        with session_factory() as db:
            owned(db)
            row = db.get(SalesBIWorkbook, key)
            row.snapshot, row.year, row.month = snapshot, snapshot['year'], snapshot['month']
            row.content_hash, row.remote_version, row.parser_version = digest, version, PARSER_VERSION
            row.synced_at, row.error = now, None
            db.commit()

    try:
        reader = reader_factory(config['current_url'], config['archive_url'], config['archive_root'])
        current_id = sha256(('current:' + config['current_url']).encode()).hexdigest()
        ingest(current_id, 'current', 'VendasGeral.xlsx', None, reader.current, config['current_year'], config['current_month'])
        files = reader.archive()
        seen = {current_id}
        for f in files:
            if stop and stop.is_set():
                raise SourceError('Leitura interrompida; será retomada automaticamente.')
            key = sha256(('archive:' + f['remote_id']).encode()).hexdigest()
            seen.add(key)
            if not f['month']:
                # Keep an explicit error in source status, rather than assigning a guessed period.
                def invalid_month():
                    raise WorkbookError('O nome do arquivo precisa identificar o mês, por exemplo Setembro-Faturamento.xlsx.')
                download = invalid_month
            else:
                download = lambda f=f: reader.download(f['path'])
            ingest(key, 'archive', f['filename'], f['version'], download, f['year'], f['month'])
        with session_factory() as db:
            owned(db)
            # Only retire removed sources after a COMPLETE directory listing.
            db.query(SalesBIWorkbook).filter(~SalesBIWorkbook.id.in_(seen)).update({'active': False}, synchronize_session=False)
            db.commit()
    except Exception as exc:
        errors.append(str(exc) if isinstance(exc, WorkbookError) else 'Falha de sincronização. A última leitura válida foi preservada.')
    finally:
        if reader:
            reader.close()
        with session_factory() as db:
            c = db.query(SalesBIConfig).filter_by(id=1, lease_token=token).first()
            if c:
                c.finished_at = utcnow()
                c.next_sync_at = utcnow() + (timedelta(minutes=2) if errors else INTERVAL)
                c.lease_until = None
                c.lease_token = None
                c.last_error = f'{len(errors)} fonte(s) com falha. ' + errors[0][:350] if errors else None
                db.commit()
    log.info('Sales BI sync completed; source errors=%d', len(errors))
    return True


def main(stop):
    while not stop.is_set():
        try:
            sync_once(stop=stop)
        except Exception:
            # Never log source URLs or raw HTTP exceptions (share links are bearer access).
            log.error('Sales BI worker could not synchronize; will retry.')
        stop.wait(15)
