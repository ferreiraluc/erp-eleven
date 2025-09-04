#!/usr/bin/env python3
"""
Script para criar funcionários padrão para teste do sistema de folgas
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from app.database import engine, SessionLocal
from app.models.funcionario import Funcionario
from sqlalchemy.orm import Session
import uuid

def create_default_funcionarios():
    """Cria funcionários padrão para teste"""
    db: Session = SessionLocal()
    
    try:
        # Verificar se já existem funcionários
        existing_count = db.query(Funcionario).count()
        if existing_count >= 5:
            print(f"Já existem {existing_count} funcionários. Pulando criação.")
            return
        
        funcionarios_default = [
            {
                "nome": "Ana Silva",
                "cpf": "123.456.789-01",
                "cargo": "Vendedora Senior",
                "cor_calendario": "#3B82F6",  # Azul
                "salario": 3000.00,
                "telefone": "(11) 98765-4321"
            },
            {
                "nome": "Carlos Santos",
                "cpf": "234.567.890-12", 
                "cargo": "Vendedor",
                "cor_calendario": "#EF4444",  # Vermelho
                "salario": 2500.00,
                "telefone": "(11) 98765-4322"
            },
            {
                "nome": "Maria Oliveira",
                "cpf": "345.678.901-23",
                "cargo": "Gerente de Vendas", 
                "cor_calendario": "#10B981",  # Verde
                "salario": 4500.00,
                "telefone": "(11) 98765-4323"
            },
            {
                "nome": "João Pereira",
                "cpf": "456.789.012-34",
                "cargo": "Vendedor Junior",
                "cor_calendario": "#F59E0B",  # Amarelo/Laranja
                "salario": 2000.00,
                "telefone": "(11) 98765-4324"
            },
            {
                "nome": "Laura Costa",
                "cpf": "567.890.123-45",
                "cargo": "Supervisora",
                "cor_calendario": "#8B5CF6",  # Roxo
                "salario": 3500.00,
                "telefone": "(11) 98765-4325"
            }
        ]
        
        for func_data in funcionarios_default:
            # Verificar se já existe pelo CPF
            existing = db.query(Funcionario).filter(Funcionario.cpf == func_data["cpf"]).first()
            if existing:
                print(f"Funcionário {func_data['nome']} já existe (CPF: {func_data['cpf']})")
                continue
            
            funcionario = Funcionario(
                id=uuid.uuid4(),
                nome=func_data["nome"],
                cpf=func_data["cpf"],
                cargo=func_data["cargo"],
                cor_calendario=func_data["cor_calendario"],
                salario=func_data["salario"],
                telefone=func_data["telefone"],
                ativo=True
            )
            
            db.add(funcionario)
            print(f"Criado funcionário: {func_data['nome']}")
        
        db.commit()
        print("Funcionários padrão criados com sucesso!")
        
    except Exception as e:
        print(f"Erro ao criar funcionários: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_default_funcionarios()