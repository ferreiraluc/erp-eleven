import uuid
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from .database import get_db
from .models.usuario import Usuario
from .models.access import AuthSession, now
from .config import settings
from .services.user_sessions import aware
from .services.user_audit import bind_actor
from .services.access_policy import is_owner

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Usuario:
    invalid = HTTPException(401, 'Sessão expirada. Entre novamente.', headers={'WWW-Authenticate': 'Bearer'})
    if not credentials:
        raise invalid
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id, session_id = uuid.UUID(payload['sub']), uuid.UUID(payload['sid'])
        version = payload['ver']
    except (JWTError, ValueError, KeyError, TypeError):
        raise invalid from None
    user = db.get(Usuario, user_id)
    session = db.get(AuthSession, session_id)
    if (not user or not user.ativo or version != user.auth_version or not session
            or session.user_id != user.id or session.revoked_at or aware(session.expires_at) <= now()):
        raise invalid
    if user.role.value == 'ADMIN' and not is_owner(user):
        raise invalid
    route = getattr(request.scope.get('route'), 'path', request.url.path)
    request.state.audit_actor = bind_actor(db, user, request_id=str(uuid.uuid4()), route=route, method=request.method)
    request.state.auth_session_id = session.id
    if user.must_change_password and request.url.path not in ('/api/auth/me', '/api/auth/password', '/api/auth/logout'):
        raise HTTPException(403, 'PASSWORD_CHANGE_REQUIRED')
    return user


async def get_current_active_user(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    return current_user


def require_role(required_roles: list):
    def role_checker(current_user: Usuario = Depends(get_current_active_user)):
        if current_user.role.value not in required_roles:
            raise HTTPException(403, 'Operação não permitida para seu perfil.')
        return current_user
    return role_checker


async def require_owner(current_user: Usuario = Depends(get_current_active_user)):
    if not is_owner(current_user):
        raise HTTPException(403, 'Acesso exclusivo do administrador Lucas.')
    return current_user
