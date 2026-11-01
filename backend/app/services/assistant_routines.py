"""Explicit, versioned shipping defaults; live identities and quantities stay per request."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import text

from ..models.assistant import AssistantAction, AssistantKnowledge, AssistantMessage, utcnow
from ..models.usuario import Usuario
from .access_policy import is_owner
from .assistant_controls import preview_reply
from .assistant_schedule import may_schedule
from .superfrete import Package


ROUTINE_KEY = 'shipping:defaults'
ROUTINE_KIND = 'shipping_defaults'


class RoutineProduct(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    unitary_value: Decimal = Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)

    @field_validator('name')
    @classmethod
    def readable_name(cls, value):
        if any(ord(char) < 32 for char in value):
            raise ValueError('Descrição não pode conter caracteres de controle.')
        return value


class RoutineArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    active: bool = True
    package: Package | None = None
    product: RoutineProduct | None = None

    @model_validator(mode='after')
    def usable_default(self):
        if self.active and self.package is None and self.product is None:
            raise ValueError('Informe o pacote ou o modelo de conteúdo para ativar o padrão.')
        return self


class StoredRoutine(RoutineArgs):
    revision: int = Field(ge=1, strict=True)


class RoutineQuantity(BaseModel):
    quantity: int = Field(ge=1, le=10000, strict=True)


def get_routine(db):
    """Return only a validated current preset; malformed storage never supplies defaults."""
    row = db.query(AssistantKnowledge).filter_by(key=ROUTINE_KEY).populate_existing().first()
    if row is None:
        return None
    try:
        if row.kind != ROUTINE_KIND:
            raise ValueError('Incorrect operational memory type')
        data = StoredRoutine.model_validate(row.data).model_dump(mode='json')
    except (ValidationError, ValueError):
        raise HTTPException(409, 'O padrão de frete precisa de revisão no ERP; nenhum dado antigo foi aplicado.') from None
    return {**data, 'key': row.key, 'updated_by': str(row.updated_by) if row.updated_by else None,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None}


def _authorized(db, message, identity, *, write=False):
    user = db.get(Usuario, message.user_id)
    return bool(message.should_reply and identity and may_schedule(db, message, identity)
                and identity.channel == message.channel and identity.external_id == message.sender_id
                and (not write or (user and is_owner(user))))


def query_routine(db, message, identity):
    if not _authorized(db, message, identity):
        return {'erro': 'Padrões de frete exigem um gestor habilitado no assistente.'}
    try:
        routine = get_routine(db)
    except HTTPException as error:
        return {'erro': error.detail}
    return {'padrao': routine,
            'orientacao': 'Padrão confirmado para campos ausentes. Dados informados neste envio prevalecem. '
            'Quantidade, destinatário, remetente, serviço e informação fiscal vêm da solicitação atual; '
            'o padrão não autoriza pagamentos nem impressões.'}


def save_routine(db, args, *, user_id, expected_revision):
    """Save an owner-authorized preset inside the caller's transaction (never commit)."""
    user = db.get(Usuario, user_id)
    if not user or not user.ativo or not is_owner(user):
        raise HTTPException(403, 'Somente Lucas pode alterar o padrão compartilhado de frete.')
    args = RoutineArgs.model_validate(args)
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise HTTPException(422, 'Informe a revisão atual do padrão.')
    # Lock an existing owner row even for the first write: an absent knowledge
    # row cannot be locked, and concurrent first saves must compare revision zero.
    user = db.query(Usuario).filter_by(id=user_id).populate_existing().with_for_update().one()
    if not user.ativo or not is_owner(user):
        raise HTTPException(403, 'Somente Lucas pode alterar o padrão compartilhado de frete.')
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(711018)'))
    current = get_routine(db)
    revision = current['revision'] if current else 0
    if expected_revision != revision:
        raise HTTPException(409, 'O padrão mudou depois da prévia. Consulte o padrão atual e prepare a alteração novamente.')
    row = db.get(AssistantKnowledge, ROUTINE_KEY)
    if row is None:
        row = AssistantKnowledge(key=ROUTINE_KEY, kind=ROUTINE_KIND)
        db.add(row)
    row.data = {**args.model_dump(mode='json'), 'revision': revision + 1}
    row.updated_by, row.updated_at = user_id, utcnow()
    from .user_audit import record
    record(db, 'shipping_defaults_updated', 'assistente', user_id=user_id, actor_name=user.nome,
           source=db.info.get('audit_actor', {}).get('source', 'assistant'),
           entity='assistant_knowledge', entity_id=ROUTINE_KEY,
           changes={field: {'before': current.get(field) if current else None, 'after': row.data[field]}
                    for field in ('revision', 'active', 'package', 'product')})
    db.flush()
    return get_routine(db)


def _number(value):
    return format(Decimal(str(value)).normalize(), 'f').replace('.', ',')


def routine_preview(action):
    args = RoutineArgs.model_validate(action.payload['routine'])
    lines = ['Atualizar o padrão de frete da equipe:']
    if not args.active:
        lines.append('Desativar o preenchimento automático do pacote e do modelo de conteúdo.')
    else:
        if args.package:
            package = args.package
            lines.append(f'Pacote: {_number(package.weight)} kg; '
                         f'{_number(package.height)} × {_number(package.width)} × {_number(package.length)} cm '
                         '(altura × largura × comprimento).')
        else:
            lines.append('Pacote: informar em cada envio.')
        if args.product:
            price = f'{args.product.unitary_value:.2f}'.replace('.', ',')
            lines.append(f'Modelo de conteúdo: {args.product.name}; R$ {price} por unidade.')
        else:
            lines.append('Conteúdo: informar em cada envio.')
    lines += ['A quantidade e os dados específicos de cada envio continuam obrigatórios. '
              'Confira se o modelo corresponde ao conteúdo real antes de emitir.',
              'Dados informados no pedido prevalecem. Esta mudança não paga nem imprime etiquetas.',
              'Confirme para guardar o padrão nas próximas conversas ou cancele.']
    return preview_reply(action, '\n'.join(lines))


def prepare_routine(db, message, identity, args):
    if not _authorized(db, message, identity, write=True):
        return {'erro': 'Somente Lucas habilitado no assistente pode alterar o padrão compartilhado de frete.'}
    args = RoutineArgs.model_validate(args)
    previous = db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    if previous:
        if previous.kind != 'padrao_frete':
            return {'erro': 'Esta mensagem já possui outra solicitação. Envie a alteração do padrão em uma nova mensagem.'}
        return {'confirmacao': routine_preview(previous)}
    try:
        current = get_routine(db)
    except HTTPException as error:
        return {'erro': error.detail}
    action = AssistantAction(source_message_id=message.id, user_id=message.user_id, kind='padrao_frete',
                             payload={'routine': args.model_dump(mode='json'),
                                      'expected_revision': current['revision'] if current else 0,
                                      'recipient': 'Padrão de frete da equipe'})
    db.add(action)
    db.flush()
    return {'confirmacao': routine_preview(action)}


def confirm_routine(db, message, action):
    user = db.get(Usuario, message.user_id)
    if not user or not user.ativo or not is_owner(user):
        return 'Somente Lucas pode alterar o padrão compartilhado de frete.'
    source = db.get(AssistantMessage, action.source_message_id)
    if (action.kind != 'padrao_frete' or action.user_id != message.user_id or not source
            or source.channel != message.channel or source.conversation_id != message.conversation_id):
        return 'Confirme na mesma conversa e com o usuário que pediu a alteração do padrão.'
    if action.status != 'draft':
        return f'Essa solicitação está {action.status}. Nenhuma alteração foi repetida.'
    created = action.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=utcnow().tzinfo)
    if created < utcnow() - timedelta(hours=24):
        return 'Solicitação expirada. Envie o pedido novamente.'
    try:
        saved = save_routine(db, action.payload['routine'], user_id=message.user_id,
                             expected_revision=action.payload['expected_revision'])
    except HTTPException as error:
        return str(error.detail)
    action.status, action.executed_at = 'executed', utcnow()
    return ('Padrão de frete salvo na memória da equipe. Vou preencher os campos ausentes nas próximas '
            'solicitações e mostrar os dados para conferência antes de emitir.' if saved['active'] else
            'Padrão de frete desativado. Pacote e conteúdo serão informados em cada envio.')


def merge_quote_defaults(db, arguments):
    """Return (copied quote arguments, provenance/missing-field metadata).

    Only absent/None package or products can be filled. Explicit structures,
    even invalid/empty ones, are left for the normal quote validator. The
    top-level ``quantidade`` is consumed solely to instantiate the saved product
    template and never stored. Full explicit products take precedence. Metadata
    contains key/revision only when defaults supplied values; no customer data.
    """
    result = deepcopy(arguments)
    quantity = result.pop('quantidade', None)
    routine = get_routine(db)
    applied = []
    if routine and routine['active']:
        if routine['package'] and result.get('package') is None:
            result['package'] = deepcopy(routine['package'])
            applied.append('package')
        if routine['product'] and result.get('products') is None and quantity is not None:
            quantity = RoutineQuantity(quantity=quantity).quantity
            result['products'] = [{**deepcopy(routine['product']), 'quantity': quantity}]
            applied.append('product')
    missing = []
    if result.get('package') is None:
        missing.append('package')
    if result.get('products') is None:
        missing.append('quantidade' if routine and routine['active'] and routine['product'] else 'products')
    metadata = {'key': ROUTINE_KEY if applied else None, 'revision': routine['revision'] if applied else None,
                'applied_fields': applied, 'missing_fields': missing}
    return result, metadata
