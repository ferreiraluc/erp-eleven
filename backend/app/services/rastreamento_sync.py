from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from ..models.pedido import Pedido, PedidoStatus
from ..models.rastreamento import Rastreamento, RastreamentoStatus
from ..models.usuario import Usuario
import uuid

class RastreamentoSyncService:
    """Serviço para sincronização bidirecional entre pedidos e rastreamentos"""

    @staticmethod
    def mapear_status_pedido_para_rastreamento(pedido_status: PedidoStatus) -> RastreamentoStatus:
        """Mapeia status de pedido para status de rastreamento"""
        mapeamento = {
            PedidoStatus.PENDENTE: RastreamentoStatus.PENDENTE,
            PedidoStatus.PROCESSANDO: RastreamentoStatus.PENDENTE,
            PedidoStatus.ENVIADO: RastreamentoStatus.EM_TRANSITO,
            PedidoStatus.ENTREGUE: RastreamentoStatus.ENTREGUE,
            PedidoStatus.CANCELADO: RastreamentoStatus.ERRO
        }
        return mapeamento.get(pedido_status, RastreamentoStatus.PENDENTE)

    @staticmethod
    def mapear_status_rastreamento_para_pedido(rastreamento_status: RastreamentoStatus) -> PedidoStatus:
        """Mapeia status de rastreamento para status de pedido"""
        mapeamento = {
            RastreamentoStatus.PENDENTE: PedidoStatus.PROCESSANDO,
            RastreamentoStatus.EM_TRANSITO: PedidoStatus.ENVIADO,
            RastreamentoStatus.ENTREGUE: PedidoStatus.ENTREGUE,
            RastreamentoStatus.ERRO: PedidoStatus.CANCELADO,
            RastreamentoStatus.NAO_ENCONTRADO: PedidoStatus.CANCELADO
        }
        return mapeamento.get(rastreamento_status, PedidoStatus.PENDENTE)

    @staticmethod
    def buscar_ou_criar_rastreamento(
        db: Session,
        codigo_rastreio: str,
        pedido: Pedido,
        user_id: uuid.UUID
    ) -> tuple[Rastreamento, bool]:
        """
        Busca rastreamento existente ou cria novo se não existir

        Returns:
            tuple: (rastreamento, foi_criado)
        """
        # Buscar rastreamento existente
        rastreamento_existente = db.query(Rastreamento).filter(
            Rastreamento.codigo_rastreio == codigo_rastreio
        ).first()

        if rastreamento_existente:
            # Se já existe, apenas associar ao pedido se ainda não estiver associado
            if rastreamento_existente.pedido_id != pedido.id:
                rastreamento_existente.pedido_id = pedido.id

                # Sincronizar status se necessário
                status_esperado = RastreamentoSyncService.mapear_status_pedido_para_rastreamento(pedido.status)
                if rastreamento_existente.status == RastreamentoStatus.PENDENTE:
                    rastreamento_existente.status = status_esperado

            return rastreamento_existente, False

        # Criar novo rastreamento
        novo_rastreamento = Rastreamento(
            codigo_rastreio=codigo_rastreio,
            pedido_id=pedido.id,
            status=RastreamentoSyncService.mapear_status_pedido_para_rastreamento(pedido.status),
            descricao=pedido.descricao,
            destinatario=pedido.cliente_nome,
            destino=pedido.endereco_entrega,
            created_by=user_id
        )

        db.add(novo_rastreamento)
        return novo_rastreamento, True

    @staticmethod
    def sincronizar_pedido_com_rastreamento(
        db: Session,
        pedido: Pedido,
        user_id: uuid.UUID
    ) -> Optional[Rastreamento]:
        """
        Sincroniza pedido com rastreamento quando código de rastreio é adicionado/atualizado
        """
        if not pedido.codigo_rastreio:
            return None

        rastreamento, foi_criado = RastreamentoSyncService.buscar_ou_criar_rastreamento(
            db, pedido.codigo_rastreio, pedido, user_id
        )

        # Salvar mudanças
        db.flush()

        return rastreamento

    @staticmethod
    def sincronizar_rastreamento_com_pedido(
        db: Session,
        rastreamento: Rastreamento
    ) -> Optional[Pedido]:
        """
        Sincroniza rastreamento com pedido quando status do rastreamento é atualizado
        """
        if not rastreamento.pedido_id:
            return None

        pedido = db.query(Pedido).filter(Pedido.id == rastreamento.pedido_id).first()
        if not pedido:
            return None

        # Atualizar status do pedido baseado no status do rastreamento
        novo_status = RastreamentoSyncService.mapear_status_rastreamento_para_pedido(rastreamento.status)

        # Só atualizar se o status for diferente e fizer sentido na progressão
        if pedido.status != novo_status:
            # Evitar retrocessos desnecessários (ex: ENTREGUE -> EM_TRANSITO)
            if not (pedido.status == PedidoStatus.ENTREGUE and novo_status in [PedidoStatus.ENVIADO, PedidoStatus.PROCESSANDO]):
                pedido.status = novo_status

        # Garantir que o código de rastreio esteja sincronizado
        if not pedido.codigo_rastreio:
            pedido.codigo_rastreio = rastreamento.codigo_rastreio

        return pedido

    @staticmethod
    def buscar_rastreamento_por_codigo(db: Session, codigo_rastreio: str) -> Optional[Rastreamento]:
        """Busca rastreamento por código"""
        return db.query(Rastreamento).filter(
            Rastreamento.codigo_rastreio == codigo_rastreio
        ).first()

    @staticmethod
    def buscar_pedido_por_rastreamento(db: Session, codigo_rastreio: str) -> Optional[Pedido]:
        """Busca pedido associado a um código de rastreamento"""
        return db.query(Pedido).filter(
            Pedido.codigo_rastreio == codigo_rastreio
        ).first()