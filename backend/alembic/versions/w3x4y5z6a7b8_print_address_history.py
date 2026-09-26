"""Recover address history for legacy A4 jobs without creating or reprinting jobs."""
import uuid
from alembic import op
import sqlalchemy as sa

revision = 'w3x4y5z6a7b8'
down_revision = 'v2w3x4y5z6a7'
branch_labels = None
depends_on = None

# Frozen address identity rules: later application changes must not alter this backfill.
import hashlib
import json
import re
import unicodedata


def normalized(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold()) if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^\w\s]', ' ', value).split())


def digits(value):
    return re.sub(r'\D', '', str(value or ''))


def fingerprint(data):
    country = normalized(data.get('pais'))
    name = normalized(data.get('nome'))
    street = normalized(' '.join(str(data.get(k) or '') for k in ('endereco','numero','bairro','complemento')))
    street = re.sub(r'\b(?:apartamento|apto|apt|ap)\s+(?=[0-9])', 'apartamento ', street)
    city, state, postcode = normalized(data.get('cidade')), normalized(data.get('estado')), digits(data.get('cep'))
    # In Paraguay a city/telephone can be the entire delivery address. Blank or
    # name-only print blocks must never become a shared address for unrelated jobs.
    phone = digits(data.get('telefone')) if not street else ''
    if not name or not any((street, city, postcode, phone)):
        return None
    identity = [country,name,street,city,state,postcode,phone]
    return hashlib.sha256(json.dumps(identity,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def print_matches_saved(printed, saved):
    """A BR print block may omit the district, but never the delivery location.

    Compare the actual street/number/complement as well as name, city and CEP.
    The caller must require a unique candidate; a name alone is never enough.
    """
    if normalized(printed.get('pais')) != 'br' or normalized(saved.get('pais')) != 'br':
        return False
    for key in ('nome', 'cidade', 'estado'):
        if not normalized(printed.get(key)) or normalized(printed.get(key)) != normalized(saved.get(key)):
            return False
    if not digits(printed.get('cep')) or digits(printed.get('cep')) != digits(saved.get('cep')):
        return False
    def street(data, district=True):
        keys = ('endereco', 'numero', 'bairro', 'complemento') if district else ('endereco', 'numero', 'complemento')
        value = normalized(' '.join(str(data.get(k) or '') for k in keys))
        return re.sub(r'\b(?:apartamento|apto|apt|ap)\s+(?=[0-9])', 'apartamento ', value)
    printed_street = street(printed)
    if not printed_street or not any(c.isdigit() for c in printed_street):
        return False
    return printed_street == street(saved) or (
        not printed.get('bairro') and printed_street == street(saved, district=False))


ADDRESS_FIELDS = ('pais','nome','telefone','cpf','endereco','numero','bairro','complemento','cidade','estado','cep','email')


def backfill(bind):
    addresses = sa.table('saved_addresses', sa.column('id',sa.Uuid()), sa.column('label',sa.String()),
        sa.column('data',sa.JSON()), sa.column('created_by',sa.Uuid()), sa.column('active',sa.Boolean()),
        sa.column('version',sa.Integer()), sa.column('updated_at',sa.DateTime(timezone=True)),
        sa.column('dedup_key',sa.String()), sa.column('merged_into_id',sa.Uuid()))
    jobs = sa.table('print_jobs', sa.column('id',sa.Uuid()), sa.column('snapshot',sa.JSON()),
        sa.column('address_id',sa.Uuid()), sa.column('source',sa.String()), sa.column('user_id',sa.Uuid()),
        sa.column('created_at',sa.DateTime(timezone=True)))
    roots = [dict(row) for row in bind.execute(sa.select(addresses).where(addresses.c.merged_into_id.is_(None))).mappings()]
    counts = {'linked':0, 'created':0, 'skipped':0}
    for job in bind.execute(sa.select(jobs).where(jobs.c.address_id.is_(None),jobs.c.source.in_(('bot','erp')))
                            .order_by(jobs.c.created_at,jobs.c.id)).mappings():
        snapshot = job['snapshot'] or {}
        raw = snapshot.get('editor') or snapshot.get('endereco') or {}
        data = {key:str(raw.get(key) or '') for key in ADDRESS_FIELDS}
        key = fingerprint(data)
        if not key or data['pais'] not in ('BR','PY'):
            counts['skipped'] += 1
            continue
        candidates = [r for r in roots if fingerprint(r['data']) == key]
        if not candidates:
            candidates = [r for r in roots if print_matches_saved(data,r['data'])]
        if candidates:
            before, after = digits(candidates[0]['data'].get('cpf')), digits(data.get('cpf'))
            if len(candidates) != 1 or (before and after and len(set(before))>1 and len(set(after))>1 and before!=after):
                counts['skipped'] += 1
                continue
            target = candidates[0]
        else:
            target = dict(id=uuid.uuid4(),label=data['nome'],data=data,created_by=job['user_id'],
                active=True,version=1,updated_at=job['created_at'],dedup_key=key,merged_into_id=None)
            bind.execute(addresses.insert().values(**target))
            roots.append(target)
            counts['created'] += 1
        bind.execute(jobs.update().where(jobs.c.id==job['id'],jobs.c.address_id.is_(None)).values(address_id=target['id']))
        counts['linked'] += 1
    return counts


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text('SELECT pg_advisory_xact_lock(711005)'))
        bind.execute(sa.text('LOCK TABLE saved_addresses, print_jobs IN SHARE ROW EXCLUSIVE MODE'))
    backfill(bind)


def downgrade():
    # Recovered historical associations remain valid in the preceding version.
    # Do not destroy addresses that may have been reused since the backfill.
    pass
