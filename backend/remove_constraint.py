#!/usr/bin/env python3
"""
Remove unique constraint from currency_pair column
"""

import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from sqlalchemy import text

def remove_constraint():
    """Remove unique constraint from currency_pair"""
    db = SessionLocal()
    
    try:
        print("🔄 Removing unique constraint from currency_pair...")
        
        # Remove unique constraint
        db.execute(text("ALTER TABLE exchange_rates DROP CONSTRAINT IF EXISTS exchange_rates_currency_pair_key;"))
        db.commit()
        
        print("✅ Unique constraint removed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error removing constraint: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    print("🗑️ Removing Unique Constraint")
    print("=" * 30)
    
    success = remove_constraint()
    
    if success:
        print("\n🎉 Constraint removed! Quick update should work now.")
    else:
        print("\n❌ Failed to remove constraint.")