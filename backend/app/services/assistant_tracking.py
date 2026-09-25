"""Customer tracking defaults to ongoing deliveries; history is an explicit request."""
import re
from pydantic import BaseModel, ConfigDict, Field
from .assistant_controls import normalized
from .assistant_queries import ShipmentArgs, query_shipments
from .assistant_replies import Reply, tracking_reply


class CustomerTrackingArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    termo: str = Field(min_length=2, max_length=100, description='Nome do cliente procurado, sem a pergunta inteira.')
    pagina: int = Field(default=1, ge=1, le=1000)


def tracking_intent(content, previous=None):
    """Do not turn PDF/label operations into tracking replies merely for mentioning a code."""
    value=normalized(content)
    if re.search(r'\b(imprim\w*|impress\w*|pdf|emit\w*|cadastr\w*|cotar|cotacao|remetente|folga\w*)\b',value):
        return False
    if re.search(r'\b(rastrei\w*|rastreamento|codigo\w*)\b',value):return True
    if previous and re.match(r'^(e |sim\b|esse\b|este\b|dele\b|dela\b|so |apenas |mais\b)',value):
        return tracking_intent(previous)
    return False


def current_customer_request(content):
    value=normalized(content)
    if re.search(r'\b(entregu\w*|historico|ultim\w*|recent\w*|ontem|anteontem|semana|mes|antig\w*)\b',value) or re.search(r'\d{2}/\d{2}',content):return False
    if re.search(r'\b[A-Z]{2}\d{9}[A-Z]{2}\b',content,re.I):return False
    return bool(re.search(r'\b(?:rastreio\w*|rastreamento|codigo)\s+(?:(?:de|do|da|para|cliente)\s+)+\w+',value))


def customer_tracking(db,args):
    base=dict(termo=args.termo,ordem='priorizar_abertos',pagina=args.pagina,limite=20)
    result=query_shipments(db,ShipmentArgs(**base,situacao='EM_TRANSITO'))
    if not result['total']:
        result=query_shipments(db,ShipmentArgs(**base,situacao='em_aberto'))
    result['somente_atuais']=True
    result['instrucao']='Envios entregues não fazem parte desta consulta. Envie código sozinho e detalhes em seguida, sem pedir confirmação quando o cliente está identificado.'
    return result


def customer_tracking_reply(result):
    rows=result.get('resultados',[])
    if not rows:
        return 'Não encontrei envio em andamento para esse cliente no ERP. Os entregues ficam no histórico; posso consultá-los se você precisar.'
    if result.get('clientes_distintos'):
        options=[]
        for row in rows:
            name=row.get('cliente') or 'Destinatário não informado'
            if name not in options:options.append(name)
        return 'Encontrei envios em andamento para mais de um destinatário. Qual deles?\n'+'\n'.join(f'{i+1}. {v}' for i,v in enumerate(options))
    parts=[]
    for row in rows:parts.extend(tracking_reply(row).parts)
    if result.get('tem_mais'):parts.append(f"Há {result['total']} envios em andamento. Mostrei 20; peça os próximos para continuar.")
    return Reply(parts)
