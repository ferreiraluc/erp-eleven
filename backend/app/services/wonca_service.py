import requests as http_requests
import logging
from ..models.rastreamento import RastreamentoStatus
from ..config import settings

logger = logging.getLogger(__name__)

WONCA_URL = "https://api-labs.wonca.com.br/wonca.labs.v1.LabsService/Track"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Apikey {settings.WONCA_API_KEY}",
    }


def fetch_tracking_raw(code: str) -> dict:
    """Call Wonca API and return raw JSON response."""
    try:
        resp = http_requests.post(
            WONCA_URL,
            headers=_headers(),
            json={"code": code},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"[Wonca raw] {code}: {data}")
        return data
    except http_requests.RequestException as e:
        raise ValueError(f"Erro ao consultar API de rastreio: {str(e)}")


def _s(val) -> str:
    """Safe string coercion."""
    return str(val).strip() if val is not None else ""


def normalize_events(raw: dict) -> list:
    """
    Normalize any Wonca response shape into a list of EventoRastreio-compatible dicts.
    Each item: { data, local, situacao, detalhes }
    """
    raw_list: list = []

    # Try direct keys first
    for key in ("events", "eventos", "evento"):
        if key in raw and isinstance(raw[key], list):
            raw_list = raw[key]
            break

    # Try wrapped shapes: { result: {...}, tracking: {...}, data: {...} }
    if not raw_list:
        for wrapper in ("result", "tracking", "data"):
            w = raw.get(wrapper)
            if isinstance(w, dict):
                for key in ("events", "eventos", "evento"):
                    if key in w and isinstance(w[key], list):
                        raw_list = w[key]
                        break
            if raw_list:
                break

    # Correios-style: { objeto: [{ evento: [...] }] }
    if not raw_list and "objeto" in raw:
        objs = raw["objeto"]
        if isinstance(objs, list) and objs:
            for key in ("evento", "eventos", "events"):
                v = objs[0].get(key) if isinstance(objs[0], dict) else None
                if isinstance(v, list):
                    raw_list = v
                    break

    result = []
    for ev in raw_list:
        if not isinstance(ev, dict):
            continue

        # Date + time
        date_val = _s(
            ev.get("data") or ev.get("date") or ev.get("eventDate") or
            ev.get("dataHora") or ev.get("dateTime") or ""
        )
        hora = _s(ev.get("hora") or ev.get("time") or "")
        if hora and hora not in date_val:
            date_val = f"{date_val} {hora}".strip()

        # Location
        unidade = ev.get("unidade") if isinstance(ev.get("unidade"), dict) else {}
        cidade = _s(ev.get("cidade") or ev.get("city") or unidade.get("cidade") or "")
        uf = _s(ev.get("uf") or ev.get("state") or unidade.get("uf") or "")
        local = _s(ev.get("local") or ev.get("location") or "")
        if not local and cidade:
            local = f"{cidade}/{uf}" if uf else cidade

        # Description
        situacao = _s(
            ev.get("descricao") or ev.get("description") or ev.get("situacao") or
            ev.get("status") or ev.get("tipo") or ""
        )
        detalhes = _s(
            ev.get("detalhe") or ev.get("detail") or ev.get("detalhes") or
            ev.get("subStatus") or ev.get("complemento") or ""
        )

        if situacao:
            result.append({
                "data": date_val,
                "local": local,
                "situacao": situacao,
                "detalhes": detalhes,
            })

    return result


def infer_status(events: list) -> RastreamentoStatus:
    """Derive a RastreamentoStatus from the most recent event description."""
    if not events:
        return RastreamentoStatus.PENDENTE

    latest = events[0].get("situacao", "").lower()

    delivered = [
        "entregue ao destinatário", "entregue", "delivered",
        "objeto entregue",
    ]
    errors = [
        "devolvido", "extraviado", "não entregue", "nao entregue",
        "recusado", "retornou ao remetente", "destruído", "indenizado",
        "mudou-se", "ausente", "cancelado", "roubado",
    ]
    transit = [
        "encaminhado", "trânsito", "transito", "saiu para entrega",
        "transferência", "transferencia", "distribuição", "distribuicao",
        "veículo de entrega", "postado", "coletado", "triagem",
        "aguardando retirada", "em processamento", "objeto recebido",
    ]

    for kw in delivered:
        if kw in latest:
            return RastreamentoStatus.ENTREGUE
    for kw in errors:
        if kw in latest:
            return RastreamentoStatus.ERRO
    for kw in transit:
        if kw in latest:
            return RastreamentoStatus.EM_TRANSITO

    # Has events but description unrecognised → assume in transit
    return RastreamentoStatus.EM_TRANSITO
