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
    CurrentRatesResponse,
    WeeklyAverageResponse,
    RateHistoryResponse
)
from ...dependencies import get_current_active_user, require_role
from datetime import date, timedelta
from sqlalchemy import and_, desc

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
    """Quick update multiple exchange rates - perfect for dashboard/header editing"""
    updated_rates = []
    
    # Helper function to update or create rate
    def update_rate(currency_pair: CurrencyPair, new_rate):
        if new_rate is None:
            return
            
        # Try to find existing active rate
        existing_rate = db.query(ExchangeRate).filter(
            ExchangeRate.currency_pair == currency_pair,
            ExchangeRate.is_active == True
        ).first()
        
        if existing_rate:
            # Update existing rate
            existing_rate.rate = new_rate
            existing_rate.source = rates.source
            existing_rate.notes = rates.notes
            existing_rate.updated_by = rates.updated_by
        else:
            # Create new rate if none exists
            new_record = ExchangeRate(
                currency_pair=currency_pair,
                rate=new_rate,
                source=rates.source,
                notes=rates.notes,
                updated_by=rates.updated_by,
                is_active=True
            )
            db.add(new_record)
        
        updated_rates.append({
            "pair": currency_pair.value,
            "rate": float(new_rate),
            "source": rates.source
        })
    
    # Update all provided rates
    update_rate(CurrencyPair.USD_TO_PYG, rates.usd_to_pyg)
    update_rate(CurrencyPair.USD_TO_BRL, rates.usd_to_brl)
    update_rate(CurrencyPair.EUR_TO_PYG, rates.eur_to_pyg)
    update_rate(CurrencyPair.EUR_TO_BRL, rates.eur_to_brl)
    
    if not updated_rates:
        raise HTTPException(status_code=400, detail="No rates provided for update")
    
    db.commit()
    
    return {
        "message": f"Successfully updated {len(updated_rates)} exchange rates",
        "updated_rates": updated_rates,
        "timestamp": date.today().isoformat(),
        "updated_by": rates.updated_by
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

@router.get("/history")
def get_exchange_rates_history(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get exchange rate history (simplified version)"""
    
    # Get current rates
    current_rates = get_current_rates(db, current_user)
    
    # Get all historical rates (simplified)
    all_rates = db.query(ExchangeRate).order_by(desc(ExchangeRate.created_at)).all()
    
    return {
        "current_rates": current_rates,
        "historical_rates": [
            {
                "id": str(rate.id),
                "currency_pair": rate.currency_pair.value,
                "rate": float(rate.rate),
                "source": rate.source,
                "is_active": rate.is_active,
                "created_at": rate.created_at.isoformat() if rate.created_at else None,
                "updated_by": rate.updated_by
            }
            for rate in all_rates
        ],
        "total_records": len(all_rates)
    }

@router.get("/weekly-average/{currency_pair}")
def get_weekly_average(
    currency_pair: CurrencyPair,
    weeks_back: int = 0,  # 0 = current week, 1 = last week, etc.
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get weekly average for specific currency pair (simplified)"""
    
    # For now, just return the current rate as "average" since we don't have rate_date yet
    current_rate = db.query(ExchangeRate).filter(
        and_(
            ExchangeRate.currency_pair == currency_pair,
            ExchangeRate.is_active == True
        )
    ).first()
    
    if not current_rate:
        raise HTTPException(
            status_code=404,
            detail=f"No current rate found for {currency_pair.value}"
        )
    
    today = date.today()
    monday = today - timedelta(days=today.weekday() + (7 * weeks_back))
    sunday = monday + timedelta(days=6)
    
    return {
        "currency_pair": currency_pair.value,
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "average_rate": float(current_rate.rate),
        "sample_count": 1,
        "min_rate": float(current_rate.rate),
        "max_rate": float(current_rate.rate),
        "note": "Simplified version - showing current rate as average until rate_date field is added"
    }

@router.get("/sales-week-average/{currency_pair}")
def get_sales_week_average(
    currency_pair: CurrencyPair,
    saturday_date: date,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get weekly average for sales period (Sunday to Saturday) - simplified version"""
    
    # Calculate the Sunday that starts this sales week
    if saturday_date.weekday() != 5:
        raise HTTPException(
            status_code=400,
            detail="Please provide a Saturday date for sales week calculation"
        )
    
    sunday_start = saturday_date - timedelta(days=6)
    
    # For now, just return the current rate as "average" since we don't have rate_date yet
    current_rate = db.query(ExchangeRate).filter(
        and_(
            ExchangeRate.currency_pair == currency_pair,
            ExchangeRate.is_active == True
        )
    ).first()
    
    if not current_rate:
        raise HTTPException(
            status_code=404,
            detail=f"No current rate found for {currency_pair.value}"
        )
    
    return {
        "currency_pair": currency_pair.value,
        "sales_week_start": sunday_start.isoformat(),
        "sales_week_end": saturday_date.isoformat(),
        "average_rate": float(current_rate.rate),
        "sample_count": 1,
        "min_rate": float(current_rate.rate),
        "max_rate": float(current_rate.rate),
        "recommendation": f"Use {float(current_rate.rate)} as rate for sales closing on {saturday_date}",
        "note": "Simplified version - showing current rate until rate_date field is added"
    }

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