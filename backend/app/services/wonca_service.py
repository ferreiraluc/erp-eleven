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
        return resp.json()
    except http_requests.RequestException as e:
        raise ValueError(f"Erro ao consultar API de rastreio: {str(e)}")


def _s(val) -> str:
    """Safe string coercion."""
    return str(val).strip() if val is not None else ""


def _unwrap(raw: dict) -> dict:
    """
    Wonca wraps the actual Correios payload as a JSON-encoded string under 'json'.
    Parse and return it; fall back to the outer dict if not present.
    """
    json_field = raw.get("json")
    if isinstance(json_field, str):
        try:
            return _json.loads(json_field)
        except Exception:
            pass
    return raw


def extract_meta(inner: dict) -> dict:
    """
    Extract top-level metadata from the unwrapped Wonca inner dict.
    Returns a dict with non-null, human-readable fields.
    """
    tipo_postal = inner.get("tipoPostal") or {}
    meta: dict = {}

    tipo_servico = _s(tipo_postal.get("descricao") or "")
    if tipo_servico:
        meta["tipo_servico"] = tipo_servico

    categoria = _s(tipo_postal.get("categoria") or "")
    if categoria:
        meta["categoria"] = categoria

    sigla = _s(tipo_postal.get("sigla") or "")
    if sigla:
        meta["sigla"] = sigla

    data_prevista = _s(inner.get("dtPrevista") or "")
    if data_prevista:
        meta["data_prevista"] = data_prevista

    if inner.get("atrasado"):
        meta["atrasado"] = True

    return meta


def normalize_events(raw: dict) -> list:
    """
    Normalize any Wonca response shape into a list of EventoRastreio-compatible dicts.
    Each item: { data, local, local_tipo, situacao, situacao_frontend, detalhes,
                 codigo_evento, destino_cidade, destino_uf }
    """
    inner = _unwrap(raw)
    raw_list: list = []

    # Direct keys on inner dict (Correios via Wonca uses "eventos")
    for key in ("eventos", "events", "evento"):
        if key in inner and isinstance(inner[key], list):
            raw_list = inner[key]
            break

    # Wrapped shapes: { result: {...}, tracking: {...}, data: {...} }
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

    result = []
    for ev in raw_list:
        if not isinstance(ev, dict):
            continue

        # ── Date ─────────────────────────────────────────────────────────
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

        # ── Location (origin unit) ────────────────────────────────────────
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

        local_tipo = _s(unidade.get("tipo") or "")

        # ── Destination unit ─────────────────────────────────────────────
        destino_cidade = ""
        destino_uf = ""
        unidade_dest = ev.get("unidadeDestino")
        if isinstance(unidade_dest, dict):
            end_dest = unidade_dest.get("endereco") if isinstance(unidade_dest.get("endereco"), dict) else {}
            destino_cidade = _s(end_dest.get("cidade") or "")
            destino_uf = _s(end_dest.get("uf") or "")

        # ── Description ──────────────────────────────────────────────────
        situacao = _s(
            ev.get("descricao") or ev.get("description") or
            ev.get("descricaoFrontEnd") or ev.get("situacao") or
            ev.get("status") or ev.get("tipo") or ""
        )
        situacao_frontend = _s(ev.get("descricaoFrontEnd") or "")
        detalhes = _s(
            ev.get("detalhe") or ev.get("detail") or ev.get("detalhes") or
            ev.get("subStatus") or ev.get("comentario") or ev.get("complemento") or ""
        )
        codigo_evento = _s(ev.get("codigo") or "")

        if not situacao:
            continue

        entry: dict = {
            "data": date_val,
            "local": local,
            "situacao": situacao,
            "detalhes": detalhes,
        }
        if local_tipo:
            entry["local_tipo"] = local_tipo
        if situacao_frontend and situacao_frontend != situacao:
            entry["situacao_frontend"] = situacao_frontend
        if destino_cidade:
            entry["destino_cidade"] = destino_cidade
            entry["destino_uf"] = destino_uf
        if codigo_evento:
            entry["codigo_evento"] = codigo_evento

        result.append(entry)

    return result


def infer_status(events: list) -> RastreamentoStatus:
    """Derive a RastreamentoStatus from the most recent event description."""
    if not events:
        return RastreamentoStatus.PENDENTE

    latest = events[0].get("situacao", "").lower()

    # Frases de NÃO entrega devem ser checadas ANTES das de entrega,
    # pois "entregue" é substring de "não entregue" e causaria falso-positivo.
    errors = [
        "não entregue", "nao entregue",
        "objeto não entregue", "objeto nao entregue",
        "carteiro não atendido", "carteiro nao atendido",
        "destinatário ausente", "destinatario ausente",
        "devolvido", "extraviado",
        "recusado", "retornou ao remetente", "destruído", "indenizado",
        "mudou-se", "ausente", "cancelado", "roubado",
        "não foi entregue", "nao foi entregue",
    ]
    delivered = [
        "entregue ao destinatário", "entregue ao destinatario",
        "objeto entregue", "delivered",
    ]
    transit = [
        "encaminhado", "trânsito", "transito", "saiu para entrega",
        "transferência", "transferencia", "distribuição", "distribuicao",
        "veículo de entrega", "postado", "coletado", "triagem",
        "aguardando retirada", "em processamento", "objeto recebido",
        "objeto em transferência", "objeto postado",
    ]

    # Erros/não-entrega primeiro para evitar falso positivo com "entregue"
    for kw in errors:
        if kw in latest:
            return RastreamentoStatus.ERRO
    for kw in delivered:
        if kw in latest:
            return RastreamentoStatus.ENTREGUE
    for kw in transit:
        if kw in latest:
            return RastreamentoStatus.EM_TRANSITO

    return RastreamentoStatus.EM_TRANSITO


def parse_tracking(code: str) -> tuple:
    """
    Fetch and fully parse tracking data for a code.
    Returns (events: list, meta: dict, inferred_status: RastreamentoStatus).
    """
    raw = fetch_tracking_raw(code)
    inner = _unwrap(raw)
    events = normalize_events(raw)
    meta = extract_meta(inner)
    inferred = infer_status(events)
    logger.info(f"[Wonca] {code}: {len(events)} eventos, status={inferred.value}")
    return events, meta, inferred
