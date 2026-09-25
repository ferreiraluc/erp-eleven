"""Treat numbered apartment abbreviations as the same delivery location."""
import hashlib
import json
import re
import unicodedata
from alembic import op
import sqlalchemy as sa

revision='u1v2w3x4y5z6'
down_revision='t0u1v2w3x4y5'
branch_labels=None
depends_on=None


def normalized(value):
    value=''.join(c for c in unicodedata.normalize('NFKD',str(value or '').casefold()) if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^\w\s]',' ',value).split())


def digits(value):
    return re.sub(r'\D','',str(value or ''))


def fingerprint(data, apartments=True):
    country,name=normalized(data.get('pais')),normalized(data.get('nome'))
    street=normalized(' '.join(str(data.get(k) or '') for k in ('endereco','numero','bairro','complemento')))
    if apartments:street=re.sub(r'\b(?:apartamento|apto|apt|ap)\s+(?=[0-9])','apartamento ',street)
    city,state,postcode=normalized(data.get('cidade')),normalized(data.get('estado')),digits(data.get('cep'))
    phone=digits(data.get('telefone')) if not street else ''
    if not name or not any((street,city,postcode,phone)):return None
    return hashlib.sha256(json.dumps([country,name,street,city,state,postcode,phone],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def consolidate(bind, apartments=True):
    table=sa.table('saved_addresses',sa.column('id',sa.Uuid()),sa.column('data',sa.JSON()),
        sa.column('cliente_id',sa.Uuid()),sa.column('pdv_cliente_id',sa.Uuid()),sa.column('active',sa.Boolean()),
        sa.column('version',sa.Integer()),sa.column('updated_at',sa.DateTime(timezone=True)),
        sa.column('dedup_key',sa.String()),sa.column('merged_into_id',sa.Uuid()))
    # Earlier aliases stay intact. Merge only current roots, preserving redirect chains.
    roots=list(bind.execute(sa.select(table).where(table.c.merged_into_id.is_(None))).mappings())
    bind.execute(table.update().where(table.c.merged_into_id.is_(None)).values(dedup_key=None))
    groups={}
    for row in roots:
        key=fingerprint(row['data'],apartments)
        if key:groups.setdefault(key,[]).append(row)
    for key,members in groups.items():
        members.sort(key=lambda r:(bool(r['cliente_id'] or r['pdv_cliente_id']),sum(bool(v) for v in r['data'].values()),r['updated_at'],str(r['id'])),reverse=True)
        target=members[0]
        data=dict(target['data'])
        active=target['active']
        linked=(target['cliente_id'],target['pdv_cliente_id'])
        for duplicate in members[1:]:
            doc,other=digits(data.get('cpf')),digits(duplicate['data'].get('cpf'))
            other_link=(duplicate['cliente_id'],duplicate['pdv_cliente_id'])
            if doc and other and doc!=other or any(linked) and any(other_link) and linked!=other_link:continue
            for field,value in duplicate['data'].items():
                if value and not data.get(field):data[field]=value
            active=active or duplicate['active']
            bind.execute(table.update().where(table.c.id==duplicate['id']).values(
                merged_into_id=target['id'],active=False,version=duplicate['version']+1))
        bind.execute(table.update().where(table.c.id==target['id']).values(
            dedup_key=key,data=data,active=active,version=target['version']+1))


def upgrade():
    bind=op.get_bind()
    if bind.dialect.name=='postgresql':bind.execute(sa.text('LOCK TABLE saved_addresses IN SHARE ROW EXCLUSIVE MODE'))
    consolidate(bind)


def downgrade():
    # Keep historical redirects; only restore the earlier address identity format.
    consolidate(op.get_bind(),apartments=False)
