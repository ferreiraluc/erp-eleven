"""Keep explicit order/parcel links coherent without inventing shipping events."""
from typing import Optional
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.pedido import Pedido, PedidoStatus
from ..models.rastreamento import Rastreamento, RastreamentoStatus
from .customer_links import validate_tracking_links
from .tracking_codes import normalize_tracking_code, tracking_code_expression, lock_tracking_codes


class RastreamentoSyncService:
    @staticmethod
    def mapear_status_pedido_para_rastreamento(pedido_status: PedidoStatus) -> RastreamentoStatus:
        return {
            PedidoStatus.PENDENTE: RastreamentoStatus.PENDENTE,
            PedidoStatus.PROCESSANDO: RastreamentoStatus.PENDENTE,
            PedidoStatus.ENVIADO: RastreamentoStatus.EM_TRANSITO,
            PedidoStatus.ENTREGUE: RastreamentoStatus.ENTREGUE,
            PedidoStatus.CANCELADO: RastreamentoStatus.ERRO,
        }.get(pedido_status, RastreamentoStatus.PENDENTE)

    @staticmethod
    def mapear_status_rastreamento_para_pedido(rastreamento_status: RastreamentoStatus) -> PedidoStatus:
        return {
            RastreamentoStatus.PENDENTE: PedidoStatus.PROCESSANDO,
            RastreamentoStatus.EM_TRANSITO: PedidoStatus.ENVIADO,
            RastreamentoStatus.ENTREGUE: PedidoStatus.ENTREGUE,
        }.get(rastreamento_status, PedidoStatus.PROCESSANDO)

    @staticmethod
    def buscar_ou_criar_rastreamento(db: Session, codigo_rastreio: str, pedido: Pedido,
                                   user_id: uuid.UUID) -> tuple[Rastreamento, bool]:
        codigo_rastreio = normalize_tracking_code(codigo_rastreio)
        if not codigo_rastreio:
            raise HTTPException(422, "Informe o código de rastreio.")
        db.query(Pedido.id).filter(Pedido.id == pedido.id).with_for_update().first()
        lock_tracking_codes(db, [codigo_rastreio])
        pedido.codigo_rastreio = codigo_rastreio
        existing = db.query(Rastreamento).filter(
            tracking_code_expression(Rastreamento.codigo_rastreio) == codigo_rastreio,
        ).with_for_update().first()
        if existing:
            if not existing.ativo:
                raise HTTPException(409, "Este rastreio está arquivado. Revise o cadastro antes de reutilizá-lo.")
            if existing.pedido_id and existing.pedido_id != pedido.id:
                raise HTTPException(409, "Este rastreio já está vinculado a outro pedido. Desvincule-o explicitamente antes.")
            _, cliente = validate_tracking_links(
                db, pedido_id=pedido.id, cliente_id=existing.cliente_id, allow_inactive_customer=True,
            )
            existing.cliente_id = cliente.id if cliente else None
            existing.pedido_id = pedido.id
            # Linking an order never overwrites a provider's actual status or recipient.
            return existing, False
        row = Rastreamento(
            codigo_rastreio=codigo_rastreio, pedido_id=pedido.id, cliente_id=pedido.cliente_id,
            status=RastreamentoStatus.PENDENTE, descricao=pedido.descricao,
            destinatario=pedido.cliente_nome, destino=pedido.endereco_entrega, created_by=user_id,
        )
        db.add(row)
        return row, True

    @staticmethod
    def sincronizar_pedido_com_rastreamento(db: Session, pedido: Pedido,
                                          user_id: uuid.UUID) -> Optional[Rastreamento]:
        if not pedido.codigo_rastreio:
            return None
        row, _ = RastreamentoSyncService.buscar_ou_criar_rastreamento(db, pedido.codigo_rastreio, pedido, user_id)
        db.flush()
        return row

    @staticmethod
    def atualizar_status_por_pacotes(db: Session, pedido: Pedido) -> None:
        db.flush()
        parcels = db.query(Rastreamento).filter(
            Rastreamento.pedido_id == pedido.id, Rastreamento.ativo == True,
        ).order_by(Rastreamento.data_criacao.desc(), Rastreamento.created_at.desc(), Rastreamento.id).all()
        codes = {normalize_tracking_code(parcel.codigo_rastreio) for parcel in parcels}
        if normalize_tracking_code(pedido.codigo_rastreio or '') not in codes:
            pedido.codigo_rastreio = parcels[0].codigo_rastreio if parcels else None
        # No active parcel is not evidence of delivery/cancellation. Explicitly cancelled
        # orders stay cancelled. Errors cannot cancel a commercial order.
        if not parcels or pedido.status == PedidoStatus.CANCELADO:
            return
        states = {p.status for p in parcels}
        if states == {RastreamentoStatus.ENTREGUE}:
            pedido.status = PedidoStatus.ENTREGUE
        elif states & {RastreamentoStatus.EM_TRANSITO, RastreamentoStatus.ENTREGUE}:
            pedido.status = PedidoStatus.ENVIADO
        elif pedido.status in (PedidoStatus.PENDENTE, PedidoStatus.PROCESSANDO, PedidoStatus.ENTREGUE):
            pedido.status = PedidoStatus.PROCESSANDO

    @staticmethod
    def sincronizar_rastreamento_com_pedido(db: Session, rastreamento: Rastreamento) -> Optional[Pedido]:
        if not rastreamento.pedido_id:
            return None
        pedido = db.query(Pedido).filter(Pedido.id == rastreamento.pedido_id).with_for_update().first()
        if not pedido:
            return None
        RastreamentoSyncService.atualizar_status_por_pacotes(db, pedido)
        if not pedido.codigo_rastreio and rastreamento.ativo:
            pedido.codigo_rastreio = rastreamento.codigo_rastreio
        return pedido

    @staticmethod
    def buscar_rastreamento_por_codigo(db: Session, codigo_rastreio: str) -> Optional[Rastreamento]:
        return db.query(Rastreamento).filter(tracking_code_expression(Rastreamento.codigo_rastreio) == normalize_tracking_code(codigo_rastreio)).first()

    @staticmethod
    def buscar_pedido_por_rastreamento(db: Session, codigo_rastreio: str) -> Optional[Pedido]:
        row = RastreamentoSyncService.buscar_rastreamento_por_codigo(db, codigo_rastreio)
        if row and row.pedido_id:
            return db.get(Pedido, row.pedido_id)
        return db.query(Pedido).filter(tracking_code_expression(Pedido.codigo_rastreio) == normalize_tracking_code(codigo_rastreio)).first()
