# DEPLOY INSTRUCTIONS - RENDER

## Como executar os scripts SQL no Render

### 1. Acesse seu banco de dados no Render CLI:
```bash
# No terminal do seu computador:
render psql [DATABASE_NAME]
```

### 2. Execute o script completo:
```sql
-- Cole todo o conteúdo do arquivo render_deploy_scripts.sql
-- Ou execute linha por linha se preferir
```

### 3. Comandos individuais (se preferir executar separadamente):

```sql
-- Criar enum
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'currencypair') THEN
        CREATE TYPE currencypair AS ENUM ('USD_TO_PYG', 'USD_TO_BRL', 'EUR_TO_PYG', 'EUR_TO_BRL');
    END IF;
END $$;

-- Criar tabela
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

-- Criar índices
CREATE INDEX IF NOT EXISTS idx_exchange_rates_currency_pair ON exchange_rates(currency_pair);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_is_active ON exchange_rates(is_active);
CREATE INDEX IF NOT EXISTS idx_exchange_rates_created_at ON exchange_rates(created_at);

-- Inserir dados iniciais
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
```

### 4. Verificar se funcionou:
```sql
SELECT 'Tabela exchange_rates criada com sucesso!' as status;
SELECT COUNT(*) as total_rates FROM exchange_rates;
SELECT currency_pair, rate, is_active FROM exchange_rates WHERE is_active = true ORDER BY currency_pair;
```

### 5. Testar endpoints após deploy:
- GET /api/exchange-rates/current
- POST /api/exchange-rates/quick-update (requer autenticação ADMIN)

## Problemas Comuns:

### Se der erro de enum já existir:
```sql
DROP TYPE IF EXISTS currencypair CASCADE;
CREATE TYPE currencypair AS ENUM ('USD_TO_PYG', 'USD_TO_BRL', 'EUR_TO_PYG', 'EUR_TO_BRL');
```

### Se der erro de constraint unique:
```sql
ALTER TABLE exchange_rates DROP CONSTRAINT IF EXISTS exchange_rates_currency_pair_key;
```