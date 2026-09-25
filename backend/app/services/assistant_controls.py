"""Server-owned choices: a callback never grants rights or lets the model execute writes."""
import re
import uuid
import unicodedata
from datetime import timedelta
from ..models.assistant import AssistantAction, AssistantNote, AssistantMessage, utcnow


def normalized(value):
    return ' '.join(re.sub(r'[^\w\s]', ' ', ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))).split())


class InteractiveReply(str):
    def __new__(cls, text, rows, document_url=None):
        result = super().__new__(cls, text)
        result.reply_markup = {'inline_keyboard': rows}
        result.document_url = document_url
        return result


def button(text, data):
    return {'text': text[:64], 'callback_data': data}


def subject(action):
    if isinstance(action, AssistantNote):
        return f'{action.kind}: {action.content[:60]}'
    p = action.payload
    if action.kind=='arquivo_imprimir':return f"PDF · {p['pages']} página(s)"
    return p.get('filename') or p.get('item_name') or p.get('recipient') or p.get('endereco', {}).get('nome') or p.get('vendedor_nome') or p.get('apelido') or 'Endereço sem nome'


def action_label(action):
    kind = getattr(action, 'kind', '')
    if kind == 'frete_emitir':
        return 'Pagar R$ ' + action.payload['price'].replace('.', ',')
    return {'arquivo_imprimir':'Imprimir PDF','item_cadastrar':'Cadastrar item','estoque_entrada':'Registrar entrada','impressao': 'Imprimir', 'frete_imprimir': 'Imprimir', 'folga': 'Cadastrar folga', 'apelido': 'Salvar apelido'}.get(kind, 'Confirmar registro')


def preview_reply(action, text, url=None):
    # UUIDs remain internal; old text confirmations still work for earlier messages.
    text = re.sub(r'\nIdentificador da prévia: [0-9a-f-]+', '', str(text))
    return InteractiveReply(text, [[button(action_label(action), 'a:' + action.id.hex),
                                    button('Cancelar', 'c:' + action.id.hex)]], url)


def pending(db, message):
    values = []
    for model in (AssistantAction, AssistantNote):
        values += db.query(model).join(AssistantMessage, AssistantMessage.id == model.source_message_id).filter(
            model.user_id == message.user_id, model.status == 'draft',
            model.created_at >= utcnow() - timedelta(hours=24),
            AssistantMessage.channel == message.channel,
            AssistantMessage.conversation_id == message.conversation_id,
        ).order_by(model.created_at.desc(), model.id).with_for_update(of=model).all()
    return sorted(values, key=lambda a: (a.created_at, str(a.id)), reverse=True)


def choose_reply(values, cancel=False, offset=0):
    page = values[offset:offset+8]
    lines = ['Escolha a prévia pelo botão ou diga “confirmar impressão NOME”:']
    rows = []
    for action in page:
        label = ('Cancelar' if cancel else action_label(action)) + ' · ' + subject(action)
        from ..config import settings
        stamp = action.created_at.replace(tzinfo=utcnow().tzinfo) if action.created_at.tzinfo is None else action.created_at
        stamp = stamp.astimezone(settings.tz).strftime('%d/%m %H:%M')
        p = action.payload if isinstance(action, AssistantAction) else {}
        detail = p.get('data') or p.get('endereco', {}).get('cidade') or stamp
        # Selecting a list item shows its exact preview before execution.
        lines.append(f'{subject(action)} · {action_label(action)} · {detail} · {stamp}')
        rows.append([button(label[:44] + ' · ' + str(detail)[:17], 'v:' + action.id.hex)])
    if offset+8 < len(values):
        rows.append([button('Mais prévias', f'p:{offset+8}')])
    return InteractiveReply('\n'.join(lines), rows)


def handle_selection(db, message, identity, content):
    from .assistant_schedule import confirm_action, action_preview
    from .assistant_tools import confirm_note
    from .assistant_agent import draft_response
    callback = re.fullmatch(r'/acao ([acv]):([0-9a-f]{32})', content)
    pages = re.fullmatch(r'/previas (\d{1,6})', content)
    if pages:
        values = pending(db, message)
        return choose_reply(values, offset=int(pages[1])) if values else 'Não há prévias pendentes nesta conversa.'
    if callback:
        key = uuid.UUID(callback[2])
        action = db.query(AssistantAction).filter_by(id=key).with_for_update().first()
        if not action:
            action = db.query(AssistantNote).filter_by(id=key).with_for_update().first()
        if not action:
            return 'Prévia não encontrada.'
        source = db.get(AssistantMessage, action.source_message_id)
        if action.user_id != message.user_id or source.channel != message.channel or source.conversation_id != message.conversation_id:
            return 'Somente quem pediu a prévia pode selecioná-la, na mesma conversa.'
        if callback[1] == 'v':
            if action not in pending(db, message):
                return 'Esta prévia já foi resolvida ou expirou. Nenhuma ação repetida.'
            return action_preview(action) if isinstance(action, AssistantAction) else draft_response(action)
        return (confirm_action(db, message, identity, action, cancel=callback[1]=='c') if isinstance(action, AssistantAction)
                else confirm_note(db, message, identity, str(action.id), cancel=callback[1]=='c'))
    match = re.fullmatch(r'(confirmo|confirma|confirmar|confirme|pode cadastrar|pode salvar|pode imprimir|imprimir|pode emitir|pode pagar|cancelo|cancelar|cancele|cancela)(?:\s+(.+?))?[.! ]*', content, re.I)
    if not match or not message.should_reply:
        return None
    target = (match[2] or '').strip(' "“”\'')
    # "Imprimir endereço ..." is a new request, not a confirmation by name.
    if match[1].lower() == 'imprimir' and target:
        return None
    cancel = match[1].lower().startswith('cancel')
    values = pending(db, message)
    if target:
        try:
            key = uuid.UUID(target)
            values = [a for a in values if a.id == key]
        except ValueError:
            printing = bool(re.search(r'impress[aã]o', target, re.I))
            target = re.sub(r'^(?:a\s+)?impress[aã]o\s*', '', target, flags=re.I).strip(' "“”\'')
            name = normalized(target)
            if printing:
                values = [a for a in values if isinstance(a, AssistantAction) and a.kind in ('impressao','frete_imprimir','arquivo_imprimir')]
            exact = [a for a in values if normalized(subject(a)) == name]
            values = exact or [a for a in values if name and set(name.split()).issubset(normalized(subject(a)).split())]
    if len(values) == 1:
        a = values[0]
        return (confirm_action(db, message, identity, a, cancel=cancel) if isinstance(a, AssistantAction)
                else confirm_note(db, message, identity, str(a.id), cancel=cancel))
    if values:
        return choose_reply(values, cancel)
    return 'Não encontrei uma prévia pendente com esse nome nesta conversa.' if target else 'Não há prévia aguardando sua confirmação nesta conversa.'
