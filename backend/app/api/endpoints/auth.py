from threading import Lock
import time
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...database import get_db
from ...models.usuario import Usuario, UsuarioRole
from ...models.access import AuthSession, now
from ...schemas.usuario import UsuarioLogin, Token, UsuarioResponse, UsuarioCreate
from ...dependencies import get_current_active_user, require_owner
from ...services.access_policy import OWNER_EMAIL
from ...services.user_sessions import verify_password, get_password_hash, issue_session, revoke_all
from ...services.user_audit import bind_actor, record

router = APIRouter()
_attempts = {}
_attempts_lock = Lock()


def authenticate_user(db, email, password):
    user = db.query(Usuario).filter(func.lower(Usuario.email) == email.strip().lower()).first()
    return user if user and verify_password(password, user.senha_hash) else None


def login_limit(email, address):
    key = (email.lower(), address)
    current = time.monotonic()
    with _attempts_lock:
        expired = [k for k, (_, since) in _attempts.items() if current - since > 600]
        for k in expired: _attempts.pop(k, None)
        count, since = _attempts.get(key, (0, current))
        if count >= 12:
            raise HTTPException(429, 'Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.')
        if len(_attempts) >= 10000: _attempts.pop(next(iter(_attempts)))
        _attempts[key] = (count + 1, since)
    return key


@router.post('/login', response_model=Token)
def login(body: UsuarioLogin, request: Request, db: Session = Depends(get_db)):
    key = login_limit(str(body.email), request.client.host if request.client else '')
    user = authenticate_user(db, str(body.email), body.senha)
    if not user or not user.ativo:
        record(db, 'login_failed', 'auth', status_code=401)
        db.commit()
        raise HTTPException(401, 'E-mail ou senha incorretos.')
    with _attempts_lock: _attempts.pop(key, None)
    bind_actor(db, user)
    user.ultimo_login = now()
    result = issue_session(db, user)
    record(db, 'login', 'auth', status_code=200)
    db.commit()
    return result


@router.get('/me', response_model=UsuarioResponse)
def me(user: Usuario = Depends(get_current_active_user)):
    return user


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=6, max_length=72)

    @field_validator('new_password')
    @classmethod
    def valid_bytes(cls, value):
        if len(value.encode('utf-8')) > 72 or not value.strip():
            raise ValueError('Senha inválida: use até 72 bytes.')
        return value


@router.post('/password', response_model=Token)
def change_password(body: PasswordChange, user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter_by(id=user.id).populate_existing().with_for_update().one()
    if not verify_password(body.current_password, user.senha_hash):
        raise HTTPException(400, 'A senha atual está incorreta.')
    if body.current_password == body.new_password:
        raise HTTPException(400, 'Escolha uma senha diferente da senha atual.')
    user.senha_hash = get_password_hash(body.new_password)
    user.must_change_password = False
    revoke_all(db, user)
    result = issue_session(db, user)
    record(db, 'password_changed', 'auth')
    db.commit()
    return result


@router.post('/register', response_model=UsuarioResponse)
def register_user(body: UsuarioCreate, user=Depends(require_owner), db: Session = Depends(get_db)):
    email = str(body.email).strip().lower()
    if body.role == UsuarioRole.ADMIN and email != OWNER_EMAIL:
        raise HTTPException(400, 'Somente Lucas pode ter perfil administrador.')
    if db.query(Usuario).filter(func.lower(Usuario.email) == email).first():
        raise HTTPException(409, 'E-mail já cadastrado.')
    created = Usuario(nome=body.nome, email=email, senha_hash=get_password_hash(body.senha),
                      role=body.role, ativo=body.ativo, must_change_password=True,
                      sales_scope='own' if body.role != UsuarioRole.ADMIN else 'all')
    db.add(created)
    db.commit()
    db.refresh(created)
    return created


@router.post('/logout')
def logout(request: Request, user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    session = db.get(AuthSession, request.state.auth_session_id)
    session.revoked_at = now()
    record(db, 'logout', 'auth')
    db.commit()
    return {'ok': True}
