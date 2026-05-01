import requests
import xml.etree.ElementTree as ET
import logging
import re

logger = logging.getLogger(__name__)

CORREIOS_CALC_URL = "http://ws.correios.com.br/calculador/CalcPrecoPrazo.aspx"

SERVICOS = {
    "40010": "SEDEX",
    "40045": "SEDEX a Cobrar",
    "40215": "SEDEX 10",
    "41106": "PAC",
    "40290": "SEDEX Hoje",
}


def _clean_cep(cep: str) -> str:
    return re.sub(r"\D", "", cep)


def calcular_frete(cep_origem: str, cep_destino: str, peso: float = 0.3) -> list:
    """
    Calculate freight cost and deadline via Correios public API.
    Returns list of dicts: { servico, codigo, valor, prazo, erro }.
    peso in kg (default 300g).
    """
    cep_orig = _clean_cep(cep_origem)
    cep_dest = _clean_cep(cep_destino)

    if len(cep_orig) != 8 or len(cep_dest) != 8:
        raise ValueError("CEP inválido — deve conter 8 dígitos")

    try:
        resp = requests.get(
            CORREIOS_CALC_URL,
            params={
                "nCdEmpresa": "",
                "sDsSenha": "",
                "sCepOrigem": cep_orig,
                "sCepDestino": cep_dest,
                "nVlPeso": str(peso),
                "nCdFormato": "1",
                "nVlComprimento": "20",
                "nVlAltura": "5",
                "nVlLargura": "15",
                "nCdServico": "40010,41106",
                "nVlDiametro": "0",
                "StrRetorno": "xml",
                "nIndicaCalculo": "3",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Erro ao consultar Correios: {str(e)}")

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        raise ValueError(f"Erro ao processar resposta dos Correios: {str(e)}")

    results = []
    for servico in root.findall(".//cServico"):
        codigo = (servico.findtext("Codigo") or "").strip()
        valor = (servico.findtext("Valor") or "").strip()
        prazo = (servico.findtext("PrazoEntrega") or "").strip()
        erro = (servico.findtext("Erro") or "0").strip()
        msg_erro = (servico.findtext("MsgErro") or "").strip()

        if erro not in ("", "0"):
            results.append({
                "servico": SERVICOS.get(codigo, codigo),
                "codigo": codigo,
                "valor": None,
                "prazo": None,
                "erro": msg_erro or f"Erro {erro}",
            })
        else:
            results.append({
                "servico": SERVICOS.get(codigo, codigo),
                "codigo": codigo,
                "valor": valor,
                "prazo": int(prazo) if prazo.isdigit() else None,
                "erro": None,
            })

    if not results:
        raise ValueError("Nenhum resultado retornado pelos Correios")

    return results
