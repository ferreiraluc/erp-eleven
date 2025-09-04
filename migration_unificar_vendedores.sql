-- Migration para unificar vendedores e funcionários
-- Execute no pgAdmin4

-- 1. Adicionar coluna cor_calendario na tabela vendedores
ALTER TABLE vendedores ADD COLUMN IF NOT EXISTS cor_calendario VARCHAR(7) DEFAULT '#3B82F6';

-- 2. Dropar tabelas e suas dependências
DROP TABLE IF EXISTS folgas;
DROP TABLE IF EXISTS pontos CASCADE;
DROP TABLE IF EXISTS funcionarios CASCADE;

-- 3. Recriar tabela folgas referenciando vendedores
CREATE TABLE folgas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendedor_id UUID NOT NULL REFERENCES vendedores(id),
    data DATE NOT NULL,
    tipo tipofolga DEFAULT 'FOLGA',
    periodo VARCHAR(20) DEFAULT 'COMPLETO',
    motivo TEXT,
    aprovado BOOLEAN DEFAULT FALSE,
    aprovado_por UUID REFERENCES usuarios(id),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_folgas_vendedor_data ON folgas(vendedor_id, data);
CREATE INDEX IF NOT EXISTS idx_folgas_data ON folgas(data);
CREATE INDEX IF NOT EXISTS idx_folgas_ativo ON folgas(ativo);

-- 5. Atualizar vendedores existentes com cores
UPDATE vendedores SET cor_calendario = (
    CASE 
        WHEN row_number() OVER (ORDER BY nome) % 5 = 1 THEN '#3B82F6'  -- Azul
        WHEN row_number() OVER (ORDER BY nome) % 5 = 2 THEN '#EF4444'  -- Vermelho
        WHEN row_number() OVER (ORDER BY nome) % 5 = 3 THEN '#10B981'  -- Verde
        WHEN row_number() OVER (ORDER BY nome) % 5 = 4 THEN '#F59E0B'  -- Laranja
        ELSE '#8B5CF6'  -- Roxo
    END
) WHERE cor_calendario = '#3B82F6' OR cor_calendario IS NULL;

-- 6. Inserir folgas de exemplo para os vendedores existentes
INSERT INTO folgas (id, vendedor_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    gen_random_uuid(),
    v.id,
    CURRENT_DATE + (floor(random() * 20 - 10))::int,
    (ARRAY['FOLGA', 'FERIAS', 'LICENCA'])[floor(random() * 3 + 1)]::tipofolga,
    'COMPLETO',
    'Folga de exemplo',
    random() > 0.3,
    true
FROM vendedores v
WHERE v.ativo = true
ORDER BY random()
LIMIT 10;

-- 7. Verificar resultado
SELECT 'Vendedores com cores:' as info;
SELECT nome, cor_calendario FROM vendedores WHERE ativo = true;

SELECT 'Folgas criadas:' as info;
SELECT COUNT(*) as total_folgas FROM folgas WHERE ativo = true;

COMMIT;