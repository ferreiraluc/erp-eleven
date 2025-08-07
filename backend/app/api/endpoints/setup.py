"""
Setup endpoints for initial database configuration
These endpoints should only be used during initial setup
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from ...database import get_db
from ...models.usuario import Usuario, UsuarioRole

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/create-admin")
async def create_admin_user(db: Session = Depends(get_db)):
    """Create initial admin user - USE ONLY FOR SETUP"""
    
    # Check if any admin user already exists
    existing_admin = db.query(Usuario).filter(Usuario.role == UsuarioRole.ADMIN).first()
    if existing_admin:
        return {
            "message": "Admin user already exists",
            "email": existing_admin.email,
            "name": existing_admin.nome
        }
    
    # Hash the default password
    hashed_password = pwd_context.hash("123456")
    
    # Create admin user
    admin_user = Usuario(
        nome="Administrador",
        email="admin@loja.com",
        senha_hash=hashed_password,
        role=UsuarioRole.ADMIN,
        ativo=True
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    return {
        "message": "Admin user created successfully",
        "id": str(admin_user.id),
        "email": admin_user.email,
        "name": admin_user.nome,
        "role": admin_user.role.value,
        "password": "123456"
    }

@router.get("/check-users")
async def check_users(db: Session = Depends(get_db)):
    """Check existing users in database"""
    users = db.query(Usuario).all()
    
    return {
        "total_users": len(users),
        "users": [
            {
                "id": str(user.id),
                "email": user.email,
                "name": user.nome,
                "role": user.role.value,
                "active": user.ativo,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
    }