"""Bounded vision adapter. Select one provider; never retry or switch after errors."""
import json
import requests

from ..config import settings


class VisionUnavailable(RuntimeError):
    pass


class VisionError(RuntimeError):
    pass


def configured_provider():
    provider = settings.VISION_PROVIDER
    if provider == 'auto':
        provider = 'deepseek' if settings.DEEPSEEK_API_KEY else 'anthropic'
    if provider not in ('deepseek', 'anthropic'):
        raise VisionUnavailable('Configuração de visão inválida no servidor.')
    key = settings.DEEPSEEK_API_KEY if provider == 'deepseek' else settings.ANTHROPIC_API_KEY
    if not key:
        raise VisionUnavailable('Leitura de imagens não configurada: defina DEEPSEEK_API_KEY ou ANTHROPIC_API_KEY no servidor.')
    return provider


def complete_vision(*, system, messages, max_tokens=2500, timeout=35):
    """Accept internal Anthropic-shaped blocks after image validation/sanitization."""
    provider = configured_provider()
    try:
        if provider == 'anthropic':
            import anthropic
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=timeout, max_retries=0)
            result = client.messages.create(model='claude-haiku-4-5', max_tokens=max_tokens,
                                            temperature=0, system=system, messages=messages)
            return '\n'.join(block.text for block in result.content if getattr(block, 'type', None) == 'text')
        converted = [{'role': 'system', 'content': system}]
        for message in messages:
            if isinstance(message['content'], str):
                converted.append(message)
                continue
            content = []
            for block in message['content']:
                if block['type'] == 'text':
                    content.append(block)
                else:
                    source = block['source']
                    if (message['role'] != 'user' or source['type'] != 'base64'
                            or source['media_type'] not in ('image/jpeg', 'image/png', 'image/webp')):
                        raise ValueError('Invalid internal image block')
                    content.append({'type': 'image_url', 'image_url': {
                        'url': f"data:{source['media_type']};base64,{source['data']}", 'detail': 'original'}})
            converted.append({'role': message['role'], 'content': content})
        with requests.post('https://api.deepseek.com/chat/completions',
                headers={'Authorization': f'Bearer {settings.DEEPSEEK_API_KEY}'},
                json={'model': settings.DEEPSEEK_VISION_MODEL, 'messages': converted,
                      'max_tokens': max_tokens, 'temperature': 0, 'thinking': {'type': 'disabled'}},
                timeout=(5, timeout), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError('Provider unavailable')
            body = bytearray()
            for chunk in response.iter_content(8192):
                body.extend(chunk)
                if len(body) > 128 * 1024:
                    raise ValueError('Response too large')
            choice = json.loads(body)['choices'][0]
            if choice.get('finish_reason') != 'stop' or not isinstance(choice['message'].get('content'), str):
                raise ValueError('Incomplete extraction')
            return choice['message']['content']
    except Exception:
        # Provider exceptions can contain credentials, request images or account details.
        raise VisionError('O serviço de leitura de imagens não concluiu a consulta. Tente novamente depois.') from None
