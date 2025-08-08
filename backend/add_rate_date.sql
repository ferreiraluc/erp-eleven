-- Migration to add rate_date column to exchange_rates table
-- Execute this SQL script in your PostgreSQL database

-- Add the rate_date column
ALTER TABLE exchange_rates 
ADD COLUMN IF NOT EXISTS rate_date DATE DEFAULT CURRENT_DATE;

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_exchange_rates_rate_date ON exchange_rates(rate_date);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_active ON exchange_rates(is_active);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_pair_active ON exchange_rates(currency_pair, is_active);

-- Remove unique constraint on currency_pair to allow history
ALTER TABLE exchange_rates 
DROP CONSTRAINT IF EXISTS exchange_rates_currency_pair_key;

-- Update existing records to have rate_date = created_at date
UPDATE exchange_rates 
SET rate_date = DATE(created_at) 
WHERE rate_date IS NULL;

-- Set NOT NULL constraint after updating existing records
ALTER TABLE exchange_rates 
ALTER COLUMN rate_date SET NOT NULL;

COMMIT;