#!/usr/bin/env python3
"""
Database Setup Script
Creates initial data for ERP Eleven system
"""

from sqlalchemy.orm import Session
from app.database import engine, get_db
from app.models import *
from app.api.endpoints.auth import get_password_hash
from decimal import Decimal
from app.models.usuario import Usuario, UsuarioRole
from app.models.venda import Venda, MoedaTipo, PagamentoMetodo  
from app.database import Base

def create_initial_admin():
    """Create initial admin user"""
    db = next(get_db())
    
    # Check if admin already exists
    existing_admin = db.query(Usuario).filter(Usuario.email == "admin@loja.com").first()
    if existing_admin:
        print("✅ Admin user already exists")
        return existing_admin
    
    # Create admin user
    admin_user = Usuario(
        nome="Administrator",
        email="admin@loja.com",
        senha_hash=get_password_hash("123456"),  # Change this in production!
        role= UsuarioRole.ADMIN,
        ativo=True
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    print(f"✅ Created admin user: {admin_user.email}")
    return admin_user

def create_sample_users(admin_user):
    """Create sample users for testing"""
    db = next(get_db())
    
    users_data = [
        {
            "nome": "João Silva",
            "email": "joao@loja.com",
            "role": UsuarioRole.GERENTE,
            "password": "gerente123"
        },
        {
            "nome": "Maria Santos",
            "email": "maria@loja.com", 
            "role": UsuarioRole.VENDEDOR,
            "password": "vendedor123"
        },
        {
            "nome": "Carlos Oliveira",
            "email": "carlos@loja.com",
            "role": UsuarioRole.FINANCEIRO,
            "password": "financeiro123"
        }
    ]
    
    created_users = []
    for user_data in users_data:
        # Check if user already exists
        existing = db.query(Usuario).filter(Usuario.email == user_data["email"]).first()
        if existing:
            print(f"⚠️ User {user_data['email']} already exists")
            created_users.append(existing)
            continue
        
        user = Usuario(
            nome=user_data["nome"],
            email=user_data["email"],
            senha_hash=get_password_hash(user_data["password"]),
            role=user_data["role"],
            ativo=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"✅ Created user: {user.nome} ({user.email})")
        created_users.append(user)
    
    return created_users

def create_sample_vendors(users):
    """Create sample vendors"""
    db = next(get_db())
    
    vendors_data = [
        {
            "nome": "Maria Vendedora",
            "taxa_comissao": Decimal("12.5"),
            "meta_semanal": Decimal("2500.00"),
            "telefone": "11987654321",
            "conta_bancaria": "123456-7"
        },
        {
            "nome": "José Santos",
            "taxa_comissao": Decimal("15.0"),
            "meta_semanal": Decimal("3000.00"),
            "telefone": "11976543210",
            "conta_bancaria": "234567-8"
        }
    ]
    
    created_vendors = []
    for i, vendor_data in enumerate(vendors_data):
        # Check if vendor already exists
        existing = db.query(Vendedor).filter(Vendedor.nome == vendor_data["nome"]).first()
        if existing:
            print(f"⚠️ Vendor {vendor_data['nome']} already exists")
            created_vendors.append(existing)
            continue
        
        vendor = Vendedor(
            nome=vendor_data["nome"],
            usuario_id=users[min(i+1, len(users)-1)].id if users else None,
            taxa_comissao=vendor_data["taxa_comissao"],
            meta_semanal=vendor_data["meta_semanal"],
            telefone=vendor_data["telefone"],
            conta_bancaria=vendor_data["conta_bancaria"],
            ativo=True
        )
        
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        
        print(f"✅ Created vendor: {vendor.nome}")
        created_vendors.append(vendor)
    
    return created_vendors

def create_sample_cambistas():
    """Create sample currency exchangers"""
    db = next(get_db())
    
    cambistas_data = [
        {
            "nome": "Casa de Câmbio Central",
            "taxa_g_para_r": Decimal("5.65"),
            "taxa_u_para_r": Decimal("5.50"),
            "taxa_eur_para_r": Decimal("6.20"),
            "telefone": "11955555555",
            "conta_bancaria": "987654-3"
        },
        {
            "nome": "Câmbio Express",
            "taxa_g_para_r": Decimal("5.70"),
            "taxa_u_para_r": Decimal("5.45"),
            "taxa_eur_para_r": Decimal("6.15"),
            "telefone": "11944444444",
            "conta_bancaria": "876543-2"
        }
    ]
    
    created_cambistas = []
    for cambista_data in cambistas_data:
        # Check if cambista already exists
        existing = db.query(Cambista).filter(Cambista.nome == cambista_data["nome"]).first()
        if existing:
            print(f"⚠️ Cambista {cambista_data['nome']} already exists")
            created_cambistas.append(existing)
            continue
        
        cambista = Cambista(**cambista_data)
        
        db.add(cambista)
        db.commit()
        db.refresh(cambista)
        
        print(f"✅ Created cambista: {cambista.nome}")
        created_cambistas.append(cambista)
    
    return created_cambistas

def create_sample_sales(vendors, cambistas, users):
    """Create sample sales data"""
    db = next(get_db())
    
    if not vendors or not users:
        print("⚠️ No vendors or users available for sample sales")
        return []
    
    from datetime import date
    
    sales_data = [
        {
            "data_venda": date.today(),
            "vendedor_id": vendors[0].id,
            "moeda": MoedaTipo.R_DOLLAR,
            "valor_bruto": Decimal("150.00"),
            "metodo_pagamento": PagamentoMetodo.PIX,
            "valor_liquido": Decimal("150.00"),
            "descricao_produto": "Camiseta básica",
            "created_by": users[0].id
        },
        {
            "data_venda": date.today(),
            "vendedor_id": vendors[0].id if len(vendors) > 0 else vendors[0].id,
            "moeda": MoedaTipo.G_DOLLAR,
            "valor_bruto": Decimal("25.00"),
            "metodo_pagamento": PagamentoMetodo.CREDITO,
            "cambista_id": cambistas[0].id if cambistas else None,
            "taxa_cambio_usada": Decimal("5.65") if cambistas else None,
            "valor_cambista": Decimal("141.25") if cambistas else None,
            "valor_liquido": Decimal("141.25"),
            "descricao_produto": "Calça jeans",
            "created_by": users[0].id
        }
    ]
    
    created_sales = []
    for sale_data in sales_data:
        venda = Venda(**sale_data)
        
        db.add(venda)
        db.commit()
        db.refresh(venda)
        
        print(f"✅ Created sale: {venda.valor_liquido} {venda.moeda.value}")
        created_sales.append(venda)
    
    return created_sales

def main():
    """Set up initial database data"""
    print("🚀 Setting up ERP Eleven Database")
    print("=" * 40)
    
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created/verified")
        
        # Create initial data
        admin_user = create_initial_admin()
        users = create_sample_users(admin_user)
        vendors = create_sample_vendors(users)
        cambistas = create_sample_cambistas()
        sales = create_sample_sales(vendors, cambistas, users)
        
        print("\n" + "=" * 40)
        print("🎉 Database setup completed successfully!")
        print("\nTest credentials:")
        print("Admin: admin@loja.com / 123456")
        print("Manager: joao@loja.com / gerente123")
        print("Vendor: maria@loja.com / vendedor123")
        print("Finance: carlos@loja.com / financeiro123")
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()