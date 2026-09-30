"""Consolidate BR addresses whose only location difference is a missing district."""
import hashlib
import json
import re
import unicodedata
from alembic import op
import sqlalchemy as sa

revision='y5z6a7b8c9d0'
down_revision='x4y5z6a7b8c9'
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


def consolidate(bind):
    table=sa.table('saved_addresses',sa.column('id',sa.Uuid()),sa.column('data',sa.JSON()),
        sa.column('cliente_id',sa.Uuid()),sa.column('pdv_cliente_id',sa.Uuid()),sa.column('active',sa.Boolean()),
        sa.column('version',sa.Integer()),sa.column('updated_at',sa.DateTime(timezone=True)),
        sa.column('dedup_key',sa.String()),sa.column('merged_into_id',sa.Uuid()))
    roots=list(bind.execute(sa.select(table).where(table.c.merged_into_id.is_(None))).mappings())
    groups={}
    for row in roots:
        d=row['data']
        if normalized(d.get('pais'))!='br' or len(digits(d.get('cep')))!=8:continue
        if not all(normalized(d.get(k)) for k in ('nome','endereco','cidade','estado')):continue
        if not digits(str(d.get('endereco',''))+' '+str(d.get('numero',''))):continue
        groups.setdefault(fingerprint({**d,'bairro':''}),[]).append(row)
    for members in groups.values():
        districts={normalized(r['data'].get('bairro')) for r in members}
        if len(members)<2 or '' not in districts or len(districts)!=2:continue
        docs={digits(r['data'].get('cpf')) for r in members if len(set(digits(r['data'].get('cpf'))))>1}
        links={(r['cliente_id'],r['pdv_cliente_id']) for r in members if r['cliente_id'] or r['pdv_cliente_id']}
        if len(docs)>1 or len(links)>1:continue
        members.sort(key=lambda r:(bool(r['data'].get('bairro')),bool(r['cliente_id'] or r['pdv_cliente_id']),r['updated_at'],str(r['id'])),reverse=True)
        target=members[0];data=dict(target['data'])
        for duplicate in members[1:]:
            for k,v in duplicate['data'].items():
                if v and not data.get(k):data[k]=v
            bind.execute(table.update().where(table.c.id==duplicate['id']).values(merged_into_id=target['id'],dedup_key=None,active=False,version=duplicate['version']+1))
        link=next(iter(links),(None,None))
        bind.execute(table.update().where(table.c.id==target['id']).values(data=data,dedup_key=fingerprint(data),
            active=any(r['active'] for r in members),cliente_id=link[0],pdv_cliente_id=link[1],version=target['version']+1))


def upgrade():
    bind=op.get_bind()
    if bind.dialect.name=='postgresql':bind.execute(sa.text('LOCK TABLE saved_addresses IN SHARE ROW EXCLUSIVE MODE'))
    consolidate(bind)


def downgrade():
    # Keep redirect IDs and immutable usage records, including subsequent operations.
    pass
