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

@router.put("/history/{rate_id}")
def edit_historical_rate(
    rate_id: str,
    rate_update: ExchangeRateUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Edit a historical exchange rate entry"""
    from ..validators import validate_uuid
    
    rate_uuid = validate_uuid(rate_id, "Rate ID")
    rate = db.query(ExchangeRate).filter(ExchangeRate.id == rate_uuid).first()
    
    if not rate:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    
    # Update fields
    update_data = rate_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rate, field, value)
    
    db.commit()
    db.refresh(rate)
    return rate

@router.delete("/history/{rate_id}")
def delete_historical_rate(
    rate_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Delete a historical exchange rate entry"""
    from ..validators import validate_uuid
    
    rate_uuid = validate_uuid(rate_id, "Rate ID")
    rate = db.query(ExchangeRate).filter(ExchangeRate.id == rate_uuid).first()
    
    if not rate:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    
    # Don't allow deletion of currently active rates
    if rate.is_active:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete active exchange rate. Deactivate it first."
        )
    
    db.delete(rate)
    db.commit()
    
    return {"message": "Exchange rate deleted successfully"}

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

@router.get("/sales-average/{currency_pair}")
def get_sales_average_rate(
    currency_pair: CurrencyPair,
    days_back: int = 7,  # Default to weekly average
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Get average exchange rate for sales calculations based on historical changes"""
    from datetime import datetime, timedelta
    from decimal import Decimal
    from sqlalchemy import func
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # Get all rates for this currency pair in the time period
    rates = db.query(ExchangeRate).filter(
        and_(
            ExchangeRate.currency_pair == currency_pair,
            ExchangeRate.created_at >= start_date,
            ExchangeRate.created_at <= end_date
        )
    ).order_by(ExchangeRate.created_at.asc()).all()
    
    if not rates:
        # If no rates in period, get the most recent rate
        latest_rate = db.query(ExchangeRate).filter(
            ExchangeRate.currency_pair == currency_pair
        ).order_by(desc(ExchangeRate.created_at)).first()
        
        if not latest_rate:
            raise HTTPException(
                status_code=404,
                detail=f"No rates found for {currency_pair.value}"
            )
        
        return {
            "currency_pair": currency_pair.value,
            "period_start": start_date.date().isoformat(),
            "period_end": end_date.date().isoformat(),
            "average_rate": float(latest_rate.rate),
            "sample_count": 1,
            "min_rate": float(latest_rate.rate),
            "max_rate": float(latest_rate.rate),
            "rates_in_period": 1,
            "recommendation": f"Use {float(latest_rate.rate)} (latest rate) for USD conversion in sales",
            "note": f"No rate changes in last {days_back} days, using most recent rate"
        }
    
    # Calculate weighted average based on time each rate was active
    total_weighted_rate = Decimal('0')
    total_time_weight = Decimal('0')
    
    for i, rate in enumerate(rates):
        # Calculate how long this rate was active
        if i < len(rates) - 1:
            # Not the last rate - active until next rate
            next_rate_time = rates[i + 1].created_at
            active_duration = (next_rate_time - rate.created_at).total_seconds()
        else:
            # Last rate - active until now
            active_duration = (end_date - rate.created_at).total_seconds()
        
        # Weight the rate by how long it was active
        weight = Decimal(str(active_duration))
        total_weighted_rate += rate.rate * weight
        total_time_weight += weight
    
    # Calculate final weighted average
    if total_time_weight > 0:
        weighted_average = total_weighted_rate / total_time_weight
    else:
        weighted_average = rates[-1].rate  # Fallback to latest rate
    
    # Calculate min, max
    rate_values = [rate.rate for rate in rates]
    min_rate = min(rate_values)
    max_rate = max(rate_values)
    
    return {
        "currency_pair": currency_pair.value,
        "period_start": start_date.date().isoformat(),
        "period_end": end_date.date().isoformat(),
        "average_rate": float(weighted_average),
        "sample_count": len(rates),
        "min_rate": float(min_rate),
        "max_rate": float(max_rate),
        "rates_in_period": len(rates),
        "recommendation": f"Use {float(weighted_average):.4f} for USD conversion in sales (weighted by time active)",
        "calculation_method": "Time-weighted average based on how long each rate was active",
        "rate_changes": [
            {
                "rate": float(rate.rate),
                "changed_at": rate.created_at.isoformat(),
                "changed_by": rate.updated_by,
                "source": rate.source
            }
            for rate in rates
        ]
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