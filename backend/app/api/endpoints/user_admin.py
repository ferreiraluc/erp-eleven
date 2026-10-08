import uuid
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import require_owner, get_current_active_user
from ...models.usuario import Usuario, UsuarioRole
from ...models.vendedor import Vendedor
from ...models.access import AuditEvent, now
from ...schemas.usuario import UsuarioResponse
from ...services.access_policy import is_owner
from ...services.user_sessions import revoke_all, get_password_hash
from ...services.user_audit import record

router = APIRouter()


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
    # Cached clients may still send heartbeats; accept without recording navigation.
    return {'active_seconds': 0, 'tracking_enabled': False}


@router.get('/audit')
def audit(days: int = Query(7, ge=1, le=90), user_id: uuid.UUID | None = None,
          module: str | None = Query(None, max_length=80), action: str | None = Query(None, max_length=40),
          offset: int = Query(0, ge=0, le=1000000), limit: int = Query(50, ge=1, le=100),
          owner=Depends(require_owner), db: Session = Depends(get_db)):
    since = now() - timedelta(days=days)
    # Preserve historical reads in the database without flooding the audit screen.
    events = db.query(AuditEvent).filter(AuditEvent.occurred_at >= since, AuditEvent.action.notin_(['read', 'request']))
    if user_id: events = events.filter(AuditEvent.user_id == user_id)
    if module: events = events.filter(AuditEvent.module == module)
    if action: events = events.filter(AuditEvent.action == action)
    count = events.count()
    rows = events.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).offset(offset).limit(limit).all()
    actions = events.with_entities(AuditEvent.user_id, AuditEvent.action, func.count()).group_by(AuditEvent.user_id, AuditEvent.action).all()
    last_events = dict(events.with_entities(AuditEvent.user_id, func.max(AuditEvent.occurred_at)).group_by(AuditEvent.user_id).all())
    names = {u.id: u.nome for u in db.query(Usuario).all()}
    ids = {r[0] for r in actions if r[0]}
    return {'total': count, 'offset': offset, 'limit': limit, 'since': since,
            'active_seconds': 0, 'tracking_enabled': False,
            'users': [{'id': str(uid), 'name': names.get(uid, 'Usuário'),
                       'active_seconds': 0, 'last_seen_at': last_events.get(uid),
                       'actions': {a: n for u, a, n in actions if u == uid}} for uid in sorted(ids, key=lambda x:names.get(x,''))],
            'modules': [],
            'events': [{key: getattr(r, key) for key in ('id','occurred_at','user_id','actor_name','source','action',
                       'module','entity','entity_id','request_id','route','method','status_code','changes')} for r in rows]}
