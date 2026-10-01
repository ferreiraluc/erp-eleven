import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import require_owner, get_current_active_user
from ...models.usuario import Usuario, UsuarioRole
from ...models.vendedor import Vendedor
from ...models.access import AuditEvent, ActivitySpan, AuthSession, now
from ...schemas.usuario import UsuarioResponse
from ...services.access_policy import is_owner
from ...services.user_sessions import revoke_all, get_password_hash, aware
from ...services.user_audit import record

router = APIRouter()
MODULES = {'dashboard', 'bi-vendas', 'enderecos', 'assistente', 'exchange-rates', 'rastreamento',
           'vendors', 'vendas', 'pedidos', 'inventory', 'clientes', 'pdv', 'fiado', 'conta', 'auditoria', 'usuarios'}


@router.get('/users', response_model=list[UsuarioResponse])
def users(owner=Depends(require_owner), db: Session = Depends(get_db)):
    return db.query(Usuario).order_by(Usuario.nome).all()


class UserAccess(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    ativo: bool
    sales_scope: Literal['all', 'own']
    sales_seller: str | None = Field(None, max_length=100)
    vendedor_id: uuid.UUID | None = None


def validate_binding(body: UserAccess, db: Session):
    if body.sales_scope == 'own' and (not body.sales_seller or not body.vendedor_id):
        raise HTTPException(400, 'Vincule o vendedor e o nome nas planilhas para liberar as vendas pessoais.')
    if body.vendedor_id and not db.get(Vendedor, body.vendedor_id):
        raise HTTPException(400, 'Vendedor não encontrado.')


class CreateUser(UserAccess):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


@router.post('/users', response_model=UsuarioResponse, status_code=201)
def create_user(body: CreateUser, owner=Depends(require_owner), db: Session = Depends(get_db)):
    email = str(body.email).strip().lower()
    if db.query(Usuario).filter(func.lower(Usuario.email) == email).first():
        raise HTTPException(409, 'Este e-mail já está cadastrado.')
    validate_binding(body, db)
    try:
        password_hash = get_password_hash(body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    user = Usuario(**body.model_dump(exclude={'password', 'email'}), email=email,
                   senha_hash=password_hash, role=UsuarioRole.GERENTE, must_change_password=True)
    db.add(user)
    db.flush()
    record(db, 'access_created', 'users', entity='usuarios', entity_id=str(user.id))
    db.commit()
    db.refresh(user)
    return user


@router.put('/users/{user_id}', response_model=UsuarioResponse)
def update_user(user_id: uuid.UUID, body: UserAccess, owner=Depends(require_owner), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter_by(id=user_id).populate_existing().with_for_update().first()
    if not user: raise HTTPException(404, 'Usuário não encontrado.')
    if is_owner(user) and (not body.ativo or body.sales_scope != 'all'):
        raise HTTPException(400, 'O administrador principal deve permanecer ativo e com acesso completo.')
    validate_binding(body, db)
    changed = any(getattr(user, key) != value for key, value in body.model_dump().items())
    for key, value in body.model_dump().items(): setattr(user, key, value)
    user.role = UsuarioRole.ADMIN if is_owner(user) else UsuarioRole.GERENTE
    if changed: revoke_all(db, user)
    record(db, 'access_changed', 'users', entity='usuarios', entity_id=str(user.id))
    db.commit()
    db.refresh(user)
    return user


class ResetPassword(BaseModel):
    password: str = Field(min_length=6, max_length=72)


@router.post('/users/{user_id}/reset-password')
def reset_password(user_id: uuid.UUID, body: ResetPassword, owner=Depends(require_owner), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter_by(id=user_id).populate_existing().with_for_update().first()
    if not user: raise HTTPException(404, 'Usuário não encontrado.')
    if user.id == owner.id: raise HTTPException(400, 'Altere sua própria senha em Minha conta.')
    try: user.senha_hash = get_password_hash(body.password)
    except ValueError as exc: raise HTTPException(400, str(exc)) from None
    user.must_change_password = True
    revoke_all(db, user)
    record(db, 'password_reset', 'users', entity='usuarios', entity_id=str(user.id))
    db.commit()
    return {'ok': True}


class Activity(BaseModel):
    id: uuid.UUID
    module: str = Field(max_length=80)
    sequence: int = Field(ge=0, le=1000000)
    seconds: int = Field(ge=0, le=30)


@router.post('/activity')
def activity(body: Activity, request: Request, user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    if body.module not in MODULES: raise HTTPException(400, 'Módulo inválido.')
    moment = now()
    session = db.query(AuthSession).filter_by(id=request.state.auth_session_id).with_for_update().one()
    span = db.get(ActivitySpan, body.id)
    if span and (span.user_id != user.id or span.session_id != session.id or span.module != body.module):
        raise HTTPException(409, 'Registro de atividade inválido.')
    if not span:
        # First contact establishes the server clock. Never trust an arbitrary past timestamp.
        span = ActivitySpan(id=body.id, user_id=user.id, session_id=session.id, module=body.module,
                            started_at=moment, last_seen_at=moment, active_seconds=0, sequence=body.sequence)
        db.add(span)
        session.activity_credit_at = moment
    elif body.sequence > span.sequence:
        elapsed = max(0, (moment - aware(span.last_seen_at)).total_seconds())
        shared = max(0, (moment - aware(session.activity_credit_at or span.last_seen_at)).total_seconds())
        # No accumulated credit after offline/suspended intervals; duplicate tabs share this cap.
        credit = min(body.seconds, int(elapsed), int(shared), 30) if elapsed <= 90 else 0
        span.active_seconds += credit
        span.last_seen_at, span.sequence = moment, body.sequence
        session.activity_credit_at = moment
    db.commit()
    return {'active_seconds': span.active_seconds}


@router.get('/audit')
def audit(days: int = Query(7, ge=1, le=90), user_id: uuid.UUID | None = None,
          module: str | None = Query(None, max_length=80), action: str | None = Query(None, max_length=40),
          offset: int = Query(0, ge=0, le=1000000), limit: int = Query(50, ge=1, le=100),
          owner=Depends(require_owner), db: Session = Depends(get_db)):
    since = now() - timedelta(days=days)
    events = db.query(AuditEvent).filter(AuditEvent.occurred_at >= since)
    spans = db.query(ActivitySpan).filter(ActivitySpan.started_at >= since)
    if user_id:
        events = events.filter(AuditEvent.user_id == user_id)
        spans = spans.filter(ActivitySpan.user_id == user_id)
    if module:
        events = events.filter(AuditEvent.module == module)
        spans = spans.filter(ActivitySpan.module == module)
    if action: events = events.filter(AuditEvent.action == action)
    count = events.count()
    rows = events.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).offset(offset).limit(limit).all()
    per_user = spans.with_entities(ActivitySpan.user_id, func.sum(ActivitySpan.active_seconds),
                                  func.max(ActivitySpan.last_seen_at)).group_by(ActivitySpan.user_id).all()
    per_module = spans.with_entities(ActivitySpan.module, func.sum(ActivitySpan.active_seconds)).group_by(ActivitySpan.module).all()
    actions = events.with_entities(AuditEvent.user_id, AuditEvent.action, func.count()).group_by(AuditEvent.user_id, AuditEvent.action).all()
    names = {u.id: u.nome for u in db.query(Usuario).all()}
    ids = {r[0] for r in per_user} | {r[0] for r in actions if r[0]}
    return {'total': count, 'offset': offset, 'limit': limit, 'since': since,
            'active_seconds': sum(r[1] for r in per_user),
            'users': [{'id': str(uid), 'name': names.get(uid, 'Usuário'),
                       'active_seconds': next((r[1] for r in per_user if r[0] == uid), 0),
                       'last_seen_at': next((r[2] for r in per_user if r[0] == uid), None),
                       'actions': {a: n for u, a, n in actions if u == uid}} for uid in sorted(ids, key=lambda x:names.get(x,''))],
            'modules': [{'module': name, 'active_seconds': seconds} for name, seconds in per_module],
            'events': [{key: getattr(r, key) for key in ('id','occurred_at','user_id','actor_name','source','action',
                       'module','entity','entity_id','request_id','route','method','status_code','changes')} for r in rows]}
