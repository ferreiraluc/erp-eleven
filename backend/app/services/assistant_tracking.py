"""Customer tracking defaults to ongoing deliveries; history is an explicit request."""
import re
from datetime import timedelta, timezone
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
    if re.search(r'\b(imprim\w*|impress\w*|reimprim\w*|reimpress\w*|pdf|emit\w*|cadastr\w*|cotar|cotacao|remetente|folga\w*)\b',value):
        return False
    if re.search(r'\b(rastrei\w*|rastreamento|codigo\w*)\b',value):return True
    if previous and re.match(r'^(e |sim\b|esse\b|este\b|dele\b|dela\b|so |apenas |mais\b)',value):
        return tracking_intent(previous)
    return False


def customer_tracking_term(content, previous=None):
    """Resolve simple named lookups without asking the model to select a tool.

    Complex requests (periods, totals, multiple people, errors, printing) keep the
    conversational tool flow. A rejected parse never means a missing shipment.
    """
    value = normalized(content)
    if not tracking_intent(content, previous):
        return None
    if re.search(r'\b(?:entreg\w*|historico|ultim\w*|recent\w*|hoje|ontem|anteontem|semana|mes|antig\w*|dia|dias)\b', value):
        return None
    if re.search(r'\d|\b(?:nao|erro|falha|trav\w*|problema|como|quantos|quantas|todos|todas|lista|liste|resumo)\b', value):
        return None
    match = re.search(r'\b(?:rastreios?|rastreamentos?|codigos?)\b', value)
    if match:
        prefix = value[:match.start()].split()
        allowed = {'eleven', 'bot', 'me', 'mim', 'manda', 'mande', 'envia', 'envie', 'passa', 'passe',
                   'mostra', 'mostre', 'quero', 'preciso', 'do', 'da', 'de', 'o', 'os', 'a', 'as',
                   'um', 'qual', 'quais', 'tem', 'teria', 'pode', 'poderia', 'consegue', 'conseguiria',
                   'por', 'favor', 'bom', 'dia', 'boa', 'tarde', 'noite', 'consultar', 'consulte',
                   'consulta', 'buscar', 'busque', 'busca', 'ver', 'veja'}
        if any(word not in allowed for word in prefix):
            return None
        term = value[match.end():].strip()
        term = re.sub(r'^de rastreio\s+', '', term)
    elif previous and customer_tracking_term(previous) and re.match(r'^e\s+(?:do|da|de)\s+', value):
        term = value[2:]
    else:
        return None
    term = re.sub(r'^(?:(?:o|a|do|da|de|dos|das|para|cliente|clientes|destinatario|destinataria)\s+)+', '', term)
    term = re.sub(r'\s+(?:por favor|por gentileza|pfv|pf|obrigado|obrigada)$', '', term).strip()
    words = term.split()
    reserved = {'e', 'ou', 'cliente', 'clientes', 'destinatario', 'destinataria', 'dele', 'dela', 'desse',
                'dessa', 'esse', 'essa', 'este', 'esta', 'mesmo', 'mesma', 'meu', 'minha', 'quem',
                'que', 'qual', 'quais', 'ainda', 'agora', 'aqui', 'ai', 'mais', 'so', 'apenas',
                'encontrei', 'encontrou', 'encontrado', 'encontrada', 'sumiu', 'status', 'situacao',
                'pedido', 'pedidos', 'produto', 'produtos', 'item', 'itens', 'sku', 'interno', 'internos',
                'barra', 'barras', 'estoque', 'venda', 'vendas', 'ticket', 'tickets', 'fornecedor',
                'pendente', 'pendentes', 'aberto', 'abertos', 'transito', 'atualize', 'atualizar'}
    if not 1 <= len(words) <= 8 or not 2 <= len(term) <= 100 or any(not word.isalpha() or word in reserved for word in words):
        return None
    return term


def current_customer_request(content, previous=None):
    value=normalized(content)
    if re.search(r'\b(entregu\w*|historico|ultim\w*|recent\w*|ontem|anteontem|semana|mes|antig\w*)\b',value) or re.search(r'\d{2}/\d{2}',content):return False
    if re.search(r'\b[A-Z]{2}\d{9}[A-Z]{2}\b',content,re.I):return False
    if customer_tracking_term(content, previous):return True
    return bool(re.search(r'\b(?:rastreio\w*|rastreamento|codigo)\s+(?:(?:de|do|da|para|cliente)\s+)+\w+',value))


AMBIGUOUS_TRACKING_PREFIX = 'Encontrei envios em andamento para mais de um destinatário. Qual deles?\n'


def tracking_choice_request(content, message, previous, now):
    """Only a recent, explicit same-author ambiguity can give a number meaning."""
    if not previous or not re.fullmatch(r'(?:[1-9]|1\d|20)', content.strip()):
        return None
    if previous.status != 'done' or not (previous.response or '').startswith(AMBIGUOUS_TRACKING_PREFIX):
        return None
    if any(getattr(previous, field) != getattr(message, field) for field in ('user_id', 'sender_id', 'channel', 'conversation_id')):
        return None
    created = previous.created_at
    if created.tzinfo is None:created = created.replace(tzinfo=timezone.utc)
    if not timedelta(0) <= now - created <= timedelta(minutes=30):
        return None
    term = customer_tracking_term(previous.text)
    return (term, int(content.strip()) - 1) if term else None


def selected_tracking_reply(result, index, previous_response):
    """Re-render live choices before interpreting an old number; never reuse rows."""
    current = customer_tracking_reply(result)
    if not result.get('clientes_distintos') or str(current) != previous_response:
        return 'A lista de envios mudou desde a consulta anterior. Informe novamente o nome do destinatário para consultar o rastreio atualizado.'
    rows = result.get('resultados', [])
    if index >= len(rows):
        return 'Esse número não corresponde à lista. Informe novamente o nome completo do destinatário para consultar o rastreio.'
    return tracking_reply(rows[index])


def customer_tracking(db,args):
    base=dict(termo=args.termo,ordem='priorizar_abertos',pagina=args.pagina,limite=20)
    result=query_shipments(db,ShipmentArgs(**base,situacao='EM_TRANSITO'),allow_fuzzy=False)
    if not result['total']:
        result=query_shipments(db,ShipmentArgs(**base,situacao='em_aberto'),allow_fuzzy=False)
    if not result['total']:
        # Exact pending recipients take priority over a similar name in transit.
        result=query_shipments(db,ShipmentArgs(**base,situacao='em_aberto'))
    result['somente_atuais']=True
    result['instrucao']='Envios entregues não fazem parte desta consulta. Envie código sozinho e detalhes em seguida, sem pedir confirmação quando o cliente está identificado. Em busca aproximada, informe a grafia cadastrada. Mais de um destinatário exige escolha.'
    return result


def customer_tracking_reply(result):
    rows=result.get('resultados',[])
    if not rows:
        return 'Não encontrei envio em andamento para esse cliente no ERP. Os entregues ficam no histórico; posso consultá-los se você precisar.'
    if result.get('clientes_distintos'):
        options=[]
        for row in rows:
            name=row.get('destinatario') or row.get('cliente') or 'Destinatário não informado'
            if row.get('destinatario') and row.get('cliente') != name:
                name+=f" (cliente: {row.get('cliente') or 'não informado'})"
            # Do not collapse homonyms/different recipient snapshots into one
            # unselectable option. The order/date help distinguish real records.
            if row.get('pedido'):name+=f" · Pedido {row['pedido']}"
            if row.get('data_envio'):name+=f" · Envio {row['data_envio']}"
            options.append(name)
        reply=AMBIGUOUS_TRACKING_PREFIX+'\n'.join(f'{i+1}. {v}' for i,v in enumerate(options))
        if result.get('tem_mais'):reply+='\nHá outros resultados. Informe o sobrenome ou peça os próximos.'
        return reply
    parts=[]
    for row in rows:parts.extend(tracking_reply(row).parts)
    if result.get('tem_mais'):parts.append(f"Há {result['total']} envios em andamento. Mostrei 20; peça os próximos para continuar.")
    return Reply(parts)
