"""Confirmed tracking registration from a receipt, without storing the image."""
import re
import uuid
from datetime import timedelta

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from ..models.assistant import AssistantAction, AssistantMessage, utcnow
from ..models.cliente import Cliente
from ..models.pedido import Pedido, PedidoStatus
from ..models.rastreamento import Rastreamento, RastreamentoStatus
from .assistant_controls import normalized, preview_reply
from .assistant_schedule import may_schedule
from .customer_links import validate_tracking_links
from .tracking_codes import lock_tracking_codes, tracking_code_expression
from .receipt_vision import ReceiptError, ReceiptObject, download_image, extract_receipt, is_image

KIND = "rastreio_comprovante"


class ReceiptArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mensagem_id: uuid.UUID | None = None


def receipt_intent(content):
    value = normalized(content)
    if re.search(r"\b(?:nao|nunca|sem)\b.{0,25}\b(?:cadastr|registr|adicion|inclu|salv|extra|lei|ler)", value):
        return False
    operation = re.search(r"\b(?:cadastr\w*|registr\w*|adicion\w*|inclu\w*|salv\w*|extrai\w*|extraia|leia|ler|lanc\w*)\b", value)
    topic = re.search(r"\b(?:rastreios?|rastreamentos?|comprovantes?|correios|postagem)\b", value)
    return bool(operation and topic)


def _source(db, message, source_id):
    if message.channel != "telegram":
        return None
    query = db.query(AssistantMessage).filter(
        AssistantMessage.user_id == message.user_id,
        AssistantMessage.channel == message.channel,
        AssistantMessage.conversation_id == message.conversation_id,
        AssistantMessage.created_at <= message.created_at,
        AssistantMessage.created_at >= utcnow() - timedelta(hours=24),
        AssistantMessage.attachment.isnot(None),
    )
    if source_id:
        source = query.filter(AssistantMessage.id == source_id).first()
        return source if source and is_image(source.attachment) else None
    if is_image(message.attachment):
        return message
    # A recent PDF must never be interpreted as the photo, nor may another author's
    # picture be picked from the group. Limit avoids scanning an unbounded history.
    return next((row for row in query.order_by(AssistantMessage.created_at.desc()).limit(32)
                 if is_image(row.attachment)), None)


def _existing(db, code):
    # Legacy codes may have lowercase letters or spaces. Inactive entries also own
    # their code and must not be silently reactivated by a receipt.
    return db.query(Rastreamento).filter(
        tracking_code_expression(Rastreamento.codigo_rastreio) == code,
    ).order_by(Rastreamento.created_at, Rastreamento.id).first()


def _order_link(db, item):
    query = db.query(Pedido).filter(Pedido.status.in_([PedidoStatus.PENDENTE, PedidoStatus.PROCESSANDO, PedidoStatus.ENVIADO]))
    coded = query.filter(tracking_code_expression(Pedido.codigo_rastreio) == item.codigo).limit(2).all()
    if len(coded) == 1:
        return coded[0], "Código já informado nesse pedido."
    if len(coded) > 1:
        return None, "Mais de um pedido já contém esse código; vínculo precisa de revisão no ERP."
    if not item.destinatario:
        return None, "Destinatário não legível; será cadastrado sem vínculo automático."
    # Conservative exact-name match, including case, with no fuzzy guessing based
    # on a partial name or a previous shipment. Closed orders are never reopened.
    name = item.destinatario.casefold()
    matches = query.outerjoin(Cliente, Cliente.id == Pedido.cliente_id).filter(
        or_(Pedido.codigo_rastreio.is_(None), Pedido.codigo_rastreio == ""),
        or_(func.lower(func.trim(Pedido.cliente_nome)) == name,
            (Cliente.ativo.is_(True)) & (func.lower(func.trim(Cliente.nome)) == name)),
    ).limit(2).all()
    if len(matches) == 1:
        return matches[0], "Nome exato de um único pedido aberto sem rastreio. Confira o vínculo."
    return None, ("Há vários pedidos desse destinatário; nenhum será escolhido automaticamente."
                  if matches else "Sem pedido aberto identificado com segurança; vínculo pode ser feito no ERP.")


def receipt_preview(action):
    rows = action.payload["objetos"]
    lines = [f"Conferir comprovante: {len(rows)} rastreio(s) novo(s)."]
    for item in rows:
        lines.append("\n" + item["codigo"])
        lines.append("Destinatário: " + (item.get("destinatario") or "não legível / não informado"))
        if item.get("cidade") or item.get("uf"):
            lines.append("Destino: " + " / ".join(v for v in (item.get("cidade"), item.get("uf")) if v))
        lines.append("Pedido: " + item["pedido_numero"] if item.get("pedido_numero") else "Pedido: sem vínculo automático.")
        if item.get("pedido_cliente_id"):
            lines.append("Cliente vinculado: " + (item.get("pedido_cliente_nome") or item["pedido_cliente_id"]))
        if item.get("vinculo_aviso"):
            lines.append(item["vinculo_aviso"])
    duplicates = action.payload.get("ja_cadastrados", [])
    if duplicates:
        lines.append("\nJá cadastrados e ignorados: " + ", ".join(duplicates))
    lines.append("\nConfira os códigos e destinatários com a foto original. Confirmar cadastra somente os itens acima no ERP, com status pendente de consulta. A foto não será arquivada. Se algum dado estiver errado, cancele e reenvie uma foto mais nítida. Prévia válida por 24h.")
    return preview_reply(action, "\n".join(lines))


def prepare_receipt(db, message, identity, args):
    if not message.should_reply or not may_schedule(db, message, identity):
        return {"erro": "Cadastro por comprovante exige gestor habilitado e pedido direto."}
    if not receipt_intent(message.text):
        return {"erro": "Peça explicitamente: ‘Cadastre os rastreios deste comprovante’. A foto sozinha não autoriza o cadastro."}
    previous = db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if previous:
        return ({"confirmacao": receipt_preview(previous)} if previous.kind == KIND and previous.status == "draft"
                else {"erro": "Esta solicitação já possui uma prévia ou foi concluída. Consulte as prévias existentes."})
    source = _source(db, message, args.mensagem_id)
    if not source:
        return {"erro": "Envie a foto do comprovante (JPG ou PNG) nesta conversa do Telegram e peça para cadastrar os rastreios. Use uma foto sua enviada nas últimas 24h."}
    try:
        objects = extract_receipt(download_image(source.attachment))
    except ReceiptError as exc:
        return {"erro": str(exc)}
    rows, duplicates = [], []
    for item in objects:
        if _existing(db, item.codigo):
            duplicates.append(item.codigo)
            continue
        order, reason = _order_link(db, item)
        customer = None
        if order and order.cliente_id:
            # A preview is a read: acquiring parent locks in photograph order can
            # deadlock against another preview with the reverse package order.
            # Confirmation locks sorted parents and revalidates the relationship.
            customer = db.get(Cliente, order.cliente_id)
            if not customer or not customer.ativo:
                order, customer = None, None
                reason = "O cadastro vinculado ao pedido precisa de revisão; nenhum vínculo será aplicado."
        rows.append({**item.model_dump(), "pedido_id": str(order.id) if order else None,
                     "pedido_numero": order.numero_pedido if order else None,
                     "pedido_destinatario_esperado": order.cliente_nome if order else None,
                     "pedido_codigo_esperado": order.codigo_rastreio if order else None,
                     "pedido_cliente_id": str(order.cliente_id) if order and order.cliente_id else None,
                     "pedido_cliente_nome": customer.nome if customer else None,
                     "vinculo_aviso": reason})
    # The minimal extracted data is sufficient for the preview and registration.
    # Erase Telegram's download reference immediately; no raw OCR/image snapshot.
    source.attachment = None
    if not rows:
        return {"erro": "Todos os códigos lidos já estão no ERP. Nenhum rastreio foi duplicado: " + ", ".join(duplicates)}
    action = AssistantAction(source_message_id=message.id, user_id=message.user_id, kind=KIND,
        payload={"objetos": rows, "ja_cadastrados": duplicates, "attachment_message_id": str(source.id),
                 "recipient": ", ".join(dict.fromkeys(row.get("destinatario") or row["codigo"] for row in rows))[:200]})
    db.add(action)
    db.flush()
    return {"confirmacao": receipt_preview(action)}


def confirm_receipt(db, message, action):
    """Called only after confirm_action checks author/conversation/permission/expiry."""
    if action.status != "draft":
        return "Esta solicitação já foi concluída. Nenhum cadastro foi repetido."
    rows = action.payload["objetos"]
    # Revalidate the stored payload before writing; a model cannot bypass code checks.
    try:
        for row in rows:
            ReceiptObject.model_validate({key: row.get(key) for key in ("codigo", "destinatario", "cidade", "uf")})
    except ValueError:
        return "A prévia contém um código inválido. Cancele e envie o comprovante novamente."
    # Shared order with web/sync: Pedido -> normalized code -> Rastreamento.
    # One deterministic order for a batch avoids locking A/B and B/A concurrently.
    order_ids = sorted({uuid.UUID(row["pedido_id"]) for row in rows if row.get("pedido_id")}, key=str)
    if order_ids:
        db.query(Pedido).filter(Pedido.id.in_(order_ids)).order_by(Pedido.id).with_for_update().all()
    lock_tracking_codes(db, [row["codigo"] for row in rows])
    orders, customers = {}, {}
    # Validate every approved association before mutating anything, including when
    # several parcels intentionally refer to the same order in this single preview.
    for row in rows:
        if not row.get("pedido_id") or _existing(db, row["codigo"]):
            continue
        order = db.query(Pedido).filter_by(id=uuid.UUID(row["pedido_id"])).with_for_update().first()
        if (not order or order.status not in (PedidoStatus.PENDENTE, PedidoStatus.PROCESSANDO, PedidoStatus.ENVIADO)
                or order.codigo_rastreio != row.get("pedido_codigo_esperado")
                or order.cliente_nome != row.get("pedido_destinatario_esperado")
                or order.numero_pedido != row.get("pedido_numero")
                or (str(order.cliente_id) if order.cliente_id else None) != row.get("pedido_cliente_id")):
            return "Um pedido da prévia mudou. Nenhum rastreio foi cadastrado. Cancele a prévia e envie novamente para conferir o vínculo atualizado."
        try:
            _, customer = validate_tracking_links(db, pedido_id=order.id, cliente_id=order.cliente_id)
        except HTTPException:
            return "O cliente ou pedido da prévia não está mais disponível para esse vínculo. Nenhum rastreio foi cadastrado. Revise no ERP antes de reenviar."
        orders[str(order.id)] = order
        customers[str(order.id)] = customer
    created, skipped = [], []
    for row in rows:
        if _existing(db, row["codigo"]):
            skipped.append(row["codigo"])
            continue
        order = orders.get(row.get("pedido_id"))
        customer = customers.get(row.get("pedido_id"))
        tracking = Rastreamento(
            codigo_rastreio=row["codigo"], destinatario=row.get("destinatario"),
            destino=" / ".join(v for v in (row.get("cidade"), row.get("uf")) if v) or None,
            status=RastreamentoStatus.PENDENTE, pedido_id=order.id if order else None,
            cliente_id=customer.id if customer else None,
            descricao="Cadastrado a partir de comprovante conferido no Telegram.", created_by=message.user_id,
        )
        try:
            with db.begin_nested():
                from .customer_reconciliation import auto_link_tracking
                auto_link_tracking(db, tracking)
                db.add(tracking)
                db.flush()
        except IntegrityError:
            if not _existing(db, row["codigo"]):
                raise
            skipped.append(row["codigo"])
            continue
        if order and not order.codigo_rastreio:
            order.codigo_rastreio = row["codigo"]
        created.append(tracking)
    action.status = "executed"
    action.executed_at = utcnow()
    action.result_id = created[0].id if created else None
    action.payload = {**action.payload, "resultados": [{"codigo": row.codigo_rastreio, "id": str(row.id)} for row in created]}
    result = f"{len(created)} rastreio(s) cadastrado(s) no ERP, pendente(s) de consulta aos Correios. A foto não foi arquivada."
    if skipped:
        result += " Já existentes, sem duplicar: " + ", ".join(skipped) + "."
    return result
