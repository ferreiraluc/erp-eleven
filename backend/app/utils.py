import random
import string
from datetime import datetime
from .config import settings
from sqlalchemy.orm import Session
from typing import Optional

def generate_order_number(db: Session, prefix: str = "PED") -> str:
    """
    Generate unique order number with format: PED-YYYY-XXXXXX
    """
    year = settings.now().year
    
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

def calculate_payment_fee(metodo_pagamento: str) -> float:
    """
    Calculate payment method fee percentage based on Excel formula:
    =IF(E13="Thais"; C13*0.98; IF(E13="Credit"; C13*0.948; IF(E13="Debit"; C13*0.975; C13)))
    
    Returns the multiplier to apply to the gross amount
    """
    from .models.venda import PagamentoMetodo
    
    fee_rates = {
        PagamentoMetodo.PIX_THAIS.value: 0.98,      # 2% fee
        PagamentoMetodo.CREDITO.value: 0.948,       # 5.2% fee  
        PagamentoMetodo.DEBITO.value: 0.975,        # 2.5% fee
        PagamentoMetodo.PIX_POWER.value: 1.0,       # No fee
        PagamentoMetodo.PIX_MERCADO_PAGO.value: 1.0, # No fee
        PagamentoMetodo.PY_TRANSFER_SUDAMERIS.value: 1.0, # No fee
        PagamentoMetodo.PY_TRANSFER_INTERFISA.value: 1.0, # No fee
    }
    
    return fee_rates.get(metodo_pagamento, 1.0)

def calculate_net_amount(valor_bruto: float, metodo_pagamento: str) -> tuple[float, float]:
    """
    Calculate net amount after payment method fees
    
    Returns: (net_amount, fee_percentage)
    """
    fee_multiplier = calculate_payment_fee(metodo_pagamento)
    net_amount = valor_bruto * fee_multiplier
    fee_percentage = (1 - fee_multiplier) * 100
    
    return net_amount, fee_percentage

# =============================================================================
# DATETIME UTILITIES
# =============================================================================

def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a datetime object is timezone-aware.
    If it's naive, assume it's in the configured timezone.
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Naive datetime - assume it's in our configured timezone
        from .config import settings
        return dt.replace(tzinfo=settings.tz)
    
    return dt


def now_in_timezone() -> datetime:
    """
    Get current datetime in the configured timezone
    """
    from .config import settings
    return settings.now()
