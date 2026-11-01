"""Explicit country selection for customer contacts, without a bulk identity rewrite."""
import re


def normalize_customer_phone(phone: str | None, country: str) -> str | None:
    value = (phone or '').strip()
    if not value:
        return None
    if country not in ('BR', 'PY') or not re.fullmatch(r'\+?[\d\s().-]+', value, re.ASCII):
        raise ValueError('Confira o telefone e selecione Brasil (+55) ou Paraguai (+595).')
    digits = re.sub(r'\D', '', value)
    international = value.startswith('+') or digits.startswith('00')
    if digits.startswith('00') and not value.startswith('+'):
        digits = digits[2:]
    if international and re.fullmatch(r'550[1-9]\d[2-9]\d{7,8}', digits):
        digits = '55' + digits[3:]
    if re.fullmatch(r'5950[1-9]\d{8}', digits):
        digits = '595' + digits[4:]
    brazil = re.fullmatch(r'55[1-9]\d[2-9]\d{7,8}', digits)
    paraguay = re.fullmatch(r'595[1-9]\d{8}', digits)
    if not international and not brazil and not paraguay:
        if digits.startswith('0'):
            digits = digits[1:]
        if country == 'BR' and re.fullmatch(r'[1-9]\d[2-9]\d{7,8}', digits):
            digits = '55' + digits
        elif country == 'PY' and re.fullmatch(r'[1-9]\d{8}', digits):
            digits = '595' + digits
        else:
            raise ValueError('Confira o telefone completo, incluindo o DDD no Brasil.')
    if (not re.fullmatch(r'[1-9]\d{7,14}', digits) or re.fullmatch(r'(\d)\1+', digits)
            or (digits.startswith('55') and not re.fullmatch(r'55[1-9]\d[2-9]\d{7,8}', digits))
            or (digits.startswith('595') and not re.fullmatch(r'595[1-9]\d{8}', digits))):
        raise ValueError('Confira o telefone completo, incluindo o DDD no Brasil.')
    return '+' + digits
