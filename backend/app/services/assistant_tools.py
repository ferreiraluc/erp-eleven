"""Validated operational tools; no arbitrary SQL or unrestricted database writes."""
import uuid
from typing import Literal
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field

from ..models.assistant import AssistantNote, utcnow
from .assistant_queries import (
    ShipmentArgs, OrderArgs, StockArgs, CustomerArgs, SalesArgs, literal_pattern,
    query_shipments, query_orders, query_stock, query_customers, query_sales,
)
from .assistant_schedule import ScheduleArgs, ScheduleWriteArgs, query_schedule, prepare_schedule


from .assistant_printing import AddressArgs, prepare_print


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    termo: str = Field(min_length=2, max_length=100)


class NoteArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["atendimento", "devolucao", "pedido", "venda", "endereco", "geral"]
    conteudo: str = Field(min_length=5, max_length=900)


def search_orders(db, termo):
    # Compatibility for internal callers; tool calls validate their complete filters below.
    return query_shipments(db, ShipmentArgs.model_construct(termo=termo, ordem="priorizar_abertos"))


def search_memory(db, termo):
    # Only explicitly confirmed team knowledge crosses channels; drafts/transcripts never do.
    notes = db.query(AssistantNote).filter(
        AssistantNote.status == "shared", AssistantNote.content.ilike(literal_pattern(termo), escape="\\"),
    ).order_by(AssistantNote.confirmed_at.desc()).limit(8).all()
    return [{"id": str(n.id), "tipo": n.kind, "conteudo": n.content,
             "registrado_em": n.confirmed_at.isoformat(), "natureza": "Relato de funcionário; não comprova lançamento financeiro ou estoque."} for n in notes]


def draft_note(db, message, identity, tipo, conteudo):
    if not identity.can_register:
        return {"erro": "Usuário sem permissão para registrar ocorrências."}
    note = db.query(AssistantNote).filter_by(source_message_id=message.id).first()
    if not note:
        note = AssistantNote(source_message_id=message.id, user_id=message.user_id, kind=tipo, content=conteudo)
        db.add(note)
        db.flush()
    return {"rascunho_id": str(note.id), "conteudo": note.content, "estado": note.status,
            "confirmacao": f"/confirmar {note.id}", "aviso": "Confirmar compartilha com a equipe nos dois canais. Não lança venda, estoque ou reembolso."}


def confirm_note(db, message, identity, note_id, cancel=False):
    if not identity.can_register:
        return "Você não tem permissão para registrar ocorrências."
    try:
        note_uuid = uuid.UUID(note_id.strip())
    except ValueError:
        return "Informe o identificador completo do rascunho."
    note = db.query(AssistantNote).filter_by(id=note_uuid, user_id=message.user_id).with_for_update().first()
    if not note:
        return "Rascunho não encontrado para o seu usuário."
    if note.status != "draft":
        return f"Esse registro já está no estado: {note.status}. Nenhuma alteração foi repetida."
    # SQLite tests may return naive timestamps; persisted PostgreSQL timestamps are aware.
    created = note.created_at.replace(tzinfo=utcnow().tzinfo) if note.created_at.tzinfo is None else note.created_at
    if created < utcnow() - timedelta(hours=24):
        return "Rascunho expirado. Envie novamente as informações para preparar outro."
    note.status = "cancelled" if cancel else "shared"
    note.confirmed_at = None if cancel else utcnow()
    if cancel:
        return "Rascunho cancelado."
    return f"Registro {note.id} salvo na memória da equipe, disponível no WhatsApp e Telegram. Isso não altera vendas, estoque ou pagamentos."


class TrackingReplyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str = Field(min_length=2, max_length=100, description="Código exato retornado pela consulta atual, nunca inventado.")


def tool(name, description, schema):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": schema.model_json_schema()}}


TOOLS = [
    tool("preparar_impressao", "Prepara uma folha A4 com UM endereço explicitamente solicitado. BR exige CEP, UF e remetente debora ou mona; PY nunca imprime remetente. Pergunte dados faltantes, não invente. Mostra prévia; confirmação humana envia à fila. Não emite frete nem declaração de conteúdo.", AddressArgs),
    tool("buscar_rastreios", "Consulta envios e códigos por nome/telefone/pedido/código OU sem termo para listagens, períodos e totais por status. em_aberto inclui PENDENTE, EM_TRANSITO e falhas. Para rastreio individual use ordem=priorizar_abertos; para último/mais recente use recentes.", ShipmentArgs),
    tool("responder_rastreio", "FINALIZA rastreio individual em duas mensagens: código sozinho e depois detalhes do ERP. Use após buscar_rastreios, com um código retornado e inequivocamente identificado. Não use para listagens ou se faltou identificar o cliente.", TrackingReplyArgs),
    tool("consultar_pedidos", "Consulta cadastro/status administrativo dos pedidos, inclusive sem código, por nome, período e situação. Entrega física é em buscar_rastreios.", OrderArgs),
    tool("consultar_estoque", "Consulta produtos ativos: nome/SKU/marca/categoria, tamanho, cor, saldos na loja/depósito, zerados e abaixo do mínimo; preço de venda com moeda. Não altera estoque.", StockArgs),
    tool("consultar_clientes", "Procura clientes ativos nos cadastros separados de pedidos e PDV. Envios avulsos podem não ter cliente cadastrado.", CustomerArgs),
    tool("consultar_vendas", "Lista vendas e totais por período/vendedor, separados por módulo (vendas/PDV) e moeda. ADMIN/GERENTE. Nunca somar módulos como faturamento consolidado.", SalesArgs),
    tool("consultar_folgas", "Consulta calendário de folgas/férias/faltas/licenças dos vendedores, por nome, período, tipo e aprovação. Sem período pode listar histórico; para agenda futura use datas ou proximos_7_dias.", ScheduleArgs),
    tool("preparar_folga", "Prepara cadastro REAL no calendário do ERP. Apenas solicitação explícita de ADMIN/GERENTE habilitado. Exige vendedor e data; não invente dados. Aplicação mostra prévia e exige confirmação do autor antes de gravar. Não aprova folgas.", ScheduleWriteArgs),
    tool("buscar_memoria", "Consulta registros operacionais compartilhados e confirmados pela equipe nos dois canais.", SearchArgs),
    tool("preparar_registro", "Prepara um único rascunho factual de ocorrência relatada nesta mensagem. Exige confirmação humana para compartilhar. Não altera pedido/venda/estoque; folgas usam preparar_folga.", NoteArgs),
]


def execute_tool(db, message, identity, name, arguments):
    if name == "preparar_impressao":
        return prepare_print(db, message, identity, AddressArgs.model_validate(arguments))
    queries = {
        "buscar_rastreios": (ShipmentArgs, query_shipments),
        "consultar_pedidos": (OrderArgs, query_orders),
        "consultar_estoque": (StockArgs, query_stock),
        "consultar_clientes": (CustomerArgs, query_customers),
        "consultar_folgas": (ScheduleArgs, query_schedule),
    }
    if name in queries:
        schema, function = queries[name]
        return function(db, schema.model_validate(arguments))
    if name == "consultar_vendas":
        return query_sales(db, SalesArgs.model_validate(arguments), message.user_id)
    if name == "preparar_folga":
        return prepare_schedule(db, message, identity, ScheduleWriteArgs.model_validate(arguments))
    if name == "buscar_memoria":
        return search_memory(db, **SearchArgs.model_validate(arguments).model_dump())
    if name == "preparar_registro":
        return draft_note(db, message, identity, **NoteArgs.model_validate(arguments).model_dump())
    return {"erro": "Ferramenta não permitida."}
