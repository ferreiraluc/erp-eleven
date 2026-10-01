"""4Devs public form adapter and manual JSON review; never saves automatically."""
import base64
import json
import threading
import time
import uuid
from typing import Literal

import requests
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError

from ..models.assistant import utcnow
from ..models.printing import PrintSender
from ..schemas.address_book import AddressData, SenderInput

PROVIDER_PAGE = "https://www.4devs.com.br/gerador_de_pessoas"
# This is the target observed in the site's own form, not their announced REST API.
FORM_URL = "https://www.4devs.com.br/ferramentas_online.php"
MAX_RESPONSE_BYTES = 64 * 1024
FIELDS = ("nome", "idade", "cpf", "rg", "data_nasc", "sexo", "signo", "mae", "pai", "email", "senha",
          "cep", "endereco", "numero", "bairro", "cidade", "estado", "telefone_fixo", "celular", "altura", "peso", "tipo_sanguineo", "cor")
STATES = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
_generation_lock = threading.Lock()
_last_generation: dict[str, float] = {}


def fail(code, message, status=400):
    raise HTTPException(status, {"code": code, "message": message, "provider_page": PROVIDER_PAGE})


class GeneratePersonArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sexo: Literal["I", "M", "F"] = "I"
    idade: int | None = Field(default=None, ge=18, le=90)
    estado: str = Field(default="", max_length=2)

    @model_validator(mode="after")
    def state(self):
        self.estado = self.estado.upper()
        if self.estado and self.estado not in STATES:
            raise ValueError("Estado inválido.")
        return self


class ImportPersonArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    json_text: str = Field(min_length=2, max_length=30000)


class SaveGeneratedSenderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_key: uuid.UUID
    approved: Literal[True]
    source: Literal["4devs_web_form", "4devs_json_import"]
    name: str = Field(min_length=1, max_length=100)
    data: AddressData
    active: bool = True


def check_rate_limit(user_id):
    now = time.monotonic()
    key = str(user_id)
    with _generation_lock:
        for candidate, stamp in list(_last_generation.items()):
            if now - stamp > 60:
                del _last_generation[candidate]
        if now - _last_generation.get(key, -60) < 10:
            fail("rate_limited", "Aguarde alguns segundos antes de gerar outra pessoa.", 429)
        if len(_last_generation) >= 1000:
            fail("rate_limited", "Limite temporário de geração atingido. Tente mais tarde.", 429)
        _last_generation[key] = now


def person_preview(value, source):
    if isinstance(value, list):
        if len(value) != 1:
            fail("one_person", "Importe exatamente uma pessoa por vez.")
        value = value[0]
    if not isinstance(value, dict) or not isinstance(value.get("nome"), str) or not value["nome"].strip():
        fail("invalid_json", "O conteúdo precisa ser o JSON de uma pessoa, com nome e campos de endereço.")
    person = {}
    for key in FIELDS:
        field = value.get(key)
        if field is None:
            person[key] = ""
        elif isinstance(field, (str, int, float)) and not isinstance(field, bool):
            clean = " ".join(str(field).split())
            if len(clean) > 250:
                fail("invalid_json", "Um campo do JSON é muito longo. Revise os dados antes de importar.")
            person[key] = clean
        else:
            fail("invalid_json", "Os campos da pessoa devem conter texto simples, sem estruturas aninhadas.")
    mapped = {key: person.get(key, "") for key in ("nome", "cpf", "endereco", "numero", "bairro", "cidade", "estado", "cep", "email")}
    mapped.update(pais="BR", telefone=person["celular"] or person["telefone_fixo"], complemento="")
    try:
        data = AddressData.model_validate(mapped).model_dump()
    except ValueError:
        fail("invalid_json", "Os dados excedem os limites do cadastro. Revise nome, documento, contato e endereço.")
    return {"person": person, "sender_data": data, "source": source, "synthetic": True,
            "provider_page": PROVIDER_PAGE, "saved": False}


def import_person(args):
    try:
        value = json.loads(args.json_text)
    except (ValueError, TypeError):
        fail("invalid_json", "Cole o JSON copiado no 4Devs, sem outros textos.")
    return person_preview(value, "4devs_json_import")


def generate_person(args, user_id):
    check_rate_limit(user_id)
    try:
        with requests.post(
            FORM_URL,
            data={"acao": "gerar_pessoa", "sexo": args.sexo, "pontuacao": "S", "idade": args.idade or "",
                  "cep_estado": args.estado, "txt_qtde": "1", "cep_cidade": ""},
            headers={"User-Agent": "ERP-Eleven/1.0", "Accept": "application/json", "Referer": PROVIDER_PAGE},
            stream=True, timeout=(5, 20), allow_redirects=False,
        ) as response:
            if response.status_code in (403, 429):
                fail("provider_blocked", "O 4Devs limitou o acesso ou precisa de verificação no site. Abra o gerador e importe o JSON manualmente.", 503)
            if response.status_code != 200:
                fail("provider_unavailable", "O formulário do 4Devs não respondeu. Você pode abrir o site e importar o JSON.", 502)
            raw = bytearray()
            for chunk in response.iter_content(8192):
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    fail("provider_unavailable", "A resposta do 4Devs ficou maior que o esperado. Use a importação de JSON.", 502)
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            # HTML/captcha is never parsed or worked around. No cookies/proxies/retries.
            fail("provider_blocked", "O 4Devs precisa ser aberto no navegador. Gere uma pessoa no site e importe o JSON.", 503)
        try:
            return person_preview(payload, "4devs_web_form")
        except HTTPException:
            fail("provider_unavailable", "O formulário devolveu dados diferentes do esperado. Abra o site e importe o JSON.", 502)
    except requests.RequestException:
        fail("provider_unavailable", "Não foi possível conectar ao 4Devs. Tente mais tarde ou importe o JSON do site.", 502)


def sender_lines(data):
    d = data.model_dump()
    return [value for value in (
        d["nome"], ", ".join(value for value in (d["endereco"], d["numero"]) if value), d["bairro"], d["complemento"],
        " - ".join(value for value in (d["cidade"], d["estado"]) if value),
        "CEP " + d["cep"] if d["cep"] else "", "CPF/CNPJ: " + d["cpf"] if d["cpf"] else "",
    ) if value]


def save_generated_sender(db, user, args):
    if args.data.pais != "BR" or not args.data.nome.strip():
        fail("review_required", "Revise o nome e o país Brasil antes de salvar o remetente.")
    # Use only sender fields. The generated password/RG/parents and the raw JSON
    # deliberately do not become persistent records.
    try:
        validated = SenderInput(name=args.name, data=args.data, active=args.active, lines=sender_lines(args.data))
    except ValueError:
        fail("sender_bounds", "Revise o tamanho dos campos: cada linha do remetente pode ter até 150 caracteres.")
    key = "g_" + base64.urlsafe_b64encode(args.request_key.bytes).decode("ascii").rstrip("=")
    core = validated.data.model_dump()
    existing = db.query(PrintSender).filter_by(id=key).with_for_update().first()
    if existing:
        prior = {name: value for name, value in (existing.data or {}).items() if name != "_generator"}
        provenance = (existing.data or {}).get("_generator", {})
        if (prior != core or existing.name != validated.name or existing.active != validated.active
                or provenance.get("reviewed_by") != str(user.id) or provenance.get("source") != args.source):
            fail("request_conflict", "Esta confirmação já salvou outros dados. Abra uma nova revisão antes de salvar novamente.", 409)
        return {"id": existing.id, "reused": True}
    core["_generator"] = {"source": args.source, "synthetic": True, "reviewed_by": str(user.id), "reviewed_at": utcnow().isoformat()}
    row = PrintSender(id=key, name=validated.name, lines=validated.lines, data=core, active=validated.active)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        fail("request_conflict", "A confirmação foi recebida em paralelo. Atualize a lista de remetentes antes de tentar novamente.", 409)
    return {"id": row.id, "reused": False}
