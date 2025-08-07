from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...models.exchange_rate import ExchangeRate, CurrencyPair
from ...schemas.exchange_rate import (
    ExchangeRateCreate, 
    ExchangeRateResponse, 
    ExchangeRateUpdate,
    QuickRateUpdate,
    CurrentRatesResponse
)
from ...dependencies import get_current_active_user, require_role

router = APIRouter()

@router.get("/current", response_model=CurrentRatesResponse)
def get_current_rates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get current exchange rates for easy frontend consumption"""
    rates = db.query(ExchangeRate).filter(ExchangeRate.is_active == True).all()
    
    result = CurrentRatesResponse()
    latest_update = None
    source = None
    
    for rate in rates:
        if rate.currency_pair == CurrencyPair.USD_TO_PYG:
            result.usd_to_pyg = rate.rate
        elif rate.currency_pair == CurrencyPair.USD_TO_BRL:
            result.usd_to_brl = rate.rate
        elif rate.currency_pair == CurrencyPair.EUR_TO_PYG:
            result.eur_to_pyg = rate.rate
        elif rate.currency_pair == CurrencyPair.EUR_TO_BRL:
            result.eur_to_brl = rate.rate
        
        # Track most recent update
        if not latest_update or rate.updated_at > latest_update:
            latest_update = rate.updated_at
            source = rate.source
    
    result.last_updated = latest_update
    result.source = source
    return result

@router.post("/quick-update")
def quick_update_rates(
    rates: QuickRateUpdate, 
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Quick update multiple exchange rates - perfect for footer editing"""
    updated_rates = []
    
    # Update USD to PYG
    if rates.usd_to_pyg is not None:
        rate_record = db.query(ExchangeRate).filter(
            ExchangeRate.currency_pair == CurrencyPair.USD_TO_PYG
        ).first()
        
        if rate_record:
            rate_record.rate = rates.usd_to_pyg
            rate_record.updated_by = rates.updated_by
        else:
            rate_record = ExchangeRate(
                currency_pair=CurrencyPair.USD_TO_PYG,
                rate=rates.usd_to_pyg,
                updated_by=rates.updated_by
            )
            db.add(rate_record)
        updated_rates.append("USD_TO_PYG")
    
    # Update USD to BRL
    if rates.usd_to_brl is not None:
        rate_record = db.query(ExchangeRate).filter(
            ExchangeRate.currency_pair == CurrencyPair.USD_TO_BRL
        ).first()
        
        if rate_record:
            rate_record.rate = rates.usd_to_brl
            rate_record.updated_by = rates.updated_by
        else:
            rate_record = ExchangeRate(
                currency_pair=CurrencyPair.USD_TO_BRL,
                rate=rates.usd_to_brl,
                updated_by=rates.updated_by
            )
            db.add(rate_record)
        updated_rates.append("USD_TO_BRL")
    
    # Update EUR to PYG  
    if rates.eur_to_pyg is not None:
        rate_record = db.query(ExchangeRate).filter(
            ExchangeRate.currency_pair == CurrencyPair.EUR_TO_PYG
        ).first()
        
        if rate_record:
            rate_record.rate = rates.eur_to_pyg
            rate_record.updated_by = rates.updated_by
        else:
            rate_record = ExchangeRate(
                currency_pair=CurrencyPair.EUR_TO_PYG,
                rate=rates.eur_to_pyg,
                updated_by=rates.updated_by
            )
            db.add(rate_record)
        updated_rates.append("EUR_TO_PYG")
    
    # Update EUR to BRL
    if rates.eur_to_brl is not None:
        rate_record = db.query(ExchangeRate).filter(
            ExchangeRate.currency_pair == CurrencyPair.EUR_TO_BRL
        ).first()
        
        if rate_record:
            rate_record.rate = rates.eur_to_brl
            rate_record.updated_by = rates.updated_by
        else:
            rate_record = ExchangeRate(
                currency_pair=CurrencyPair.EUR_TO_BRL,
                rate=rates.eur_to_brl,
                updated_by=rates.updated_by
            )
            db.add(rate_record)
        updated_rates.append("EUR_TO_BRL")
    
    if not updated_rates:
        raise HTTPException(status_code=400, detail="No rates provided for update")
    
    db.commit()
    
    return {
        "message": f"Successfully updated {len(updated_rates)} exchange rates",
        "updated_pairs": updated_rates,
        "timestamp": db.query(ExchangeRate).first().updated_at if updated_rates else None
    }

@router.get("/", response_model=List[ExchangeRateResponse])
def list_exchange_rates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """List all exchange rates"""
    return db.query(ExchangeRate).filter(ExchangeRate.is_active == True).all()

@router.post("/", response_model=ExchangeRateResponse)
def create_exchange_rate(
    rate: ExchangeRateCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Create new exchange rate"""
    # Check if rate already exists for this currency pair
    existing = db.query(ExchangeRate).filter(
        ExchangeRate.currency_pair == rate.currency_pair,
        ExchangeRate.is_active == True
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Active exchange rate already exists for {rate.currency_pair.value}"
        )
    
    db_rate = ExchangeRate(**rate.dict())
    db.add(db_rate)
    db.commit()
    db.refresh(db_rate)
    return db_rate

@router.put("/{rate_id}", response_model=ExchangeRateResponse)
def update_exchange_rate(
    rate_id: str, 
    rate_update: ExchangeRateUpdate, 
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Update specific exchange rate"""
    rate = db.query(ExchangeRate).filter(ExchangeRate.id == rate_id).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    
    update_data = rate_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rate, field, value)
    
    db.commit()
    db.refresh(rate)
    return rate

@router.get("/{currency_pair}")
def get_rate_by_pair(
    currency_pair: CurrencyPair, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get current rate for specific currency pair"""
    rate = db.query(ExchangeRate).filter(
        ExchangeRate.currency_pair == currency_pair,
        ExchangeRate.is_active == True
    ).first()
    
    if not rate:
        raise HTTPException(
            status_code=404, 
            detail=f"No active exchange rate found for {currency_pair.value}"
        )
    
    return {
        "currency_pair": currency_pair.value,
        "rate": rate.rate,
        "last_updated": rate.updated_at,
        "source": rate.source
    }