import random
import string
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional

def generate_order_number(db: Session, prefix: str = "PED") -> str:
    """
    Generate unique order number with format: PED-YYYY-XXXXXX
    """
    year = datetime.now().year
    
    # Generate random 6-digit number
    random_number = ''.join(random.choices(string.digits, k=6))
    
    order_number = f"{prefix}-{year}-{random_number}"
    
    # Check if order number already exists (very unlikely but possible)
    from .models.pedido import Pedido
    existing = db.query(Pedido).filter(Pedido.numero_pedido == order_number).first()
    
    # If exists, generate a new one (recursive)
    if existing:
        return generate_order_number(db, prefix)
    
    return order_number

def validate_brazilian_phone(phone: Optional[str]) -> bool:
    """
    Validate Brazilian phone number format
    """
    if not phone:
        return True
    
    # Remove all non-digits
    digits_only = ''.join(filter(str.isdigit, phone))
    
    # Brazilian phone numbers have 10 or 11 digits
    return len(digits_only) in [10, 11]

def validate_brazilian_cep(cep: Optional[str]) -> bool:
    """
    Validate Brazilian CEP format
    """
    if not cep:
        return True
    
    # Remove all non-digits
    digits_only = ''.join(filter(str.isdigit, cep))
    
    # CEP has exactly 8 digits
    return len(digits_only) == 8

def validate_brazilian_cpf(cpf: Optional[str]) -> bool:
    """
    Validate Brazilian CPF format and check digit
    """
    if not cpf:
        return True
        
    # Remove all non-digits
    cpf = ''.join(filter(str.isdigit, cpf))
    
    # CPF must have 11 digits
    if len(cpf) != 11:
        return False
    
    # Check for known invalid patterns
    if cpf in ['00000000000', '11111111111', '22222222222', '33333333333',
               '44444444444', '55555555555', '66666666666', '77777777777',
               '88888888888', '99999999999']:
        return False
    
    # Calculate first check digit
    sum1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digit1 = 11 - (sum1 % 11)
    if digit1 >= 10:
        digit1 = 0
    
    # Calculate second check digit
    sum2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digit2 = 11 - (sum2 % 11)
    if digit2 >= 10:
        digit2 = 0
    
    # Verify check digits
    return cpf[9] == str(digit1) and cpf[10] == str(digit2)

def format_currency(value: float, currency: str = "R$") -> str:
    """
    Format currency value for display
    """
    return f"{currency} {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def calculate_commission(valor_venda: float, taxa_comissao: float) -> float:
    """
    Calculate commission amount
    """
    return (valor_venda * taxa_comissao) / 100