import json as _json
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
        return data
    except http_requests.RequestException as e:
        raise ValueError(f"Erro ao consultar API de rastreio: {str(e)}")


def _s(val) -> str:
    """Safe string coercion."""
    return str(val).strip() if val is not None else ""


def _unwrap(raw: dict) -> dict:
    """
    Wonca wraps the actual tracking payload as a JSON-encoded string under the
    key 'json'.  Unwrap it when present; otherwise return the dict as-is.
    """
    json_field = raw.get("json")
    if isinstance(json_field, str):
        try:
            return _json.loads(json_field)
        except Exception:
            pass
    return raw


def normalize_events(raw: dict) -> list:
    """
    Normalize any Wonca response shape into a list of EventoRastreio-compatible dicts.
    Each item: { data, local, situacao, detalhes }
    """
    # Unwrap the double-encoded JSON if present
    inner = _unwrap(raw)

    raw_list: list = []

    # Direct keys on inner dict (Correios via Wonca uses "eventos")
    for key in ("eventos", "events", "evento"):
        if key in inner and isinstance(inner[key], list):
            raw_list = inner[key]
            break

    # Try wrapped shapes: { result: {...}, tracking: {...}, data: {...} }
    if not raw_list:
        for wrapper in ("result", "tracking", "data"):
            w = inner.get(wrapper)
            if isinstance(w, dict):
                for key in ("eventos", "events", "evento"):
                    if key in w and isinstance(w[key], list):
                        raw_list = w[key]
                        break
            if raw_list:
                break

    # Correios-style: { objeto: [{ evento: [...] }] }
    if not raw_list and "objeto" in inner:
        objs = inner["objeto"]
        if isinstance(objs, list) and objs:
            for key in ("evento", "eventos", "events"):
                v = objs[0].get(key) if isinstance(objs[0], dict) else None
                if isinstance(v, list):
                    raw_list = v
                    break

    logger.info(f"[Wonca normalize] found {len(raw_list)} raw events")

    result = []
    for ev in raw_list:
        if not isinstance(ev, dict):
            continue

        # Date: prefer dtHrCriado.date (Correios via Wonca), fall back to flat fields
        dthrcriado = ev.get("dtHrCriado")
        if isinstance(dthrcriado, dict):
            date_val = _s(dthrcriado.get("date", ""))
        else:
            date_val = _s(
                ev.get("data") or ev.get("date") or ev.get("eventDate") or
                ev.get("dataHora") or ev.get("dateTime") or ""
            )
        hora = _s(ev.get("hora") or ev.get("time") or "")
        if hora and hora not in date_val:
            date_val = f"{date_val} {hora}".strip()

        # Location: unidade.endereco.cidade/uf (Correios via Wonca)
        unidade = ev.get("unidade") if isinstance(ev.get("unidade"), dict) else {}
        endereco = unidade.get("endereco") if isinstance(unidade.get("endereco"), dict) else {}
        cidade = _s(
            ev.get("cidade") or ev.get("city") or
            endereco.get("cidade") or unidade.get("cidade") or ""
        )
        uf = _s(
            ev.get("uf") or ev.get("state") or
            endereco.get("uf") or unidade.get("uf") or ""
        )
        local = _s(ev.get("local") or ev.get("location") or "")
        if not local and cidade:
            local = f"{cidade}/{uf}" if uf else cidade

        # Description: descricao primary, descricaoFrontEnd fallback
        situacao = _s(
            ev.get("descricao") or ev.get("description") or
            ev.get("descricaoFrontEnd") or ev.get("situacao") or
            ev.get("status") or ev.get("tipo") or ""
        )
        detalhes = _s(
            ev.get("detalhe") or ev.get("detail") or ev.get("detalhes") or
            ev.get("subStatus") or ev.get("comentario") or ev.get("complemento") or ""
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
        "objeto em transferência", "objeto postado",
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
