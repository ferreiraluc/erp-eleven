import json
import re
from typing import Optional
from ..config import settings


def parse_label_image(image_base64: str, brand: Optional[str] = None, templates=None) -> dict:
    """Parse a product label image using Claude Vision API with optional few-shot examples."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("Pacote 'anthropic' não instalado. Execute: pip install anthropic")

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY não configurado no ambiente")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    system_prompt = (
        "Você é especialista em ler etiquetas de roupas e calçados de marcas variadas. "
        "Sua tarefa: extrair informações do produto a partir de fotos de etiquetas. "
        "Retorne APENAS JSON válido, sem texto antes ou depois."
    )

    parse_instruction = (
        "Analise esta etiqueta e retorne APENAS este JSON (null para campos não encontrados):\n\n"
        '{"nome": "nome/modelo do produto (não a marca)", '
        '"marca": "nome da marca", '
        '"tamanho": "PP/P/M/G/GG/XG ou número", '
        '"cor": "cor em português", '
        '"codigo_barras": "apenas dígitos EAN 8-13 chars", '
        '"preco": número ou null, '
        '"moeda": "PYG/BRL/USD/EUR ou null", '
        '"texto_bruto": "todo texto visível na etiqueta"}\n\n'
        "Contexto: etiquetas de moda do Paraguai/Brasil. "
        "Preços em Guaranis (PYG) são números inteiros grandes (ex: 150000). "
        "Tamanhos de roupas: PP P M G GG XG. Calçados: 34-45. Calças: 30-52."
    )

    # Add brand-specific notes from templates
    brand_notes = []
    if templates:
        for t in templates:
            if t.notes and t.notes.strip():
                brand_notes.append(t.notes.strip())
    if brand_notes:
        parse_instruction += "\n\nDicas específicas desta marca:\n" + "\n".join(f"- {n}" for n in set(brand_notes))

    messages = []

    # Few-shot examples from saved templates
    if templates:
        for tmpl in templates[:3]:
            if not tmpl.sample_image:
                continue
            img_data = tmpl.sample_image
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            correct = {
                "nome": tmpl.parsed_name,
                "marca": brand or tmpl.brand,
                "tamanho": tmpl.parsed_size,
                "cor": tmpl.parsed_color,
                "codigo_barras": tmpl.parsed_barcode,
                "preco": float(tmpl.parsed_price) if tmpl.parsed_price else None,
                "moeda": tmpl.parsed_currency,
                "texto_bruto": "",
            }
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_data}},
                    {"type": "text", "text": parse_instruction},
                ],
            })
            messages.append({
                "role": "assistant",
                "content": json.dumps(correct, ensure_ascii=False),
            })

    # Actual image to parse
    img_data = image_base64
    if "," in img_data:
        img_data = img_data.split(",", 1)[1]

    messages.append({
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_data}},
            {"type": "text", "text": parse_instruction},
        ],
    })

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )

    content = response.content[0].text.strip()
    # Extract JSON block (handles markdown code fences)
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        content = json_match.group()

    return json.loads(content)
