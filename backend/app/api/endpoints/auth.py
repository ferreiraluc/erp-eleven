from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt
from ...database import get_db
from ...models.usuario import Usuario
from ...schemas.usuario import UsuarioLogin, Token, UsuarioResponse, UsuarioCreate
from ...dependencies import get_current_active_user
from ...config import settings

router = APIRouter()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def _token_expiry() -> datetime:
    """
    Returns the JWT expiration as naive UTC datetime.
    Always expires at midnight (local timezone) 7 days from today,
    so sessions never cut off mid-shift and reset predictably every week.
    """
    now_local = datetime.now(settings.tz)
    midnight_today = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    expire_local = midnight_today + timedelta(days=7)
    return expire_local.astimezone(timezone.utc).replace(tzinfo=None)


def create_access_token(data: dict) -> str:
    """Create JWT access token — expires at midnight 7 days from now (local timezone)"""
    to_encode = data.copy()
    expire = _token_expiry()
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def authenticate_user(db: Session, email: str, password: str) -> Usuario:
    """Authenticate user credentials"""
    user = db.query(Usuario).filter(Usuario.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.senha_hash):
        return None
    return user

@router.post("/login", response_model=Token)
async def login(user_credentials: UsuarioLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access token"""
    user = authenticate_user(db, user_credentials.email, user_credentials.senha)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated"
        )
    
    # Update last login
    user.ultimo_login = settings.now()
    db.commit()
    
    access_token = create_access_token(data={"sub": user.email})
    expires_in = int((_token_expiry() - datetime.utcnow()).total_seconds())
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in
    )

@router.get("/me", response_model=UsuarioResponse)
async def get_current_user_info(current_user: Usuario = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user

@router.post("/register", response_model=UsuarioResponse)
async def register_user(
    user_data: UsuarioCreate, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Register new user (admin only)"""
    # Check if current user is admin
    if current_user.role.value != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create new users"
        )
    
    # Check if email already exists
    if db.query(Usuario).filter(Usuario.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.senha)
    db_user = Usuario(
        nome=user_data.nome,
        email=user_data.email,
        senha_hash=hashed_password,
        role=user_data.role,
        ativo=user_data.ativo
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@router.post("/logout")
async def logout(current_user: Usuario = Depends(get_current_active_user)):
    """Logout user (invalidate token on client side)"""
    return {"message": "Successfully logged out"}