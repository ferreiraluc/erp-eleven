import secrets
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
from ...services.login_throttle import login_limit
from ...services.user_sessions import verify_password, get_password_hash, issue_session, revoke_all
from ...services.user_audit import bind_actor, record

router = APIRouter()
_dummy_hash = get_password_hash(secrets.token_urlsafe(32))


def authenticate_user(db, email, password):
    user = db.query(Usuario).filter(func.lower(Usuario.email) == email.strip().lower()).first()
    # Equal bcrypt work for unknown/inactive accounts; never interpolate SQL.
    valid = verify_password(password, user.senha_hash if user else _dummy_hash)
    return user if user and valid else None


@router.post('/login', response_model=Token)
def login(body: UsuarioLogin, request: Request, db: Session = Depends(get_db)):
    login_limit(db, str(body.email), request.client.host if request.client else '')
    user = authenticate_user(db, str(body.email), body.senha)
    if not user or not user.ativo:
        record(db, 'login_failed', 'auth', status_code=401)
        db.commit()
        raise HTTPException(401, 'E-mail ou senha incorretos.')
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
    try: user.senha_hash = get_password_hash(body.new_password)
    except ValueError as exc: raise HTTPException(422,str(exc)) from None
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
    try: password_hash = get_password_hash(body.senha)
    except ValueError as exc: raise HTTPException(422,str(exc)) from None
    created = Usuario(nome=body.nome, email=email, senha_hash=password_hash,
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
