from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...models.cambista import Cambista
from ...models.exchange_rate import ExchangeRate, CurrencyPair
from ...schemas.cambista import CambistaCreate, CambistaResponse
from ...dependencies import get_current_active_user, require_role
from ..validators import validate_uuid

router = APIRouter()

@router.get("/", response_model=List[CambistaResponse])
def listar_cambistas(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    cambistas = db.query(Cambista).filter(Cambista.ativo == True).all()
    return cambistas

@router.post("/", response_model=CambistaResponse)
def criar_cambista(
    cambista: CambistaCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["ADMIN", "GERENTE"]))
):
    db_cambista = Cambista(**cambista.dict())
    db.add(db_cambista)
    db.commit()
    db.refresh(db_cambista)
    return db_cambista

@router.get("/{cambista_id}", response_model=CambistaResponse)
def obter_cambista(
    cambista_id: str, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    validated_id = validate_uuid(cambista_id, "cambista_id")
    cambista = db.query(Cambista).filter(Cambista.id == validated_id).first()
    if not cambista:
        raise HTTPException(status_code=404, detail="Cambista não encontrado")
    return cambista

@router.get("/{cambista_id}/current-rates")
def get_cambista_with_current_rates(
    cambista_id: str, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get cambista with current exchange rates from the system"""
    validated_id = validate_uuid(cambista_id, "cambista_id")
    cambista = db.query(Cambista).filter(Cambista.id == validated_id).first()
    if not cambista:
        raise HTTPException(status_code=404, detail="Cambista não encontrado")
    
    # Get current system exchange rates
    usd_to_pyg = db.query(ExchangeRate).filter(
        ExchangeRate.currency_pair == CurrencyPair.USD_TO_PYG,
        ExchangeRate.is_active == True
    ).first()
    
    usd_to_brl = db.query(ExchangeRate).filter(
        ExchangeRate.currency_pair == CurrencyPair.USD_TO_BRL,
        ExchangeRate.is_active == True
    ).first()
    
    eur_to_brl = db.query(ExchangeRate).filter(
        ExchangeRate.currency_pair == CurrencyPair.EUR_TO_BRL,
        ExchangeRate.is_active == True
    ).first()
    
    return {
        "cambista": cambista,
        "current_system_rates": {
            "usd_to_pyg": usd_to_pyg.rate if usd_to_pyg else None,
            "usd_to_brl": usd_to_brl.rate if usd_to_brl else None,
            "eur_to_brl": eur_to_brl.rate if eur_to_brl else None,
        },
        "rate_comparison": {
            "usd_to_brl_diff": float(cambista.taxa_u_para_r - usd_to_brl.rate) if usd_to_brl else None,
            "eur_to_brl_diff": float(cambista.taxa_eur_para_r - eur_to_brl.rate) if eur_to_brl else None,
        }
    }