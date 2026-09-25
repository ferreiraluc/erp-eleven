"""Consolidate duplicate recipient addresses, preserving every source ID and operation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision='t0u1v2w3x4y5'
down_revision='s9t0u1v2w3x4'
branch_labels=None
depends_on=None

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
    city, state, postcode = normalized(data.get('cidade')), normalized(data.get('estado')), digits(data.get('cep'))
    # In Paraguay a city/telephone can be the entire delivery address. Blank or
    # name-only print blocks must never become a shared address for unrelated jobs.
    phone = digits(data.get('telefone')) if not street else ''
    if not name or not any((street, city, postcode, phone)):
        return None
    identity = [country,name,street,city,state,postcode,phone]
    return hashlib.sha256(json.dumps(identity,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def upgrade():
    op.add_column('saved_addresses',sa.Column('dedup_key',sa.String(64)))
    op.add_column('saved_addresses',sa.Column('merged_into_id',UUID(as_uuid=True),sa.ForeignKey('saved_addresses.id')))
    op.create_index('ix_saved_addresses_merged_into_id','saved_addresses',['merged_into_id'])
    bind=op.get_bind()
    # Block old-version writers during backfill; keep the unique index creation atomic.
    if bind.dialect.name=='postgresql':bind.execute(sa.text('LOCK TABLE saved_addresses IN SHARE ROW EXCLUSIVE MODE'))
    consolidate(bind)
    op.create_index('uq_saved_address_identity','saved_addresses',['dedup_key'],unique=True,
        postgresql_where=sa.text('merged_into_id IS NULL AND dedup_key IS NOT NULL'),
        sqlite_where=sa.text('merged_into_id IS NULL AND dedup_key IS NOT NULL'))
    op.create_index('ix_freight_orders_address_id','freight_orders',['address_id'])
    op.create_index('ix_print_jobs_address_id','print_jobs',['address_id'])


def consolidate(bind):
    table=sa.table('saved_addresses',sa.column('id',sa.Uuid()),sa.column('label',sa.String()),
        sa.column('data',sa.JSON()),sa.column('cliente_id',sa.Uuid()),sa.column('pdv_cliente_id',sa.Uuid()),
        sa.column('active',sa.Boolean()),sa.column('version',sa.Integer()),sa.column('updated_at',sa.DateTime(timezone=True)),
        sa.column('dedup_key',sa.String()),sa.column('merged_into_id',sa.Uuid()))
    rows=list(bind.execute(sa.select(table)).mappings())
    groups={}
    for row in rows:
        key=fingerprint(row['data'])
        if key:groups.setdefault(key,[]).append(row)
    canonical={}
    ambiguous=set()
    for key,members in groups.items():
        members.sort(key=lambda r:(bool(r['cliente_id'] or r['pdv_cliente_id']),sum(bool(v) for v in r['data'].values()),r['updated_at'],str(r['id'])),reverse=True)
        target=members[0]
        canonical[key]=target['id']
        bind.execute(table.update().where(table.c.id==target['id']).values(dedup_key=key))
        doc=digits(target['data'].get('cpf'))
        linked=(target['cliente_id'],target['pdv_cliente_id'])
        active=target['active']
        for duplicate in members[1:]:
            other_doc=digits(duplicate['data'].get('cpf'))
            other_link=(duplicate['cliente_id'],duplicate['pdv_cliente_id'])
            if doc and other_doc and doc!=other_doc or any(linked) and any(other_link) and linked!=other_link:
                ambiguous.add(key)
                continue  # not a proven duplicate; preserve conflicting identities for review
            active=active or duplicate['active']
            bind.execute(table.update().where(table.c.id==duplicate['id']).values(
                merged_into_id=target['id'],active=False,version=duplicate['version']+1))
        if active:bind.execute(table.update().where(table.c.id==target['id']).values(active=True))
    # Recover links for old print snapshots where the same address is unambiguous.
    jobs=sa.table('print_jobs',sa.column('id',sa.Uuid()),sa.column('snapshot',sa.JSON()),sa.column('address_id',sa.Uuid()))
    for row in bind.execute(sa.select(jobs.c.id,jobs.c.snapshot).where(jobs.c.address_id.is_(None))).mappings():
        snapshot=row['snapshot'] or {}
        key=fingerprint(snapshot.get('editor') or snapshot.get('endereco') or {})
        if key in canonical and key not in ambiguous:
            bind.execute(jobs.update().where(jobs.c.id==row['id']).values(address_id=canonical[key]))


def downgrade():
    op.drop_index('ix_print_jobs_address_id',table_name='print_jobs')
    op.drop_index('ix_freight_orders_address_id',table_name='freight_orders')
    op.drop_index('uq_saved_address_identity',table_name='saved_addresses')
    op.execute('UPDATE saved_addresses SET active=true WHERE merged_into_id IS NOT NULL')
    op.drop_index('ix_saved_addresses_merged_into_id',table_name='saved_addresses')
    op.drop_column('saved_addresses','merged_into_id')
    op.drop_column('saved_addresses','dedup_key')
