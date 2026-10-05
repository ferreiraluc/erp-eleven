"""Safe provider diagnostics. Do not persist arbitrary error bodies or documents."""
import re
from fastapi import HTTPException

UNAVAILABLE = 'Emissão de etiquetas temporariamente fora do ar. A solicitação será consultada automaticamente; avisaremos quando puder continuar.'
UNCERTAIN = 'Criação ainda não confirmada. Consultaremos a SuperFrete automaticamente, sem criar ou cobrar outra etiqueta.'


class ProviderError(HTTPException):
    def __init__(self, category, detail, *, rejected=False, http_status=None):
        super().__init__(400 if category == 'validation' else 503 if category == 'unavailable' else 502, detail)
        self.category = category
        # Only a proven rejection / failure before connection permits another POST.
        self.rejected = rejected
        self.provider_status = http_status


def response_error(status, data):
    if status in (400, 422):
        fields = data.get('errors', {}) if isinstance(data, dict) else {}
        labels = {'origin_postcode':'CEP de origem', 'destination_postcode':'CEP de destino',
                  'weight':'peso', 'height':'altura', 'width':'largura', 'length':'comprimento',
                  'document':'CPF/CNPJ', 'postal_code':'CEP', 'district':'bairro', 'address':'rua',
                  'invoice':'nota fiscal', 'products':'conteúdo', 'name':'nome'}
        invalid = sorted({label for field in fields for key, label in labels.items() if key in str(field)}) if isinstance(fields, dict) else []
        message = 'SuperFrete: confira ' + ', '.join(invalid) + '.' if invalid else 'A SuperFrete recusou os dados do envio. Confira endereço, CPF/CNPJ, conteúdo e dimensões antes de cotar novamente.'
        return ProviderError('validation', message, rejected=True, http_status=status)
    if status in (401, 403):
        return ProviderError('configuration', 'A SuperFrete recusou o acesso à conta. Confira o token e as permissões da integração.', rejected=True, http_status=status)
    if status == 429 or status >= 500:
        return ProviderError('unavailable', UNAVAILABLE, rejected=status == 429, http_status=status)
    return ProviderError('unknown', 'Não foi possível confirmar a resposta da SuperFrete. A operação precisa de consulta.', http_status=status)


def valid_document(value):
    value = re.sub(r'\D', '', str(value or ''))
    if len(set(value)) <= 1: return False
    if len(value) == 11:
        for length in (9, 10):
            digit = (sum(int(v) * w for v, w in zip(value[:length], range(length+1, 1, -1))) * 10 % 11) % 10
            if digit != int(value[length]): return False
        return True
    if len(value) == 14:
        for length, weights in ((12, (5,4,3,2,9,8,7,6,5,4,3,2)), (13, (6,5,4,3,2,9,8,7,6,5,4,3,2))):
            remainder = sum(int(v)*w for v,w in zip(value[:length], weights)) % 11
            if (0 if remainder < 2 else 11-remainder) != int(value[length]): return False
        return True
    return False
