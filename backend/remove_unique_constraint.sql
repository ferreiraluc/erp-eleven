-- Remove unique constraint from currency_pair to allow historical rates
ALTER TABLE exchange_rates DROP CONSTRAINT IF EXISTS exchange_rates_currency_pair_key;