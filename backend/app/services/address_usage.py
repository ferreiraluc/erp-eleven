"""Usage history reads the original operations: retries never create extra uses."""
from sqlalchemy import select, literal, union_all, func, case
from ..models.address_book import FreightOrder
from ..models.printing import PrintJob
from ..models.usuario import Usuario
from .address_book import address_family


def usage_query(ids):
    freight=select(FreightOrder.id.label('id'),literal('frete').label('kind'),FreightOrder.created_at.label('created_at'),
        FreightOrder.state.label('status'),literal('SuperFrete').label('source'),Usuario.nome.label('user'),
        FreightOrder.tracking.label('tracking'),FreightOrder.price.label('price'),FreightOrder.payload.label('snapshot'),
        FreightOrder.environment.label('environment'),literal(None).label('finished_at')).join(Usuario,Usuario.id==FreightOrder.user_id).where(FreightOrder.address_id.in_(ids))
    printing=select(PrintJob.id,literal('impressao'),PrintJob.created_at,PrintJob.status,
        PrintJob.source,Usuario.nome,literal(None),literal(None),PrintJob.snapshot,literal(None),PrintJob.finished_at).join(
        Usuario,Usuario.id==PrintJob.user_id).where(PrintJob.address_id.in_(ids),PrintJob.source!='bot_pdf_ephemeral')
    return union_all(freight,printing).subquery()


def usage_stats(db, ids):
    q=usage_query(ids)
    completed=(q.c.kind=='impressao') & (q.c.status=='submitted')
    row=db.execute(select(func.count().label('total'),func.max(func.coalesce(q.c.finished_at,q.c.created_at)).label('last_used_at'),
        func.sum(case((q.c.kind=='frete',1),else_=0)).label('quotes'),
        func.sum(case(((q.c.kind=='frete') & q.c.status.in_(('released','posted','delivered')),1),else_=0)).label('labels'),
        func.sum(case((q.c.kind=='impressao',1),else_=0)).label('prints'),
        func.sum(case((completed,1),else_=0)).label('completed_prints'),
        func.sum(case((completed & q.c.source.in_(('bot','erp')),1),else_=0)).label('address_prints'),
        func.sum(case((completed & (q.c.source=='superfrete'),1),else_=0)).label('label_prints'),
        func.max(case((completed,func.coalesce(q.c.finished_at,q.c.created_at)))).label('last_printed_at'))).mappings().one()
    return {k:(v or 0) if k not in ('last_used_at','last_printed_at') else v for k,v in row.items()}


def history(db, address, offset=0, limit=30, kind='all'):
    ids=address_family(db,address)
    table=usage_query(ids)
    query=select(table)
    if kind!='all':query=query.where(table.c.kind==kind)
    count=db.execute(select(func.count()).select_from(query.subquery())).scalar()
    result=[]
    for item in db.execute(query.order_by(func.coalesce(table.c.finished_at,table.c.created_at).desc(),table.c.kind,table.c.id).offset(offset).limit(limit)).mappings():
        row=dict(item)
        row['id']=str(row['id'])
        row['price']=str(row['price']) if row['price'] is not None else None
        snapshot=row.pop('snapshot') or {}
        if row['kind']=='frete':
            p=snapshot.get('to',{})
            row['recipient']=p.get('name','')
            row['address_text']=', '.join(str(p.get(k) or '') for k in ('address','number','district','complement','city','state_abbr','postal_code') if p.get(k))
        else:
            p=snapshot.get('editor') or snapshot.get('endereco') or {}
            row['recipient']=p.get('nome','')
            row['address_text']=', '.join(str(p.get(k) or '') for k in ('endereco','numero','bairro','complemento','cidade','estado','cep') if p.get(k))
        result.append(row)
    return {'total':count,'summary':usage_stats(db,ids),'items':result}
