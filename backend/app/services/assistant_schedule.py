"""Folgas share the ERP calendar; writes are confirmed, permission checked and transactional."""
import uuid
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models.assistant import AssistantAction, AssistantMessage, utcnow
from ..models.folga import Folga, TipoFolga
from ..models.usuario import Usuario
from ..models.vendedor import Vendedor
from .assistant_queries import DatedArgs, contains, date_filter, page, period_info, scalar


class ScheduleArgs(DatedArgs):
    tipo: TipoFolga | None = None
    aprovacao: Literal["todas", "aprovadas", "pendentes"] = "todas"


class ScheduleWriteArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    vendedor: str = Field(min_length=2, max_length=100, description="Nome do vendedor informado pelo usuário.")
    data: date = Field(description="Data explicitamente solicitada, AAAA-MM-DD. Pergunte se ausente.")
    tipo: TipoFolga = TipoFolga.FOLGA
    periodo: Literal["COMPLETO", "MANHA", "TARDE"] = "COMPLETO"
    motivo: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def half_day(self):
        if self.tipo == TipoFolga.MEIO_PERIODO and self.periodo == "COMPLETO":
            raise ValueError("Meio período exige MANHA ou TARDE.")
        if self.periodo != "COMPLETO" and self.tipo == TipoFolga.FOLGA:
            self.tipo = TipoFolga.MEIO_PERIODO
        return self


def query_schedule(db, args):
    q = db.query(Folga, Vendedor.nome).join(Vendedor, Vendedor.id == Folga.vendedor_id).filter(
        Folga.ativo.is_(True), Vendedor.ativo.is_(True))
    if args.termo:
        from .assistant_knowledge import employee_candidates
        q = q.filter(Vendedor.id.in_([v.id for v in employee_candidates(db, args.termo)]))
    if args.tipo:
        q = q.filter(Folga.tipo == args.tipo)
    if args.aprovacao != "todas":
        q = q.filter(Folga.aprovado.is_(args.aprovacao == "aprovadas"))
    q = date_filter(q, Folga.data, args)
    rows, info = page(q.order_by(Folga.data, Vendedor.nome, Folga.id), args)
    # Personal/medical reasons are intentionally not published in group calendar queries.
    return {**info, "periodo": period_info(args, "dia da folga"), "resultados": [
        {"vendedor": name, "data": scalar(f.data), "tipo": scalar(f.tipo), "periodo": f.periodo,
         "aprovada": f.aprovado} for f, name in rows],
        "aviso": "Calendário de vendedores do ERP; cadastro e aprovação são estados diferentes."}


def may_schedule(db, message, identity):
    user = db.get(Usuario, message.user_id)
    return bool(identity.active and identity.user_id == message.user_id and identity.can_register
                and user and user.ativo and scalar(user.role) in ("ADMIN", "GERENTE"))


def action_preview(action):
    if action.kind == "apelido":
        from .assistant_knowledge import alias_preview
        return alias_preview(action)
    if action.kind in ("frete_emitir","frete_imprimir"):
        from .assistant_freight import preview
        return preview(action)
    if action.kind == "impressao":
        from .assistant_printing import print_preview
        return print_preview(action)
    p = action.payload
    from .assistant_controls import preview_reply
    return preview_reply(action, (f"Cadastrar no calendário: {p['vendedor_nome']} — {p['data']} — {p['tipo']} — {p['periodo']}.\n"
            + (f"Motivo informado: {p['motivo']}\n" if p.get("motivo") else "") +
            "Será registrada como pendente de aprovação, igual ao cadastro pelo ERP.\n"
            "Diga ‘confirmo’ para cadastrar ou ‘cancela’ para descartar. "
            f"Ainda não foi cadastrada. A confirmação expira em 24 horas.\nIdentificador da prévia: {action.id}"))


def prepare_schedule(db, message, identity, args):
    if not message.should_reply or not may_schedule(db, message, identity):
        return {"erro": "Cadastro de folgas exige ADMIN/GERENTE com permissão de registro no assistente e pedido direto."}
    previous = db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if previous:
        return {"confirmacao": action_preview(previous)}
    from .assistant_knowledge import employee_candidates
    candidates = employee_candidates(db, args.vendedor)
    if len(candidates) != 1:
        return {"erro": "Não foi possível identificar uma única pessoa. Consulte consultar_equipe e escolha entre os candidatos.",
                "candidatos": [v.nome for v in candidates]}
    vendor = candidates[0]
    existing = db.query(Folga).filter_by(vendedor_id=vendor.id, data=args.data, ativo=True).first()
    if existing:
        return {"erro": "Já existe um registro nesse dia. Nenhuma folga foi duplicada.", "data": scalar(existing.data), "tipo": scalar(existing.tipo)}
    action = AssistantAction(source_message_id=message.id, user_id=message.user_id, kind="folga",
        payload={**args.model_dump(mode="json", exclude={"vendedor"}), "vendedor_id": str(vendor.id), "vendedor_nome": vendor.nome})
    db.add(action)
    db.flush()
    return {"confirmacao": action_preview(action)}


def confirm_action(db, message, identity, action, cancel=False):
    source = db.get(AssistantMessage, action.source_message_id)
    if action.user_id != message.user_id or source.channel != message.channel or source.conversation_id != message.conversation_id:
        return "Confirme na mesma conversa e com o usuário que pediu o cadastro."
    if not may_schedule(db, message, identity):
        return "Você não tem permissão para executar esta ação pelo assistente."
    if action.status != "draft":
        return f"Essa solicitação está {action.status}. Nenhuma alteração foi repetida."
    created = action.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=utcnow().tzinfo)
    if created < utcnow() - timedelta(hours=24):
        return "Solicitação expirada. Envie o pedido novamente."
    if cancel:
        action.status = "cancelled"
        if action.kind=="frete_imprimir":return "Impressão cancelada. A etiqueta já emitida não foi cancelada nem reembolsada."
        return "Pedido cancelado. Nenhuma ação executada."
    if action.kind == "apelido":
        from .assistant_knowledge import confirm_alias
        return confirm_alias(db, message, action)
    if action.kind in ("frete_emitir","frete_imprimir"):
        from .assistant_freight import confirm
        return confirm(db,message,action)
    if action.kind == "impressao":
        from .assistant_printing import enqueue_print
        return enqueue_print(db, action)
    if action.kind != "folga":
        return "Tipo de ação não permitido."
    p = action.payload
    # Serializes competing assistant confirmations for the same seller.
    vendor = db.query(Vendedor).filter_by(id=uuid.UUID(p["vendedor_id"]), ativo=True).with_for_update().first()
    if not vendor:
        return "Vendedor inativo ou não encontrado. Nenhuma folga cadastrada."
    day = date.fromisoformat(p["data"])
    existing = db.query(Folga).filter_by(vendedor_id=vendor.id, data=day, ativo=True).first()
    if existing:
        action.status = "cancelled"
        return "Já existe um registro nesse dia. Nenhuma folga foi duplicada."
    folga = Folga(vendedor_id=vendor.id, data=day, tipo=TipoFolga(p["tipo"]), periodo=p["periodo"],
                  motivo=p.get("motivo"), aprovado=False, ativo=True)
    db.add(folga)
    db.flush()
    action.status, action.result_id, action.executed_at = "executed", folga.id, utcnow()
    return (f"Folga cadastrada no ERP: {vendor.nome}, {day.strftime('%d/%m/%Y')}, {p['tipo']}, {p['periodo']}. "
            "Status: pendente de aprovação. Já aparece no calendário de folgas.")
