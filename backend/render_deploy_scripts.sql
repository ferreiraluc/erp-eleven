-- =========================================
-- RENDER DEPLOYMENT SCRIPTS
-- Execute estes comandos no Render CLI psql
-- =========================================

-- 1. Criar enum para tipos de moeda (se não existir)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'currencypair') THEN
        CREATE TYPE currencypair AS ENUM ('USD_TO_PYG', 'USD_TO_BRL', 'EUR_TO_PYG', 'EUR_TO_BRL');
    END IF;
END $$;

-- 2. Criar tabela de exchange_rates (se não existir)
CREATE TABLE IF NOT EXISTS exchange_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    currency_pair currencypair NOT NULL,
    rate DECIMAL(12,4) NOT NULL,
    source VARCHAR(100) DEFAULT 'Manual Entry',
    is_active BOOLEAN DEFAULT true,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100)
);

-- 3. Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_exchange_rates_currency_pair ON exchange_rates(currency_pair);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_is_active ON exchange_rates(is_active);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_created_at ON exchange_rates(created_at);

-- 4. Criar trigger para updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER IF NOT EXISTS update_exchange_rates_updated_at 
    BEFORE UPDATE ON exchange_rates 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 5. Remover constraint unique se existir (para permitir histórico)
ALTER TABLE exchange_rates DROP CONSTRAINT IF EXISTS exchange_rates_currency_pair_key;

-- 6. Inserir dados iniciais (apenas se não existirem taxas ativas)
INSERT INTO exchange_rates (currency_pair, rate, source, is_active, notes, updated_by)
SELECT 'USD_TO_BRL', 5.8500, 'Configuração Inicial', true, 'Taxa inicial USD para BRL', 'Sistema'
WHERE NOT EXISTS (SELECT 1 FROM exchange_rates WHERE currency_pair = 'USD_TO_BRL' AND is_active = true);

INSERT INTO exchange_rates (currency_pair, rate, source, is_active, notes, updated_by)
SELECT 'USD_TO_PYG', 7500.0000, 'Configuração Inicial', true, 'Taxa inicial USD para Guarani', 'Sistema'
WHERE NOT EXISTS (SELECT 1 FROM exchange_rates WHERE currency_pair = 'USD_TO_PYG' AND is_active = true);

INSERT INTO exchange_rates (currency_pair, rate, source, is_active, notes, updated_by)
SELECT 'EUR_TO_BRL', 6.2000, 'Configuração Inicial', true, 'Taxa inicial EUR para BRL', 'Sistema'
WHERE NOT EXISTS (SELECT 1 FROM exchange_rates WHERE currency_pair = 'EUR_TO_BRL' AND is_active = true);

INSERT INTO exchange_rates (currency_pair, rate, source, is_active, notes, updated_by)
SELECT 'EUR_TO_PYG', 8200.0000, 'Configuração Inicial', true, 'Taxa inicial EUR para Guarani', 'Sistema'
WHERE NOT EXISTS (SELECT 1 FROM exchange_rates WHERE currency_pair = 'EUR_TO_PYG' AND is_active = true);

-- 7. Verificar se tudo foi criado corretamente
SELECT 'Tabela exchange_rates criada com sucesso!' as status;
SELECT COUNT(*) as total_rates FROM exchange_rates;
SELECT currency_pair, rate, is_active FROM exchange_rates WHERE is_active = true ORDER BY currency_pair;