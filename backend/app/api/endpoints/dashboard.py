from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, List
from datetime import date
from ...database import get_db
from ...models.venda import Venda
from ...models.vendedor import Vendedor
from ...models.pedido import Pedido
from ...dependencies import get_current_active_user
from ..validators import validate_date

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
) -> Dict[str, Any]:
    # Get current date
    today = date.today()
    
    # Total vendas (sum of valor_liquido)
    total_vendas = db.query(func.sum(Venda.valor_liquido)).scalar() or 0
    
    # Total vendedores ativos
    total_vendedores = db.query(func.count(Vendedor.id)).filter(Vendedor.ativo == True).scalar() or 0
    
    # Total pedidos
    total_pedidos = db.query(func.count(Pedido.id)).scalar() or 0
    
    # Vendas hoje
    vendas_hoje = db.query(func.count(Venda.id)).filter(Venda.data_venda == today).scalar() or 0
    
    # Meta mensal (mock data for now)
    meta_mensal = 15000
    
    # Vendas por moeda
    vendas_por_moeda = db.query(
        Venda.moeda,
        func.sum(Venda.valor_bruto).label('valor'),
        func.count(Venda.id).label('quantidade')
    ).group_by(Venda.moeda).all()
    
    vendas_por_moeda_formatted = [
        {
            "moeda": row.moeda,
            "valor": float(row.valor or 0),
            "quantidade": row.quantidade
        }
        for row in vendas_por_moeda
    ]
    
    return {
        "totalVendas": float(total_vendas),
        "totalVendedores": total_vendedores,
        "totalPedidos": total_pedidos,
        "vendasHoje": vendas_hoje,
        "metaMensal": meta_mensal,
        "vendas_por_moeda": vendas_por_moeda_formatted
    }

@router.get("/vendas-por-periodo")
def get_vendas_por_periodo(
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    query = db.query(
        func.date(Venda.data_venda).label('data'),
        func.sum(Venda.valor_liquido).label('total'),
        func.count(Venda.id).label('quantidade')
    ).group_by(func.date(Venda.data_venda))
    
    if start_date:
        validated_start = validate_date(start_date, "start_date")
        query = query.filter(Venda.data_venda >= validated_start)
    if end_date:
        validated_end = validate_date(end_date, "end_date")
        query = query.filter(Venda.data_venda <= validated_end)
    
    resultados = query.order_by(func.date(Venda.data_venda)).all()
    
    return [
        {
            "data": row.data.strftime('%Y-%m-%d'),
            "total": float(row.total or 0),
            "quantidade": row.quantidade
        }
        for row in resultados
    ]

@router.get("/vendedores-performance")
def get_vendedores_performance(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    resultados = db.query(
        Vendedor.nome,
        func.count(Venda.id).label('total_vendas'),
        func.sum(Venda.valor_liquido).label('valor_total')
    ).join(Venda, Vendedor.id == Venda.vendedor_id)\
     .group_by(Vendedor.id, Vendedor.nome)\
     .order_by(func.sum(Venda.valor_liquido).desc()).all()
    
    return [
        {
            "nome": row.nome,
            "total_vendas": row.total_vendas,
            "valor_total": float(row.valor_total or 0)
        }
        for row in resultados
    ]