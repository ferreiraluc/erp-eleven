"""Atomic, owner-reviewed revisions of PDV records; never calls a payment provider."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import uuid
from fastapi import HTTPException
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, load_only
from sqlalchemy.exc import IntegrityError
from ..config import settings
from ..models.pdv import PdvSale, PdvSaleItem, PdvPayment, PdvCliente, PdvFiadoMovement, PdvSaleEvent
from ..models.inventory import Item
from ..models.usuario import Usuario
from ..schemas.pdv import validate_pdv_quantity
from .access_policy import is_owner, own_sales, sales_query
from .inventory_service import create_movement, StockMovementError
from .user_audit import bind_actor, record
from .pdv_payments import validate_payment, unchanged_payment

CENT = Decimal('.01')
MAX_MONEY = Decimal('9999999999999.99')

def money(value):
    try: result = Decimal(str(value))
    except (ValueError, ArithmeticError): raise HTTPException(422, 'Valor monetário inválido.') from None
    if not result.is_finite() or abs(result) > MAX_MONEY: raise HTTPException(422, 'Valor monetário inválido.')
    return result.quantize(CENT, rounding=ROUND_HALF_UP)

def positive(value):
    result = money(value)
    if result < 0: raise HTTPException(422, 'Valores negativos não são permitidos.')
    return result

def serial(value):
    if isinstance(value, dict): return {k: serial(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [serial(v) for v in value]
    if isinstance(value, (Decimal, uuid.UUID)): return str(value)
    if isinstance(value, (datetime, date)): return value.isoformat()
    return value

def digest(value): return hashlib.sha256(json.dumps(serial(value),sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def snapshot(sale):
    fields = ('id','vendedor_id','cliente_id','cliente_nome','subtotal_gs','desconto_gs','total_gs','status','stock_applied','notas','created_at','version','refunded_gs','fiado_reversed_gs','deleted_at')
    return serial({**{f:getattr(sale,f) for f in fields},
        'items':[{c.name:getattr(r,c.name) for c in r.__table__.columns} for r in sorted(sale.items,key=lambda r:str(r.id))],
        'payments':[{c.name:getattr(r,c.name) for c in r.__table__.columns} for r in sorted(sale.payments,key=lambda r:str(r.id))]})

def owner(user):
    if not user.ativo or not is_owner(user): raise HTTPException(403,'Somente Lucas pode editar, excluir ou estornar vendas.')

def get_sale(db, sid, user, lock=False):
    q = sales_query(db.query(PdvSale), PdvSale, user, pdv=True).filter(PdvSale.id == sid)
    if not is_owner(user): q = q.filter(PdvSale.deleted_at.is_(None))
    sale = (q.populate_existing().with_for_update() if lock else q).first()
    if not sale: raise HTTPException(404,'Venda não encontrada.')
    if lock:
        # Relationships may have been loaded before a concurrent transaction.
        db.expire(sale, ['items','payments'])
    return sale

def detail(db,sid,user):
    sale=get_sale(db,sid,user)
    data=snapshot(sale)
    people=dict(db.query(Usuario.id,Usuario.nome).filter(Usuario.id.in_([sale.vendedor_id,sale.created_by])).all())
    data.update(seller=people.get(sale.vendedor_id),actor=people.get(sale.created_by),can_manage=is_owner(user))
    removed=dict(db.query(Item.id,Item.name).filter(Item.id.in_([r.item_id for r in sale.items if r.item_id]),Item.deleted_at.isnot(None)).all())
    for line in data['items']:
        line['product_deleted']=uuid.UUID(line['item_id']) in removed if line['item_id'] else False
        if line['product_deleted']:line['item_name']='Produto excluído — '+line['item_name']
    data['events']=[]
    events=db.query(PdvSaleEvent).filter_by(sale_id=sid).order_by(PdvSaleEvent.created_at.desc()).limit(100).all() if is_owner(user) else []
    actors=dict(db.query(Usuario.id,Usuario.nome).filter(Usuario.id.in_([e.created_by for e in events])).all())
    for e in events:
        data['events'].append(serial({'id':e.id,'operation':e.operation,'reason':e.reason,'at':e.created_at,
            'actor':actors.get(e.created_by),'before':e.before,'after':e.after,'effects':e.effects}))
    data['payment_difference_gs']=str(money(sum(p.amount_gs for p in sale.payments))-money(sale.total_gs))
    return data

def listing(db,user,*,page=1,page_size=25,q='',status=None,date_from=None,date_to=None,seller_id=None,payment=None,deleted=False):
    query=sales_query(db.query(PdvSale),PdvSale,user,pdv=True)
    if deleted:
        owner(user);query=query.filter(PdvSale.deleted_at.isnot(None))
    else:query=query.filter(PdvSale.deleted_at.is_(None))
    if date_from:query=query.filter(PdvSale.created_at >= datetime.combine(date_from,time.min))
    if date_to:query=query.filter(PdvSale.created_at < datetime.combine(date_to+timedelta(days=1),time.min))
    if date_from and date_to and date_from>date_to:raise HTTPException(422,'O início do período deve anteceder o fim.')
    if seller_id:query=query.filter(PdvSale.vendedor_id==seller_id)
    if status:query=query.filter(PdvSale.status==status)
    if payment:query=query.filter(PdvSale.id.in_(db.query(PdvPayment.sale_id).filter(PdvPayment.method==payment)))
    if q.strip():
        term='%'+q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        matches=db.query(PdvSaleItem.sale_id).filter(or_(PdvSaleItem.item_name.ilike(term,escape='\\'),PdvSaleItem.item_sku.ilike(term,escape='\\')))
        parts=[PdvSale.cliente_nome.ilike(term,escape='\\'),PdvSale.id.in_(matches)]
        try:parts.append(PdvSale.id==uuid.UUID(q))
        except ValueError:pass
        query=query.filter(or_(*parts))
    count=query.count()
    grouped=query.with_entities(PdvSale.status,func.count(PdvSale.id),func.sum(PdvSale.total_gs),func.sum(PdvSale.refunded_gs)).group_by(PdvSale.status).all()
    # Cancelled records remain auditable but never inflate effective sales.
    gross=sum((r[2] or 0) for r in grouped if r[0]!='cancelled')
    refunds=sum((r[3] or 0) for r in grouped)
    effective_refunds=sum((r[3] or 0) for r in grouped if r[0]!='cancelled')
    rows=query.options(joinedload(PdvSale.vendedor),joinedload(PdvSale.items),joinedload(PdvSale.payments)).order_by(PdvSale.created_at.desc(),PdvSale.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return serial({'page':page,'page_size':page_size,'total':count,'own_sales_only':own_sales(user),'can_manage':is_owner(user),
        'summary':{'gross_gs':gross,'refunded_gs':refunds,'net_gs':gross-effective_refunds,'cancelled':sum(r[1] for r in grouped if r[0]=='cancelled')},
        'items':[{'id':s.id,'created_at':s.created_at,'cliente_nome':s.cliente_nome,'seller':s.vendedor.nome if s.vendedor else None,
                  'total_gs':s.total_gs,'refunded_gs':s.refunded_gs,'status':s.status,'items_count':len(s.items),
                  'payment_methods':sorted({p.method for p in s.payments}),'deleted_at':s.deleted_at,'version':s.version} for s in rows]})

def _debt(db,sale):
    # Use posted ledger entries, never assume a legacy payment created a debit.
    return money(sum((r.valor_gs if r.tipo=='debit' else -r.valor_gs if r.tipo=='credit' else 0)
                     for r in db.query(PdvFiadoMovement).filter_by(sale_id=sale.id).all()))

def _validated_edit(db,body,original_payments=()):
    if not body.items or len(body.items)>200 or not body.payments or len(body.payments)>30:raise HTTPException(422,'Informe de 1 a 200 itens e de 1 a 30 pagamentos.')
    data=body.model_dump()
    subtotal=Decimal(0)
    for row in data['items']:
        row['quantity']=validate_pdv_quantity(row['quantity'],avulso=row['is_avulso'])
        row['unit_price_gs']=positive(row['unit_price_gs']);row['discount_gs']=positive(row['discount_gs'])
        if not row['item_name'].strip():raise HTTPException(422,'Informe o nome de cada item.')
        row['total_gs']=money(row['quantity']*row['unit_price_gs']-row['discount_gs'])
        if row['total_gs']<0:raise HTTPException(422,'O desconto do item supera seu valor.')
        if row['original_price_gs'] is not None:row['original_price_gs']=positive(row['original_price_gs'])
        subtotal+=row['total_gs']
    data['subtotal_gs']=positive(subtotal);data['desconto_gs']=positive(data['desconto_gs'])
    data['total_gs']=money(subtotal-data['desconto_gs'])
    if data['total_gs']<0:raise HTTPException(422,'O desconto da venda supera seu valor.')
    paid=Decimal(0)
    legacy_candidates = list(original_payments)
    for p in data['payments']:
        original = next((old for old in legacy_candidates if unchanged_payment(p, old)), None)
        if original is not None:
            legacy_candidates.remove(original)
        p.update(validate_payment(p, preserve_legacy=original is not None))
        paid+=p['amount_gs']
    # For a correction, payments represent the amount applied, excluding change.
    if money(paid)!=data['total_gs']:raise HTTPException(422,'Os pagamentos corrigidos devem somar o total da venda, sem incluir troco.')
    if any(p['method']=='fiado' and p['amount_gs']>0 for p in data['payments']) and not data['cliente_id']:raise HTTPException(422,'Selecione o cliente para lançar fiado.')
    if data['vendedor_id'] and not db.get(Usuario,data['vendedor_id']):raise HTTPException(422,'Vendedor não encontrado.')
    return data

def plan(db,sid,user,command):
    owner(user);sale=get_sale(db,sid,user,lock=True)
    if sale.deleted_at:raise HTTPException(409,'Esta venda já foi excluída da listagem; o histórico está preservado.')
    before=snapshot(sale);delta=defaultdict(Decimal);new=None;returns=[];refund=Decimal(0)
    warnings=[];debt_changes=defaultdict(Decimal);old_debt=_debt(db,sale)
    if old_debt<0:raise HTTPException(409,'O histórico de fiado desta venda precisa de conferência antes de alterar.')
    if command.operation=='edit':
        if sale.status!='completed' or sale.refunded_gs or any(r.returned_quantity for r in sale.items):raise HTTPException(409,'Venda com devolução ou cancelamento não pode ser reescrita. Consulte o histórico e registre uma nova venda.')
        new=_validated_edit(db,command.edit,sale.payments)
        new['vendedor_id']=new['vendedor_id'] or sale.vendedor_id
        for r in sale.items:
            if not r.is_avulso and sale.stock_applied:
                if not r.item_id or r.location not in ('loja','deposito'):raise HTTPException(409,'Vínculo ou local original inválido. Confira a venda antes de corrigir.')
                delta[(r.item_id,r.location)]+=validate_pdv_quantity(r.quantity,avulso=False)
        for r in new['items']:
            if not r['is_avulso']:delta[(r['item_id'],r['location'])]-=r['quantity']
        if sale.cliente_id:debt_changes[sale.cliente_id]-=old_debt
        if new['cliente_id']:debt_changes[new['cliente_id']]+=sum(p['amount_gs'] for p in new['payments'] if p['method']=='fiado')
    elif sale.status in ('completed','partially_refunded'):
        paid=sum(positive(p.amount_gs) for p in sale.payments)
        fiado_paid=sum(positive(p.amount_gs) for p in sale.payments if p.method=='fiado')
        if money(paid)<money(sale.total_gs) or fiado_paid>money(sale.total_gs):raise HTTPException(409,'Os pagamentos originais não cobrem a venda ou o fiado supera o total. Confira e corrija os pagamentos antes de estornar.')
        if money(fiado_paid-sale.fiado_reversed_gs)!=old_debt:raise HTTPException(409,'O fiado lançado não confere com os pagamentos da venda. Revise o histórico antes de estornar.')
        selected={r.line_id:r for r in command.lines}
        if command.operation=='return' and set(selected)-{r.id for r in sale.items}:raise HTTPException(422,'A seleção contém itens de outra venda.')
        if not sale.items:raise HTTPException(409,'Venda sem itens; confira o registro antes de estornar.')
        for r in sale.items:
            try:
                validate_pdv_quantity(r.quantity,avulso=r.is_avulso)
                if r.returned_quantity is None or r.returned_quantity<0 or r.returned_quantity>r.quantity:raise ValueError('Devoluções anteriores inválidas.')
                if r.returned_quantity:validate_pdv_quantity(r.returned_quantity,avulso=r.is_avulso)
            except ValueError as e:raise HTTPException(409,'Quantidade original inválida. '+str(e)) from None
        eligible=[r for r in sale.items if r.quantity>r.returned_quantity]
        if command.operation=='return' and set(selected)-{r.id for r in eligible}:raise HTTPException(409,'A seleção contém peças já totalmente devolvidas. Atualize a venda.')
        if not eligible:raise HTTPException(409,'Todas as peças já foram devolvidas.')
        subtotal=positive(sale.subtotal_gs);total=positive(sale.total_gs)
        # Allocate sale-level discount deterministically; final line carries rounding residue.
        allocations={};cumulative=Decimal(0);allocated=Decimal(0)
        ordered=sorted(sale.items,key=lambda r:str(r.id))
        if subtotal==0 and total>0:raise HTTPException(409,'Subtotal original inválido. Corrija os valores antes de estornar.')
        if money(sum(positive(r.total_gs) for r in ordered))!=subtotal or money(subtotal-positive(sale.desconto_gs))!=total:raise HTTPException(409,'Totais originais inconsistentes. Corrija a venda antes de estornar.')
        for index,r in enumerate(ordered):
            cumulative+=positive(r.total_gs)
            target=total if index==len(ordered)-1 else money(cumulative*total/subtotal) if subtotal else Decimal(0)
            value=target-allocated
            if value<0:raise HTTPException(409,'Totais originais inconsistentes. Corrija a venda antes de estornar.')
            allocations[r.id]=value;allocated=target
        for r in eligible:
            selection=selected.get(r.id)
            qty=(selection.quantity if selection else Decimal(0)) if command.operation=='return' else r.quantity-r.returned_quantity
            if not qty:continue
            qty=validate_pdv_quantity(qty,avulso=r.is_avulso)
            if qty>r.quantity-r.returned_quantity:raise HTTPException(409,'Quantidade superior ao saldo disponível para devolução.')
            restock=selection.restock if selection else command.restock
            line_refund=money(allocations[r.id]*(r.returned_quantity+qty)/r.quantity)-money(allocations[r.id]*r.returned_quantity/r.quantity)
            refund+=line_refund
            returns.append({'line_id':r.id,'name':r.item_name,'quantity':qty,'restock':restock,'refund_gs':line_refund})
            if restock and not r.is_avulso and sale.stock_applied:
                if not r.item_id or r.location not in ('loja','deposito'):raise HTTPException(409,'Produto sem vínculo/local para devolver ao estoque. Revise ou escolha sem reposição.')
                delta[(r.item_id,r.location)]+=qty
        if not returns:raise HTTPException(409,'Nenhuma peça disponível na seleção.')
        if not sale.stock_applied:warnings.append('Esta venda não possui baixa ativa de estoque; nenhuma reposição será feita.')
        if sale.cliente_id:debt_changes[sale.cliente_id]-=min(old_debt,refund)
    elif command.operation!='delete':raise HTTPException(409,'Esta venda já foi cancelada ou totalmente estornada.')
    if command.operation=='delete':warnings.append('A venda será retirada da listagem principal. Registros, revisões e comprovantes permanecem no histórico de excluídas.')
    delta={key:value for key,value in delta.items() if value}
    product_ids={key[0] for key in delta}
    if new:product_ids.update(r['item_id'] for r in new['items'] if not r['is_avulso'])
    products=db.query(Item).options(load_only(Item.id,Item.name,Item.sku_internal,Item.category,Item.size,Item.color,Item.deleted_at,Item.is_active,Item.current_stock,Item.stock_loja,Item.stock_deposito)).filter(Item.id.in_(product_ids)).order_by(Item.id).with_for_update().populate_existing().all()
    by_id={r.id:r for r in products}
    if len(by_id)!=len(product_ids):raise HTTPException(409,'Um produto não existe mais. Revise os vínculos ou a reposição ao estoque.')
    effects=[]
    for p in products:
        d_loja=delta.get((p.id,'loja'),0);d_dep=delta.get((p.id,'deposito'),0)
        if p.deleted_at:raise HTTPException(409,'Produto excluído do catálogo: escolha devolução sem reposição ou selecione outro produto na edição.')
        if new and any(r['item_id']==p.id and not r['is_avulso'] for r in new['items']) and not p.is_active:raise HTTPException(409,'Selecione produtos ativos para a venda corrigida.')
        if not(d_loja or d_dep):continue
        if any(v is None or v<0 for v in (p.current_stock,p.stock_loja,p.stock_deposito)) or p.current_stock!=p.stock_loja+p.stock_deposito:raise HTTPException(409,'Saldo original desconhecido ou divergente. Confira o estoque antes de alterar esta venda.')
        if min(p.stock_loja+d_loja,p.stock_deposito+d_dep)<0:raise HTTPException(409,'Estoque insuficiente para a alteração solicitada.')
        if max(p.stock_loja+d_loja,p.stock_deposito+d_dep,p.current_stock+d_loja+d_dep)>2147483647:raise HTTPException(409,'Saldo resultante acima do limite permitido.')
        for loc,d in [('loja',d_loja),('deposito',d_dep)]:
            if d:effects.append({'item_id':p.id,'name':p.name,'location':loc,'delta':int(d),'before':getattr(p,'stock_'+loc),'after':int(getattr(p,'stock_'+loc)+d)})
    if new:
        for r in new['items']:
            if not r['is_avulso']:
                p=by_id[r['item_id']]
                r.update(item_name=p.name,item_sku=p.sku_internal,item_category=p.category,item_size=p.size,item_color=p.color)
    customer_ids=set(debt_changes)
    if new and new['cliente_id']:customer_ids.add(new['cliente_id'])
    customers=db.query(PdvCliente).filter(PdvCliente.id.in_(customer_ids)).order_by(PdvCliente.id).with_for_update().populate_existing().all()
    if len(customers)!=len(customer_ids):raise HTTPException(409,'Cliente da venda não encontrado.')
    debt_effects=[{'customer_id':c.id,'name':c.nome,'before':money(c.saldo_fiado_gs),'delta':money(debt_changes[c.id]),'after':money(c.saldo_fiado_gs+debt_changes[c.id])} for c in customers if debt_changes[c.id]]
    if any(e['after']<0 for e in debt_effects):warnings.append('O abatimento gera saldo a favor do cliente no fiado; confira valores já recebidos antes de devolver dinheiro.')
    if new and new['cliente_id']:new['cliente_nome']=next(c.nome for c in customers if c.id==new['cliente_id'])
    fiado_credit=sum(-e['delta'] for e in debt_effects if e['delta']<0) if not new else Decimal(0)
    public=serial({'operation':command.operation,'reason':command.reason,'before_total_gs':sale.total_gs,'after_total_gs':new['total_gs'] if new else money(sale.total_gs-sale.refunded_gs-refund) if sale.status!='cancelled' else 0,
        'refund_gs':refund,'fiado_credit_gs':fiado_credit,'cash_refund_gs':refund-fiado_credit,'stock':effects,'fiado':debt_effects,'returns':returns,'warnings':warnings,
        'correction':new,
        'payment_notice':'Esta operação registra o estorno no ERP. A devolução por dinheiro, Pix ou cartão é realizada fora do sistema.'})
    token=digest({'before':before,'command':command.model_dump(mode='json'),'effects':public,
        'products':[(p.id,p.deleted_at,p.is_active,p.current_stock,p.stock_loja,p.stock_deposito) for p in products],
        'customers':[(c.id,c.saldo_fiado_gs) for c in customers]})
    return sale,before,new,returns,effects,debt_effects,{**public,'plan_token':token}

def commit(db,sid,user,body):
    owner(user)
    # Serialize even idempotent retries against the sale's current transaction.
    sale=get_sale(db,sid,user,lock=True)
    fingerprint=digest({'sale_id':sid,'command':body.command.model_dump(mode='json'),'plan_token':body.plan_token})
    previous=db.query(PdvSaleEvent).filter_by(request_id=body.request_id).first()
    if previous:
        if previous.sale_id!=sid or previous.fingerprint!=fingerprint:raise HTTPException(409,'Identificador já usado em outra operação.')
        return {'ok':True,'sale_id':str(sid),'event_id':str(previous.id),'replayed':True}
    sale,before,new,returns,stock,fiado,preview=plan(db,sid,user,body.command)
    if preview['plan_token']!=body.plan_token:raise HTTPException(409,'A venda, o estoque ou o fiado mudou. Confira uma nova prévia antes de confirmar.')
    bind_actor(db,user)
    try:
        # Exits first to avoid transient total overflow when moving between locals.
        for change in sorted(stock,key=lambda r:(r['delta']>0,str(r['item_id']),r['location'])):
            mv=create_movement(db,change['item_id'],'entry' if change['delta']>0 else 'exit',abs(change['delta']),user.id,
                reason='pdv_'+body.command.operation,reference_type='pdv_sale',reference_id=str(sid),location=change['location'],notes=body.command.reason)
            if change['delta']>0:mv.location_from=None;mv.location_to=change['location']
        for change in fiado:
            cid=uuid.UUID(change['customer_id']) if isinstance(change['customer_id'],str) else change['customer_id']
            customer=db.get(PdvCliente,cid);customer.saldo_fiado_gs=money(change['after'])
            db.add(PdvFiadoMovement(cliente_id=cid,sale_id=sid,tipo='debit' if change['delta']>0 else 'credit',valor_gs=abs(change['delta']),saldo_gs=customer.saldo_fiado_gs,notas=body.command.reason,created_by=user.id))
        if new:
            for r in list(sale.items):db.delete(r)
            for p in list(sale.payments):db.delete(p)
            for key in ('vendedor_id','cliente_id','cliente_nome','subtotal_gs','desconto_gs','total_gs','notas'):setattr(sale,key,new[key])
            for r in new['items']:db.add(PdvSaleItem(sale_id=sid,**r))
            for p in new['payments']:db.add(PdvPayment(sale_id=sid,**p))
            sale.stock_applied=True
        elif returns:
            by_id={r.id:r for r in sale.items}
            for r in returns:by_id[r['line_id']].returned_quantity+=r['quantity']
            sale.refunded_gs+=money(preview['refund_gs']);sale.fiado_reversed_gs+=money(preview['fiado_credit_gs'])
            full=all(r.returned_quantity==r.quantity for r in sale.items)
            sale.status='cancelled' if body.command.operation in ('cancel','delete') else 'refunded' if full else 'partially_refunded'
            if full:sale.stock_applied=False
        if body.command.operation=='delete':sale.deleted_at=settings.now()
        sale.version+=1
        db.flush();db.expire(sale,['items','payments'])
        event=PdvSaleEvent(sale_id=sid,request_id=body.request_id,fingerprint=fingerprint,operation=body.command.operation,
            reason=body.command.reason,before=before,after=snapshot(sale),effects={k:v for k,v in preview.items() if k!='plan_token'},created_by=user.id)
        db.add(event);db.flush()
        record(db,'pdv_'+body.command.operation,'pdv',entity='pdv_sales',entity_id=str(sid),changes={'version':sale.version,'event_id':str(event.id),'refund_gs':preview['refund_gs']})
        result={'ok':True,'sale_id':str(sid),'event_id':str(event.id),'replayed':False}
        db.commit();return result
    except (StockMovementError,ValueError) as e:
        db.rollback();raise HTTPException(409,str(e)) from None
    except IntegrityError:
        db.rollback();raise HTTPException(409,'A operação conflitou com outro registro. Atualize a venda e confira o histórico antes de repetir.') from None
