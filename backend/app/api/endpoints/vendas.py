from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
from datetime import date
from ...database import get_db
from ...models.venda import Venda
from ...schemas.venda import VendaCreate, VendaResponse
from ...utils import calculate_net_amount
from ...services.thais_transfer_service import ThaisTransferService
from ...dependencies import get_current_active_user
from ..validators import validate_uuid

router = APIRouter()

@router.get("/", response_model=List[VendaResponse])
def listar_vendas(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    vendas = db.query(Venda).offset(skip).limit(limit).all()
    return vendas

@router.post("/", response_model=VendaResponse)
def criar_venda(
    venda: VendaCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    # Calculate net amount and fee based on payment method
    valor_liquido, taxa_desconto = calculate_net_amount(
        float(venda.valor_bruto), 
        venda.metodo_pagamento.value
    )
    
    # Create venda data with calculated values
    venda_data = {
        "moeda": venda.moeda,
        "valor_bruto": venda.valor_bruto,
        "vendedor_id": venda.vendedor_id,
        "metodo_pagamento": venda.metodo_pagamento,
        "valor_liquido": Decimal(str(valor_liquido)),
        "taxa_desconto_pagamento": Decimal(str(taxa_desconto)),
        "data_venda": venda.data_venda or date.today(),
        "cambista_id": venda.cambista_id,
        "descricao_produto": venda.descricao_produto,
        "observacoes": venda.observacoes,
        "created_by": venda.created_by
    }
    
    db_venda = Venda(**venda_data)
    db.add(db_venda)
    db.flush()  # Get the ID without committing yet
    
    # Handle PIX_THAIS automatic transfer accumulation
    if ThaisTransferService.is_thais_payment(venda.metodo_pagamento):
        transfer = ThaisTransferService.add_sale_to_pending_transfer(db, db_venda)
        if transfer:
            db_venda.pending_transfer_id = transfer.id
            db_venda.requires_thais_transfer = True
    
    db.commit()
    db.refresh(db_venda)
    return db_venda

@router.get("/{venda_id}", response_model=VendaResponse)
def obter_venda(
    venda_id: str, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    validated_id = validate_uuid(venda_id, "venda_id")
    venda = db.query(Venda).filter(Venda.id == validated_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    return venda