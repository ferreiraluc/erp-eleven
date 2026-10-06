from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Any
import uuid
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

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
from ...config import settings
from ...models.pedido import Pedido
from ...services.customer_links import validate_tracking_links, lock_tracking_row
from ...services.rastreamento_sync import RastreamentoSyncService
from ...services.tracking_codes import normalize_tracking_code, tracking_code_expression, lock_tracking_codes
router = APIRouter()


@router.get("/", response_model=List[RastreamentoComPedido])
def listar_rastreamentos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[RastreamentoStatus] = None,
    ativo: bool = True,
    cliente_id: Optional[uuid.UUID] = None,
    pedido_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Lista rastreamentos com filtros opcionais"""
    query = db.query(Rastreamento).filter(Rastreamento.ativo == ativo)
    
    if cliente_id:
        query = query.filter(Rastreamento.cliente_id == cliente_id)
    if pedido_id:
        query = query.filter(Rastreamento.pedido_id == pedido_id)
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
            "rastreio_info": r.rastreio_info or {},
            "custo_emissao": r.custo_emissao,
            "pedido_id": r.pedido_id,
            "cliente_id": r.cliente_id,
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
    
    codigo = normalize_tracking_code(rastreamento.codigo_rastreio)
    if not codigo:
        raise HTTPException(422, "Informe o código de rastreio.")
    pedido, cliente = validate_tracking_links(
        db, pedido_id=rastreamento.pedido_id, cliente_id=rastreamento.cliente_id,
    )
    lock_tracking_codes(db, [codigo])
    existing = db.query(Rastreamento).filter(tracking_code_expression(Rastreamento.codigo_rastreio) == codigo).first()
    if existing:
        raise HTTPException(409, "Código de rastreamento já cadastrado, inclusive no histórico arquivado.")
    data = rastreamento.model_dump()
    data.update(codigo_rastreio=codigo, cliente_id=cliente.id if cliente else None)
    db_rastreamento = Rastreamento(**data, created_by=current_user.id)
    from ...services.customer_reconciliation import auto_link_tracking
    auto_link_tracking(db, db_rastreamento)
    db.add(db_rastreamento)
    try:
        db.flush()
        if pedido:
            RastreamentoSyncService.sincronizar_rastreamento_com_pedido(db, db_rastreamento)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Este código já foi cadastrado. Atualize a lista antes de continuar.")
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
        "cliente_id": rastreamento.cliente_id,
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
        tracking_code_expression(Rastreamento.codigo_rastreio) == normalize_tracking_code(codigo),
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
        "cliente_id": rastreamento.cliente_id,
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
    
    update_data = rastreamento_update.model_dump(exclude_unset=True)
    previous_pedido_id = db_rastreamento.pedido_id
    # Lock parent rows before any code/parcel lock, matching receipt confirmation.
    parent_ids = {value for value in (previous_pedido_id, update_data.get("pedido_id")) if value}
    if parent_ids:
        db.query(Pedido.id).filter(Pedido.id.in_(parent_ids)).order_by(Pedido.id).with_for_update().all()
    if "codigo_rastreio" in update_data:
        codigo = normalize_tracking_code(update_data["codigo_rastreio"] or "")
        if not codigo:
            raise HTTPException(422, "Informe o código de rastreio.")
        update_data["codigo_rastreio"] = codigo
        lock_tracking_codes(db, [codigo])
        if db.query(Rastreamento.id).filter(tracking_code_expression(Rastreamento.codigo_rastreio) == codigo,
                                           Rastreamento.id != db_rastreamento.id).first():
            raise HTTPException(409, "Código de rastreamento já cadastrado. Confira os vínculos.")
    db_rastreamento = db.query(Rastreamento).filter(Rastreamento.id == rastreamento_id).populate_existing().with_for_update().first()
    if not db_rastreamento or not db_rastreamento.ativo or db_rastreamento.pedido_id != previous_pedido_id:
        raise HTTPException(409, "O vínculo do rastreio mudou. Atualize os dados antes de continuar.")
    if "pedido_id" in update_data or "cliente_id" in update_data:
        requested_order = update_data.get("pedido_id", db_rastreamento.pedido_id)
        if previous_pedido_id and requested_order and previous_pedido_id != requested_order:
            raise HTTPException(409, "Desvincule o rastreio do pedido atual antes de transferi-lo.")
        _, cliente = validate_tracking_links(
            db, pedido_id=requested_order,
            cliente_id=update_data.get("cliente_id", db_rastreamento.cliente_id),
            allow_inactive_customer=update_data.get("cliente_id", db_rastreamento.cliente_id) == db_rastreamento.cliente_id,
        )
        update_data["cliente_id"] = cliente.id if cliente else None
    previous_code = db_rastreamento.codigo_rastreio
    for field, value in update_data.items():
        setattr(db_rastreamento, field, value)
    try:
        db.flush()
        if previous_pedido_id and (previous_pedido_id != db_rastreamento.pedido_id or previous_code != db_rastreamento.codigo_rastreio):
            previous_order = db.query(Pedido).filter(Pedido.id == previous_pedido_id).with_for_update().first()
            if previous_order and previous_order.codigo_rastreio == previous_code:
                remaining = db.query(Rastreamento).filter(Rastreamento.pedido_id == previous_pedido_id,
                    Rastreamento.ativo == True).order_by(Rastreamento.created_at.desc()).first()
                previous_order.codigo_rastreio = remaining.codigo_rastreio if remaining else None
            if previous_order:
                RastreamentoSyncService.atualizar_status_por_pacotes(db, previous_order)
        if db_rastreamento.pedido_id:
            RastreamentoSyncService.sincronizar_rastreamento_com_pedido(db, db_rastreamento)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Código de rastreamento já cadastrado. Confira os vínculos.")
    db.refresh(db_rastreamento)
    return db_rastreamento


@router.delete("/{rastreamento_id}")
def deletar_rastreamento(
    rastreamento_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Soft delete de um rastreamento"""
    db_rastreamento = lock_tracking_row(db, rastreamento_id)
    
    if not db_rastreamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rastreamento não encontrado"
        )
    
    db_rastreamento.ativo = False
    RastreamentoSyncService.sincronizar_rastreamento_com_pedido(db, db_rastreamento)
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
    
    # Rastreamentos recentes (últimos 12)
    recentes = db.query(Rastreamento).filter(
        Rastreamento.ativo == True
    ).order_by(desc(Rastreamento.updated_at)).limit(12).all()
    
    return RastreamentoResumo(
        total_rastreamentos=total,
        em_transito=em_transito,
        entregues=entregues,
        pendentes=pendentes,
        com_erro=com_erro,
        rastreamentos_recentes=recentes
    )


# ─── Calcular frete (Correios) ───────────────────────────────────────────────

@router.post("/calcular-frete")
def calcular_frete_endpoint(
    body: dict,
    current_user: Usuario = Depends(get_current_user),
):
    """Calculates freight cost and delivery time via Correios public API."""
    from ...services.correios_service import calcular_frete

    cep_origem = (body.get("cep_origem") or "").strip()
    cep_destino = (body.get("cep_destino") or "").strip()
    peso = float(body.get("peso") or 0.3)

    if not cep_origem or not cep_destino:
        raise HTTPException(status_code=400, detail="CEP de origem e destino são obrigatórios")

    try:
        resultados = calcular_frete(cep_origem, cep_destino, peso)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"resultados": resultados}


# ─── Wonca API helpers ──────────────────────────────────────────────────────────

def _build_response(r: Rastreamento) -> dict:
    """Build the standard RastreamentoComPedido dict for a single object."""
    return {
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
        "rastreio_info": r.rastreio_info or {},
        "custo_emissao": r.custo_emissao,
        "pedido_id": r.pedido_id,
        "cliente_id": r.cliente_id,
        "data_criacao": r.data_criacao,
        "ativo": r.ativo,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
        "created_by": r.created_by,
        "numero_pedido": r.pedido.numero_pedido if r.pedido else None,
        "cliente_nome_pedido": r.pedido.cliente_nome if r.pedido else None,
        "cliente_telefone": r.pedido.cliente_telefone if r.pedido else None,
        "endereco_entrega": r.pedido.endereco_entrega if r.pedido else None,
    }


# ─── Consultar (sem salvar) ─────────────────────────────────────────────────────

@router.post("/consultar")
def consultar_rastreamento(
    body: dict,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Consulta rastreamento na Wonca API sem persistir no banco."""
    from ...services.wonca_service import parse_tracking

    raw_code = body.get("codigo", "")
    if not isinstance(raw_code, str) or len(raw_code) > 100:
        raise HTTPException(422, "Código de rastreio inválido.")
    codigo = normalize_tracking_code(raw_code)
    if not codigo:
        raise HTTPException(status_code=400, detail="Código de rastreio não informado")

    try:
        events, meta, inferred = parse_tracking(codigo)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "codigo": codigo,
        "status": inferred.value,
        "eventos": events,
        "rastreio_info": meta,
        "sucesso": bool(events),
    }


# ─── Consultar e Salvar ─────────────────────────────────────────────────────────

@router.post("/consultar-e-salvar")
def consultar_e_salvar_rastreamento(
    body: dict,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Consulta na Wonca API e cria ou atualiza o rastreamento no banco."""
    from ...services.wonca_service import parse_tracking

    raw_code = body.get("codigo", "")
    if not isinstance(raw_code, str) or len(raw_code) > 100:
        raise HTTPException(422, "Código de rastreio inválido.")
    codigo = normalize_tracking_code(raw_code)
    if not codigo:
        raise HTTPException(status_code=400, detail="Código de rastreio não informado")

    from ...services.tracking_refresh import TrackingVersion, apply_provider_results
    before = db.query(Rastreamento).filter(tracking_code_expression(Rastreamento.codigo_rastreio) == codigo).first()
    if before and not before.ativo:
        raise HTTPException(409, "Este rastreio está arquivado. Revise o cadastro antes de reutilizá-lo.")
    version = TrackingVersion.capture(before) if before else None
    try:
        events, meta, inferred = parse_tracking(codigo)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if version:
        changed, skipped = apply_provider_results(db, [(version, events, meta, inferred)])
        if skipped:
            raise HTTPException(409, "O rastreio foi alterado durante a consulta. Atualize para consultar novamente.")
        db.commit()
        db.refresh(changed[0])
        return _build_response(changed[0])

    lock_tracking_codes(db, [codigo])
    if db.query(Rastreamento.id).filter(tracking_code_expression(Rastreamento.codigo_rastreio) == codigo).first():
        raise HTTPException(409, "Este código foi cadastrado durante a consulta. Atualize a lista antes de continuar.")

    new_r = Rastreamento(
        codigo_rastreio=codigo,
        status=inferred,
        historico_eventos=events,
        rastreio_info=meta,
        ultima_atualizacao=settings.now(),
        created_by=current_user.id,
    )
    db.add(new_r)
    db.commit()
    db.refresh(new_r)
    return _build_response(new_r)


# ─── Atualizar individual via Wonca ────────────────────────────────────────────

@router.post("/{rastreamento_id}/atualizar")
def atualizar_rastreamento_online(
    rastreamento_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Busca dados atualizados na Wonca API para um rastreamento existente."""
    from ...services.wonca_service import parse_tracking

    r = db.query(Rastreamento).filter(
        Rastreamento.id == rastreamento_id,
        Rastreamento.ativo == True,
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rastreamento não encontrado")

    from ...services.tracking_refresh import TrackingVersion, apply_provider_results
    version = TrackingVersion.capture(r)
    try:
        events, meta, inferred = parse_tracking(version.code)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    changed, skipped = apply_provider_results(db, [(version, events, meta, inferred)])
    if skipped:
        raise HTTPException(409, "O rastreio foi alterado durante a consulta. Atualize para consultar novamente.")
    db.commit()
    db.refresh(changed[0])
    return _build_response(changed[0])


# ─── Atualizar todos via Wonca ──────────────────────────────────────────────────

@router.post("/atualizar-todos")
def atualizar_todos_rastreamentos(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Atualiza todos os rastreamentos ativos (exceto entregues) via Wonca API."""
    from ...services.tracking_refresh import refresh_active
    result = refresh_active(db)
    db.commit()
    return result
