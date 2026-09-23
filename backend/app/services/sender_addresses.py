"""One sender address for printing and freight, including legacy print blocks."""
import re
import unicodedata
from ..schemas.address_book import AddressData


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c)).strip()


def sender_address(sender):
    data=AddressData(pais='BR',nome=sender.name).model_dump()
    remaining=[]
    for raw in sender.lines or []:
        line=raw.strip()
        if not line or normalized(line) in (normalized(sender.name),'remetente'):continue
        if re.search(r'\b(?:CPF|CNPJ)\b',line,re.I):
            data['cpf']=re.sub(r'\D','',line);continue
        cep=re.fullmatch(r'(?:CEP\s*:?\s*)?(\d{5})[- ]?(\d{3})',line,re.I)
        if cep:data['cep']=''.join(cep.groups());continue
        city=re.fullmatch(r'(.+?)\s*[-–/]\s*([A-Z]{2})',line,re.I)
        if city:data['cidade']=city[1].strip();data['estado']=city[2].upper();continue
        street=re.fullmatch(r'(.+?),\s*(\d+[A-Za-z]?|s/?n)',line,re.I)
        if not street and re.match(r'^(?:Rua|R\.|Avenida|Av\.?|Alameda|Travessa|Estrada|Rodovia)\s',line,re.I):
            street=re.fullmatch(r'(.+?)\s+(\d+[A-Za-z]?|s/?n)',line,re.I)
        if street:data['endereco']=street[1].strip();data['numero']=street[2];continue
        district=re.fullmatch(r'(?:bairro)\s*:?\s*(.+)',line,re.I)
        if district:data['bairro']=district[1].strip();continue
        remaining.append((line,bool(data['endereco'] and not data['cidade'])))
    # One remaining line in a complete legacy block is its neighborhood.
    # Ambiguous multi-line blocks are left for the user/model to clarify.
    if len(remaining)==1 and remaining[0][1] and data['cidade'] and data['cep']:
        data['bairro']=remaining[0][0]
    for key,value in (sender.data or {}).items():
        if value and key in data:data[key]=value
    return data


def sender_lines(sender):
    if not sender.data:return list(sender.lines)
    d=sender_address(sender)
    return [v for v in [d['nome'],', '.join(x for x in [d['endereco'],d['numero']] if x),
        d['bairro'],d['complemento'],' - '.join(x for x in [d['cidade'],d['estado']] if x),
        'CEP '+d['cep'] if d['cep'] else '', 'CPF/CNPJ: '+d['cpf'] if d['cpf'] else ''] if v]
