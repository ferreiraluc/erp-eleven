"""Persistent operational map, explicit aliases, and fresh employee resolution."""
import uuid
from pydantic import BaseModel, ConfigDict, Field
from ..models.assistant import AssistantKnowledge, AssistantAction, utcnow
from ..models.vendedor import Vendedor
from .assistant_controls import normalized, preview_reply


class KnowledgeArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    termo: str = Field(default='', max_length=100)


class AliasArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    vendedor: str = Field(min_length=2, max_length=100)
    apelido: str = Field(min_length=2, max_length=100)


def employee_candidates(db, name):
    rows = db.query(Vendedor).filter_by(ativo=True).order_by(Vendedor.nome).all()
    key = normalized(name)
    exact = [v for v in rows if normalized(v.nome) == key]
    if exact:
        return exact
    alias = db.get(AssistantKnowledge, 'alias:' + key)
    if alias:
        found = [v for v in rows if str(v.id) == alias.data.get('vendedor_id')]
        if found:return found
    tokens = set(key.split())
    # Full name supplied for a single-token ERP registration (Junior Favretto -> Junior).
    # Multiple Juniors remain ambiguous and are never arbitrarily selected.
    return [v for v in rows if tokens and (tokens.issubset(normalized(v.nome).split()) or
            len(normalized(v.nome).split()) == 1 and normalized(v.nome) in tokens)]


def query_team(db, args):
    rows = employee_candidates(db, args.termo) if args.termo else db.query(Vendedor).filter_by(ativo=True).order_by(Vendedor.nome).all()
    return {'vendedores': [{'id':str(v.id), 'nome':v.nome} for v in rows],
            'orientacao':'Um único resultado identifica o vendedor. Use o nome cadastrado em preparar_folga; não exija nome completo. Se houver vários, peça escolha.'}


def system_catalog(db, args):
    from .assistant_tools import TOOLS
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(711004)"))
    locations = {'rastreios':'/rastreamento', 'pedidos':'/pedidos', 'estoque':'/inventory', 'clientes':'/clientes',
                 'vendas':'/vendas', 'folga':'/vendors', 'endereco':'/enderecos', 'etiqueta':'/enderecos',
                 'superfrete':'/enderecos', 'impressao':'/enderecos', 'equipe':'/vendors'}
    existing = {r.key:r for r in db.query(AssistantKnowledge).filter_by(kind='capability')}
    items = []
    active_keys = set()
    for tool in TOOLS:
        f = tool['function']
        key = 'tool:' + f['name']
        active_keys.add(key)
        path = next((v for k,v in locations.items() if k in f['name']), '/assistente')
        data = {'ferramenta':f['name'], 'descricao':f['description'], 'pagina':path}
        row = existing.get(key)
        if not row:
            db.add(AssistantKnowledge(key=key, kind='capability', data=data))
        elif row.data != data:
            row.data, row.updated_at = data, utcnow()
        if not args.termo or any(t in normalized(str(data)) for t in normalized(args.termo).split()):
            items.append(data)
    for key, row in existing.items():
        if key not in active_keys:db.delete(row)
    db.flush()
    return {'capacidades':items, 'origem':'Catálogo persistido e sincronizado com as ferramentas desta versão.',
            'orientacao':'Combine as ferramentas para concluir a tarefa. Consulte equipe, endereços e memória antes de pedir dados que podem estar no ERP. Dados atuais, saldos, envios e agenda devem ser consultados novamente; não são congelados na memória.'}


def alias_preview(action):
    p = action.payload
    return preview_reply(action, f"Guardar na memória da equipe: {p['apelido']} identifica {p['vendedor_nome']}. Confirme para salvar ou cancele.")


def prepare_alias(db, message, identity, args):
    from .assistant_schedule import may_schedule
    if not message.should_reply or not may_schedule(db, message, identity):
        return {'erro':'Somente gestores habilitados podem definir apelidos.'}
    candidates = employee_candidates(db, args.vendedor)
    if len(candidates) != 1:
        return {'erro':'Escolha um vendedor entre os candidatos.', 'candidatos':[v.nome for v in candidates]}
    vendor = candidates[0]
    conflict = employee_candidates(db, args.apelido)
    if any(v.id != vendor.id for v in conflict):
        return {'erro':'Esse nome já identifica outro vendedor. Escolha outro apelido.'}
    action = db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if not action:
        action = AssistantAction(source_message_id=message.id, user_id=message.user_id, kind='apelido',
            payload={'vendedor_id':str(vendor.id), 'vendedor_nome':vendor.nome, 'apelido':args.apelido})
        db.add(action);db.flush()
    return {'confirmacao':alias_preview(action)}


def confirm_alias(db, message, action):
    p = action.payload
    vendor = db.get(Vendedor, uuid.UUID(p['vendedor_id']))
    if not vendor or not vendor.ativo:return 'Vendedor não está ativo. Nenhum apelido salvo.'
    # Lock an employee row to serialize competing aliases in addition to the unique key.
    db.query(Vendedor).order_by(Vendedor.id).with_for_update().all()
    conflict = employee_candidates(db, p['apelido'])
    if any(v.id != vendor.id for v in conflict):return 'O apelido passou a identificar outro vendedor. Nenhuma mudança realizada.'
    key = 'alias:' + normalized(p['apelido'])
    row = db.get(AssistantKnowledge, key)
    if not row:
        row = AssistantKnowledge(key=key, kind='employee_alias');db.add(row)
    row.data={'vendedor_id':str(vendor.id), 'apelido':p['apelido']}
    row.updated_by=message.user_id;row.updated_at=utcnow()
    action.status='executed';action.executed_at=utcnow()
    return f"Memória salva: {p['apelido']} identifica {vendor.nome}. Usarei esse apelido nas consultas e folgas."
