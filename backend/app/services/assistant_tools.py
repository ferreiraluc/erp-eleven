"""Narrow ERP tools: lookup and draft operational notes, never arbitrary database edits."""
import uuid
from typing import Literal
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_

from ..models.assistant import AssistantNote, utcnow
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    termo: str = Field(min_length=2, max_length=100)


class NoteArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["atendimento", "devolucao", "pedido", "venda", "endereco", "geral"]
    conteudo: str = Field(min_length=5, max_length=900)


def literal_pattern(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def search_orders(db, termo):
    pattern = literal_pattern(termo.strip())
    orders = db.query(Pedido).filter(or_(
        Pedido.cliente_nome.ilike(pattern, escape="\\"),
        Pedido.numero_pedido.ilike(pattern, escape="\\"),
        Pedido.codigo_rastreio.ilike(pattern, escape="\\"),
        Pedido.cliente_telefone.ilike(pattern, escape="\\"),
    )).order_by(Pedido.created_at.desc()).limit(6).all()
    results = []
    for order in orders:
        tracks = db.query(Rastreamento).filter_by(pedido_id=order.id, ativo=True).all()
        results.append({
            "pedido": order.numero_pedido, "cliente": order.cliente_nome,
            "data": order.created_at.isoformat() if order.created_at else None,
            "status_pedido": order.status.value, "codigo_cadastrado": order.codigo_rastreio,
            "rastreios": [{"codigo": r.codigo_rastreio, "status": r.status.value,
                           "consultado_em": r.ultima_atualizacao.isoformat() if r.ultima_atualizacao else None} for r in tracks],
        })
    # Independent shipments need to be searchable too.
    unlinked = db.query(Rastreamento).filter(
        Rastreamento.ativo.is_(True), Rastreamento.pedido_id.is_(None),
        or_(Rastreamento.destinatario.ilike(pattern, escape="\\"), Rastreamento.codigo_rastreio.ilike(pattern, escape="\\")),
    ).order_by(Rastreamento.created_at.desc()).limit(6).all()
    results.extend({"pedido": None, "cliente": r.destinatario, "codigo_cadastrado": r.codigo_rastreio,
                    "status": r.status.value, "consultado_em": r.ultima_atualizacao.isoformat() if r.ultima_atualizacao else None} for r in unlinked)
    return {"resultados": results, "instrucao": "Se houver múltiplos clientes/envios, peça identificação. Dados do ERP; não é consulta online aos Correios."}


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


TOOLS = [
    {"type": "function", "function": {"name": "buscar_rastreios", "description": "Busca pedidos e rastreios por nome, número de pedido, telefone ou código.", "parameters": SearchArgs.model_json_schema()}},
    {"type": "function", "function": {"name": "buscar_memoria", "description": "Consulta registros operacionais compartilhados e confirmados pela equipe nos dois canais.", "parameters": SearchArgs.model_json_schema()}},
    {"type": "function", "function": {"name": "preparar_registro", "description": "Prepara um único rascunho factual de ocorrência relatada nesta mensagem. Exige confirmação humana para compartilhar. Não altera o pedido/venda/estoque.", "parameters": NoteArgs.model_json_schema()}},
]


def execute_tool(db, message, identity, name, arguments):
    if name == "buscar_rastreios":
        return search_orders(db, **SearchArgs.model_validate(arguments).model_dump())
    if name == "buscar_memoria":
        return search_memory(db, **SearchArgs.model_validate(arguments).model_dump())
    if name == "preparar_registro":
        return draft_note(db, message, identity, **NoteArgs.model_validate(arguments).model_dump())
    return {"erro": "Ferramenta não permitida."}
