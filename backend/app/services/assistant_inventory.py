"""Confirmed inventory writes use the ERP item and stock-movement records."""
import uuid
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import text
from ..models.inventory import Item
from ..models.assistant import AssistantAction,utcnow
from .assistant_schedule import may_schedule
from .assistant_controls import normalized,preview_reply
from .assistant_queries import StockArgs,query_stock
from .inventory_service import create_movement

Currency=Literal['BRL','USD','PYG','EUR']


class ItemDraft(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    nome:str=Field(min_length=2,max_length=200)
    marca:str=Field(default='',max_length=100)
    categoria:str=Field(default='',max_length=100)
    tamanho:str=Field(default='',max_length=50)
    cor:str=Field(default='',max_length=50)
    codigo_barras:str=Field(default='',max_length=200)
    preco_venda:Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    moeda_venda:Currency|None=None
    custo:Decimal|None=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    moeda_custo:Currency|None=None
    quantidade:int=Field(default=0,ge=0,le=100000)
    local:Literal['loja','deposito']|None=None

    @model_validator(mode='after')
    def explicit_units(self):
        if self.preco_venda is not None and not self.moeda_venda:raise ValueError('Informe a moeda do preço de venda.')
        if self.custo is not None and not self.moeda_custo:raise ValueError('Informe a moeda do custo.')
        if self.quantidade and not self.local:raise ValueError('Informe se a quantidade inicial vai para a loja ou depósito.')
        return self


class ItemsArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    itens:list[ItemDraft]=Field(min_length=1,max_length=20)


class EntryArgs(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    item_id:uuid.UUID|None=None
    termo:str|None=Field(default=None,min_length=2,max_length=100)
    tamanho:str|None=Field(default=None,max_length=50)
    cor:str|None=Field(default=None,max_length=50)
    quantidade:int=Field(ge=1,le=100000)
    local:Literal['loja','deposito']
    @model_validator(mode='after')
    def item_ref(self):
        if not self.item_id and not self.termo:raise ValueError('Informe o nome ou SKU do produto.')
        return self


def identity(data):
    return tuple(normalized(data.get(k) or '') for k in ('nome','marca','tamanho','cor'))


def duplicate_items(db,items):
    existing=db.query(Item.id,Item.name,Item.brand,Item.size,Item.color,Item.barcode,Item.sku_internal,Item.is_active).all()
    seen=set();duplicates=[]
    for data in items:
        key=identity(data)
        if key in seen:duplicates.append({'nome':data['nome'],'motivo':'Repetido na mesma solicitação.'})
        seen.add(key)
        for row in existing:
            other={'nome':row.name,'marca':row.brand,'tamanho':row.size,'cor':row.color}
            if identity(other)==key or data.get('codigo_barras') and data['codigo_barras']==row.barcode:
                duplicates.append({'id':str(row.id),'nome':row.name,'sku':row.sku_internal,'ativo':row.is_active})
    return duplicates


def inventory_preview(action):
    p=action.payload
    if action.kind=='estoque_entrada':
        content=f"Registrar entrada: {p['item_name']} ({p['sku']})\nQuantidade: +{p['quantidade']} unidade(s) no local {p['local']}.\nO saldo será aumentado e a movimentação ficará no histórico do estoque."
    else:
        lines=['Cadastrar produtos no estoque:']
        for i in p['itens']:
            lines.append(' · '.join(v for v in (i['nome'],i['marca'],i['tamanho'],i['cor']) if v))
            lines.append(f"Estoque inicial: {i['quantidade']}"+(f" no local {i['local']}" if i['quantidade'] else ' (sem movimentação).'))
            lines.append(f"Venda: {i['moeda_venda'] or 'USD'} {i['preco_venda'] or '0'}; custo: {i['moeda_custo'] or 'BRL'} {i['custo'] or '0'}."+
                         (' Valores ausentes ficam em zero, como no cadastro do ERP.' if i['preco_venda'] is None or i['custo'] is None else ''))
        content='\n'.join(lines)
    return preview_reply(action,content+'\nConfirme para salvar no ERP ou cancele. Nenhuma alteração foi aplicada ainda.')


def prepare_inventory(db,message,identity_record,name,args):
    if not message.should_reply or not may_schedule(db,message,identity_record):return {'erro':'Cadastro/entrada de estoque exige ADMIN ou GERENTE habilitado e pedido direto.'}
    previous=db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if previous:return {'confirmacao':inventory_preview(previous)} if previous.kind in ('item_cadastrar','estoque_entrada') else {'erro':'Esta mensagem já tem outra prévia.'}
    if name=='preparar_itens':
        items=args.model_dump(mode='json')['itens']
        duplicates=duplicate_items(db,items)
        if duplicates:return {'erro':'Já existe produto com esses dados. Para acrescentar unidades use preparar_entrada_estoque; não crie outro cadastro.','candidatos':duplicates}
        payload={'itens':items,'item_name':', '.join(i['nome'] for i in items)};kind='item_cadastrar'
    else:
        if args.item_id:item=db.get(Item,args.item_id)
        else:
            result=query_stock(db,StockArgs(termo=args.termo,tamanho=args.tamanho,cor=args.cor,limite=5))
            if result.get('total')!=1:return {'erro':'Escolha o produto/variante para a entrada.','candidatos':result.get('resultados',[])}
            item=db.get(Item,uuid.UUID(result['resultados'][0]['id']))
        if not item or not item.is_active:return {'erro':'Produto não encontrado ou inativo.'}
        payload={'item_id':str(item.id),'item_name':item.name,'sku':item.sku_internal,'quantidade':args.quantidade,'local':args.local};kind='estoque_entrada'
    action=AssistantAction(source_message_id=message.id,user_id=message.user_id,kind=kind,payload=payload)
    db.add(action);db.flush()
    return {'confirmacao':inventory_preview(action)}


def confirm_inventory(db,message,action):
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(711006)'))
    p=action.payload
    if action.kind=='estoque_entrada':
        item=db.query(Item).filter_by(id=uuid.UUID(p['item_id']),is_active=True).with_for_update().first()
        if not item:return 'Produto inativo ou removido. Nenhuma entrada registrada.'
        move=create_movement(db,item.id,'entry',p['quantidade'],message.user_id,location=p['local'],reason='Entrada pelo assistente',reference_type='assistant_action',reference_id=str(action.id))
        action.result_id=move.id
        answer=f"Entrada registrada: +{p['quantidade']} de {item.name} no local {p['local']}. Saldo atual: loja {item.stock_loja}, depósito {item.stock_deposito}."
    else:
        if duplicate_items(db,p['itens']):
            action.status='cancelled'
            return 'Um desses produtos já foi cadastrado. Nenhum item foi duplicado. Consulte o estoque e peça entrada de unidades se necessário.'
        created=[]
        for data in p['itens']:
            i=ItemDraft.model_validate(data)
            title=lambda s:' '.join(word.capitalize() for word in s.strip().split()) if s else None
            item=Item(name=title(i.nome),brand=title(i.marca),category=title(i.categoria),color=title(i.cor),size=i.tamanho or None,
                barcode=i.codigo_barras or None,sku_internal='INV-'+utcnow().strftime('%Y%m%d')+'-'+uuid.uuid4().hex[:12].upper(),
                sale_price=i.preco_venda or 0,sale_currency=i.moeda_venda or 'USD',cost_price=i.custo or 0,cost_currency=i.moeda_custo or 'BRL',
                created_by=message.user_id,current_stock=0,stock_loja=0,stock_deposito=0)
            db.add(item);db.flush()
            if i.quantidade:create_movement(db,item.id,'entry',i.quantidade,message.user_id,location=i.local,reason='Estoque inicial pelo assistente',reference_type='assistant_action',reference_id=str(action.id))
            created.append(item)
        action.result_id=created[0].id
        answer='Produtos cadastrados no ERP:\n'+'\n'.join(f'{i.name} · {i.size or ""} {i.color or ""} · SKU {i.sku_internal} · saldo {i.current_stock}' for i in created)
    action.status='executed';action.executed_at=utcnow()
    return answer
