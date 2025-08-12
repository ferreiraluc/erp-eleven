#!/usr/bin/env python3
"""
Create sample exchange rates data
"""

import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models.exchange_rate import ExchangeRate, CurrencyPair
from decimal import Decimal
from datetime import date, timedelta
import uuid

def create_sample_data():
    """Create sample exchange rate data"""
    db = SessionLocal()
    
    try:
        print("🔄 Creating sample exchange rate data...")
        
        # Clear existing active rates
        db.query(ExchangeRate).update({"is_active": False})
        
        # Clear all existing rates first to avoid unique constraint
        db.query(ExchangeRate).delete()
        db.commit()
        
        # Sample rates (working with current database schema)
        sample_rates = [
            # Current rates (active)
            {
                "currency_pair": CurrencyPair.USD_TO_BRL,
                "rate": Decimal("5.8500"),
                "source": "Manual Entry",
                "is_active": True,
                "notes": "Taxa atual USD para BRL",
                "updated_by": "System"
            },
            {
                "currency_pair": CurrencyPair.USD_TO_PYG,
                "rate": Decimal("7500.0000"),
                "source": "Manual Entry", 
                "is_active": True,
                "notes": "Taxa atual USD para Guarani",
                "updated_by": "System"
            },
            {
                "currency_pair": CurrencyPair.EUR_TO_BRL,
                "rate": Decimal("6.2000"),
                "source": "Manual Entry",
                "is_active": True,
                "notes": "Taxa atual EUR para BRL",
                "updated_by": "System"
            },
            {
                "currency_pair": CurrencyPair.EUR_TO_PYG,
                "rate": Decimal("8200.0000"),
                "source": "Manual Entry",
                "is_active": True,
                "notes": "Taxa atual EUR para Guarani",
                "updated_by": "System"
            }
        ]
        
        # Insert sample data
        for rate_data in sample_rates:
            rate = ExchangeRate(**rate_data)
            db.add(rate)
        
        db.commit()
        print("✅ Sample exchange rate data created successfully!")
        
        # Show created data
        current_rates = db.query(ExchangeRate).filter(ExchangeRate.is_active == True).all()
        print(f"\n📊 Current active rates ({len(current_rates)}):")
        for rate in current_rates:
            print(f"   {rate.currency_pair.value}: {rate.rate} (Source: {rate.source})")
        
        historical_count = db.query(ExchangeRate).filter(ExchangeRate.is_active == False).count()
        print(f"\n📚 Historical rates: {historical_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    print("💱 Creating Sample Exchange Rate Data")
    print("=" * 40)
    
    success = create_sample_data()
    
    if success:
        print("\n🎉 Sample data created! You can now test the exchange rate system.")
    else:
        print("\n❌ Failed to create sample data. Check database connection.")