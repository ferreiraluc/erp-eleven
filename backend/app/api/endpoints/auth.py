from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from ...config import settings

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    nome: str
    email: str
    role: str
    ativo: bool

# Mock user for testing
MOCK_USER = {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "nome": "Administrador", 
    "email": "admin@loja.com",
    "role": "ADMIN",
    "ativo": True,
    "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"  # secret
}

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    # Mock authentication - in production, verify against database
    if login_data.email == MOCK_USER["email"] and login_data.password == "123456":
        access_token = create_access_token(data={"sub": login_data.email})
        return LoginResponse(access_token=access_token)
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/me", response_model=UserResponse)
async def get_current_user(email: str = Depends(verify_token)):
    # Mock user data - in production, fetch from database
    if email == MOCK_USER["email"]:
        return UserResponse(**{k: v for k, v in MOCK_USER.items() if k != "password_hash"})
    
    raise HTTPException(status_code=404, detail="User not found")