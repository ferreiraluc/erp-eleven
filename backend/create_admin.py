"""
Script to create admin user in the database
Run this once to set up the initial admin user
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.models.usuario import Usuario, UserRole
from app.database import Base

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin_user():
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not found")
        return False
        
    print(f"🔗 Connecting to database: {database_url[:50]}...")
    
    try:
        # Create engine and session
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        # Check if admin user already exists
        existing_admin = session.query(Usuario).filter(Usuario.email == "admin@loja.com").first()
        if existing_admin:
            print("✅ Admin user already exists!")
            print(f"   Email: {existing_admin.email}")
            print(f"   Name: {existing_admin.nome}")
            print(f"   Role: {existing_admin.role.value}")
            print(f"   Active: {existing_admin.ativo}")
            session.close()
            return True
        
        # Hash the password
        hashed_password = pwd_context.hash("123456")
        print("🔐 Password hashed successfully")
        
        # Create admin user
        admin_user = Usuario(
            nome="Administrador",
            email="admin@loja.com", 
            senha_hash=hashed_password,
            role=UserRole.ADMIN,
            ativo=True
        )
        
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
        
        print("✅ Admin user created successfully!")
        print(f"   ID: {admin_user.id}")
        print(f"   Email: {admin_user.email}")
        print(f"   Name: {admin_user.nome}")
        print(f"   Role: {admin_user.role.value}")
        print(f"   Password: 123456")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin user: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Creating admin user...")
    success = create_admin_user()
    if success:
        print("🎉 Admin user setup completed!")
    else:
        print("💥 Admin user setup failed!")
        sys.exit(1)