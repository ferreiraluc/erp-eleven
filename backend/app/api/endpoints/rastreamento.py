from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
import uuid
from datetime import datetime, date, timedelta

from ...database import get_db
from ...models.rastreamento import Rastreamento, RastreamentoStatus
from ...models.usuario import Usuario
from ...schemas.rastreamento import (
    RastreamentoCreate, 
    RastreamentoUpdate, 
    RastreamentoResponse,
    RastreamentoComPedido,
    RastreamentoResumo
)
from ...dependencies import get_current_user

router = APIRouter()


@router.get("/", response_model=List[RastreamentoComPedido])
def listar_rastreamentos(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[RastreamentoStatus] = None,
    ativo: bool = True,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Lista rastreamentos com filtros opcionais"""
    query = db.query(Rastreamento).filter(Rastreamento.ativo == ativo)
    
    if status_filter:
        query = query.filter(Rastreamento.status == status_filter)
    
    rastreamentos = query.order_by(desc(Rastreamento.updated_at)).offset(skip).limit(limit).all()
    
    # Converter para RastreamentoComPedido incluindo dados do pedido
    resultado = []
    for r in rastreamentos:
        rastreamento_dict = {
            "id": r.id,
            "codigo_rastreio": r.codigo_rastreio,
            "status": r.status,
            "servico_provedor": r.servico_provedor,
            "ultima_atualizacao": r.ultima_atualizacao,
            "descricao": r.descricao,
            "destinatario": r.destinatario,
            "origem": r.origem,
            "destino": r.destino,
            "historico_eventos": r.historico_eventos or [],
            "pedido_id": r.pedido_id,
            "data_criacao": r.data_criacao,
            "ativo": r.ativo,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "created_by": r.created_by,
            # Dados do pedido
            "numero_pedido": r.pedido.numero_pedido if r.pedido else None,
            "cliente_nome_pedido": r.pedido.cliente_nome if r.pedido else None,
            "cliente_telefone": r.pedido.cliente_telefone if r.pedido else None,
            "endereco_entrega": r.pedido.endereco_entrega if r.pedido else None,
        }
        resultado.append(rastreamento_dict)
    
    return resultado


@router.post("/", response_model=RastreamentoResponse)
def criar_rastreamento(
    rastreamento: RastreamentoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Cria um novo rastreamento"""
    
    # Verificar se código já existe
    existing = db.query(Rastreamento).filter(
        Rastreamento.codigo_rastreio == rastreamento.codigo_rastreio,
        Rastreamento.ativo == True
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de rastreamento já existe"
        )
    
    # Criar rastreamento
    db_rastreamento = Rastreamento(
        **rastreamento.dict(),
        created_by=current_user.id
    )
    
    db.add(db_rastreamento)
    db.commit()
    db.refresh(db_rastreamento)
    
    return db_rastreamento


@router.get("/{rastreamento_id}", response_model=RastreamentoComPedido)
def obter_rastreamento(
    rastreamento_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtém um rastreamento específico"""
    rastreamento = db.query(Rastreamento).filter(
        Rastreamento.id == rastreamento_id,
        Rastreamento.ativo == True
    ).first()
    
    if not rastreamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rastreamento não encontrado"
        )
    
    # Construir resposta com dados do pedido
    return {
        "id": rastreamento.id,
        "codigo_rastreio": rastreamento.codigo_rastreio,
        "status": rastreamento.status,
        "servico_provedor": rastreamento.servico_provedor,
        "ultima_atualizacao": rastreamento.ultima_atualizacao,
        "descricao": rastreamento.descricao,
        "destinatario": rastreamento.destinatario,
        "origem": rastreamento.origem,
        "destino": rastreamento.destino,
        "historico_eventos": rastreamento.historico_eventos or [],
        "pedido_id": rastreamento.pedido_id,
        "data_criacao": rastreamento.data_criacao,
        "ativo": rastreamento.ativo,
        "created_at": rastreamento.created_at,
        "updated_at": rastreamento.updated_at,
        "created_by": rastreamento.created_by,
        # Dados do pedido
        "numero_pedido": rastreamento.pedido.numero_pedido if rastreamento.pedido else None,
        "cliente_nome_pedido": rastreamento.pedido.cliente_nome if rastreamento.pedido else None,
        "cliente_telefone": rastreamento.pedido.cliente_telefone if rastreamento.pedido else None,
        "endereco_entrega": rastreamento.pedido.endereco_entrega if rastreamento.pedido else None,
    }


@router.get("/codigo/{codigo}", response_model=RastreamentoComPedido)
def obter_rastreamento_por_codigo(
    codigo: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtém um rastreamento pelo código"""
    rastreamento = db.query(Rastreamento).filter(
        Rastreamento.codigo_rastreio == codigo,
        Rastreamento.ativo == True
    ).first()
    
    if not rastreamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rastreamento não encontrado"
        )
    
    return {
        "id": rastreamento.id,
        "codigo_rastreio": rastreamento.codigo_rastreio,
        "status": rastreamento.status,
        "servico_provedor": rastreamento.servico_provedor,
        "ultima_atualizacao": rastreamento.ultima_atualizacao,
        "descricao": rastreamento.descricao,
        "destinatario": rastreamento.destinatario,
        "origem": rastreamento.origem,
        "destino": rastreamento.destino,
        "historico_eventos": rastreamento.historico_eventos or [],
        "pedido_id": rastreamento.pedido_id,
        "data_criacao": rastreamento.data_criacao,
        "ativo": rastreamento.ativo,
        "created_at": rastreamento.created_at,
        "updated_at": rastreamento.updated_at,
        "created_by": rastreamento.created_by,
        # Dados do pedido
        "numero_pedido": rastreamento.pedido.numero_pedido if rastreamento.pedido else None,
        "cliente_nome_pedido": rastreamento.pedido.cliente_nome if rastreamento.pedido else None,
        "cliente_telefone": rastreamento.pedido.cliente_telefone if rastreamento.pedido else None,
        "endereco_entrega": rastreamento.pedido.endereco_entrega if rastreamento.pedido else None,
    }


@router.put("/{rastreamento_id}", response_model=RastreamentoResponse)
def atualizar_rastreamento(
    rastreamento_id: uuid.UUID,
    rastreamento_update: RastreamentoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Atualiza um rastreamento"""
    db_rastreamento = db.query(Rastreamento).filter(
        Rastreamento.id == rastreamento_id,
        Rastreamento.ativo == True
    ).first()
    
    if not db_rastreamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rastreamento não encontrado"
        )
    
    update_data = rastreamento_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_rastreamento, field, value)
    
    db.commit()
    db.refresh(db_rastreamento)
    
    return db_rastreamento


@router.delete("/{rastreamento_id}")
def deletar_rastreamento(
    rastreamento_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Soft delete de um rastreamento"""
    db_rastreamento = db.query(Rastreamento).filter(
        Rastreamento.id == rastreamento_id
    ).first()
    
    if not db_rastreamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rastreamento não encontrado"
        )
    
    db_rastreamento.ativo = False
    db.commit()
    
    return {"message": "Rastreamento removido com sucesso"}


@router.get("/resumo/dashboard", response_model=RastreamentoResumo)
def obter_resumo_dashboard(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtém resumo de rastreamentos para a dashboard"""
    
    # Contadores por status
    total = db.query(Rastreamento).filter(Rastreamento.ativo == True).count()
    em_transito = db.query(Rastreamento).filter(
        Rastreamento.ativo == True,
        Rastreamento.status == RastreamentoStatus.EM_TRANSITO
    ).count()
    entregues = db.query(Rastreamento).filter(
        Rastreamento.ativo == True,
        Rastreamento.status == RastreamentoStatus.ENTREGUE
    ).count()
    pendentes = db.query(Rastreamento).filter(
        Rastreamento.ativo == True,
        Rastreamento.status == RastreamentoStatus.PENDENTE
    ).count()
    com_erro = db.query(Rastreamento).filter(
        Rastreamento.ativo == True,
        Rastreamento.status.in_([RastreamentoStatus.ERRO, RastreamentoStatus.NAO_ENCONTRADO])
    ).count()
    
    # Rastreamentos recentes (últimos 5)
    recentes = db.query(Rastreamento).filter(
        Rastreamento.ativo == True
    ).order_by(desc(Rastreamento.updated_at)).limit(5).all()
    
    return RastreamentoResumo(
        total_rastreamentos=total,
        em_transito=em_transito,
        entregues=entregues,
        pendentes=pendentes,
        com_erro=com_erro,
        rastreamentos_recentes=recentes
    )