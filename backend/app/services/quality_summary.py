"""One bounded aggregate-only LLM explanation; no tools or application writes."""
from dataclasses import dataclass
import json
import re
import requests
from ..config import settings

MAX_OUTPUT_TOKENS = 600
MAX_INPUT_BYTES = 4096
CHECK_KEYS = ('inventory_missing_metadata', 'inventory_balance', 'inventory_limits',
              'sale_avulso_without_reason', 'print_uncertain', 'print_failed', 'print_stale',
              'printer_offline', 'bi_sync_problem', 'worker_problem', 'customer_duplicate_candidate',
              'address_duplicate_candidate', 'address_link_review')
SYSTEM = ('Você resume um diagnóstico interno do ERP Eleven. Recebe somente contagens anônimas de verificações limitadas. '
          'Não pode executar ações, alterar vendas/estoque/impressões, pedir credenciais ou inferir fraude. '
          'Avulso sem motivo é uma pendência de contexto, não prova de erro. Dados incompletos não são inventário inteiro. '
          'Responda JSON com uma única propriedade "summary": até 600 caracteres, em português simples, '
          'somente interpretação dos números e até duas prioridades de conferência. Sem nomes, links ou comandos.')


@dataclass(frozen=True)
class QualitySummary:
    status: str
    text: str | None = None
    provider: str | None = None
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def aggregate_payload(counters, coverage):
    # Reconstruct, do not redact arbitrary objects: names, IDs, free text, query
    # strings and malformed values have no path to either provider.
    safe = {key: min(10**9, max(0, value)) for key, value in counters.items()
            if key in CHECK_KEYS and type(value) is int}
    complete = {key: bool(value.get('complete')) for key, value in coverage.items()
                if key in {'inventory', 'sales', 'prints', 'printers', 'bi', 'workers', 'customers', 'addresses'}
                and isinstance(value, dict)}
    payload = json.dumps({'counts': safe, 'complete': complete}, sort_keys=True, ensure_ascii=False)
    if len(payload.encode()) > MAX_INPUT_BYTES:
        raise ValueError('quality_input_budget')
    return payload


def _text(value):
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or set(parsed) != {'summary'}:
        raise ValueError('quality_output_schema')
    summary = parsed['summary']
    if (not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 600
            or re.search(r'https?://|www\.|\b[\w.+-]+@[\w.-]+\.\w+|```|[\x00-\x08\x0b-\x1f]', summary)):
        raise ValueError('quality_output_schema')
    return summary.strip()


def _usage(value):
    return min(100000, max(0, value)) if type(value) is int else 0


def summarize(counters, coverage, *, deepseek_key=None, anthropic_key=None):
    """No automatic retry. An independent fallback receives the same tiny input."""
    payload = aggregate_payload(counters, coverage)
    deepseek_key = settings.DEEPSEEK_API_KEY if deepseek_key is None else deepseek_key
    anthropic_key = settings.ANTHROPIC_API_KEY if anthropic_key is None else anthropic_key
    calls = 0
    input_tokens, output_tokens = 0, 0
    # These are fixed official origins, not request-supplied provider URLs.
    with requests.Session() as session:
        session.trust_env = False
        if deepseek_key:
            calls += 1
            try:
                response = session.post('https://api.deepseek.com/chat/completions',
                    headers={'Authorization': f'Bearer {deepseek_key}'},
                    json={'model': settings.DEEPSEEK_MODEL, 'max_tokens': MAX_OUTPUT_TOKENS,
                          'temperature': 0.1, 'thinking': {'type': 'disabled'},
                          'response_format': {'type': 'json_object'},
                          'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': payload}]},
                    timeout=(3, 10), allow_redirects=False)
                if response.status_code != 200 or len(response.content) > 20000:
                    raise ValueError('quality_provider_error')
                body = response.json()
                usage = body.get('usage') or {}
                input_tokens += _usage(usage.get('prompt_tokens'))
                output_tokens += min(MAX_OUTPUT_TOKENS, _usage(usage.get('completion_tokens')))
                result = _text(body['choices'][0]['message']['content'])
                return QualitySummary('completed', result, 'deepseek', calls,
                    input_tokens, output_tokens)
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
                pass
        if anthropic_key:
            calls += 1
            try:
                response = session.post('https://api.anthropic.com/v1/messages',
                    headers={'x-api-key': anthropic_key, 'anthropic-version': '2023-06-01'},
                    json={'model': 'claude-haiku-5-5', 'max_tokens': MAX_OUTPUT_TOKENS,
                          'thinking': {'type': 'disabled'},
                          'system': SYSTEM, 'messages': [{'role': 'user', 'content': payload}]},
                    timeout=(3, 10), allow_redirects=False)
                if response.status_code != 200 or len(response.content) > 20000:
                    raise ValueError('quality_provider_error')
                body = response.json()
                usage = body.get('usage') or {}
                input_tokens += _usage(usage.get('input_tokens'))
                output_tokens += min(MAX_OUTPUT_TOKENS, _usage(usage.get('output_tokens')))
                result = _text(''.join(part.get('text', '') for part in body['content'] if part.get('type') == 'text'))
                return QualitySummary('fallback' if calls > 1 else 'completed', result, 'anthropic', calls,
                    input_tokens, output_tokens)
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
                pass
    return QualitySummary('unavailable' if calls else 'not_configured', calls=calls, input_tokens=input_tokens, output_tokens=output_tokens)
