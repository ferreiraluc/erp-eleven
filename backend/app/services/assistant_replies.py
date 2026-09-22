"""A persisted response may be delivered as several ordered, independently retried messages."""
from datetime import datetime, timezone

from ..config import settings


class Reply(str):
    def __new__(cls, parts):
        result = super().__new__(cls, "\n\n".join(parts))
        result.parts = parts
        return result


def text_reply(text, channel):
    limit = 3500 if channel == "telegram" else 1500
    parts = []
    while len(text) > limit:
        position = text.rfind("\n", 0, limit)
        if position < limit // 2:
            position = text.rfind(" ", 0, limit)
        if position < limit // 2:
            position = limit
        parts.append(text[:position].rstrip())
        text = text[position:].lstrip()
    if text:
        parts.append(text)
    return Reply(parts)


def tracking_reply(row):
    status = {"PENDENTE": "Pendente", "EM_TRANSITO": "Em trânsito", "ENTREGUE": "Entregue",
              "ERRO": "Erro na consulta do rastreio", "NAO_ENCONTRADO": "Rastreio não encontrado",
              "CANCELADO": "Pedido cancelado"}.get(row["status"], row["status"])
    details = [f"Cliente: {row.get('cliente') or 'não informado'}", f"Status: {status}"]
    if row.get("pedido"):
        details.append(f"Pedido: {row['pedido']}")
    if row.get("data_envio"):
        label = "Data do pedido" if row["origem"] == "pedido_sem_rastreamento" else "Envio cadastrado em"
        details.append(f"{label}: {datetime.fromisoformat(row['data_envio']).strftime('%d/%m/%Y')}")
    if row.get("consultado_em"):
        stamp = datetime.fromisoformat(row["consultado_em"])
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        details.append(f"Atualização no ERP: {stamp.astimezone(settings.tz).strftime('%d/%m/%Y %H:%M')} ({settings.TIMEZONE})")
    details.append("Dados salvos no ERP.")
    return Reply([row["codigo"], "\n".join(details)])


class DocumentReply(str):
    def __new__(cls,text,url):
        result=super().__new__(cls,text)
        result.document_url=url
        return result
