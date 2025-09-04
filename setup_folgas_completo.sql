-- Script completo para configurar sistema de folgas

-- 1. PRIMEIRO: Adicionar cor_calendario na tabela vendedores
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vendedores' 
          AND column_name = 'cor_calendario'
          AND table_schema = 'public'
    ) THEN
        ALTER TABLE vendedores ADD COLUMN cor_calendario VARCHAR(7) DEFAULT '#3B82F6';
        RAISE NOTICE 'Coluna cor_calendario adicionada à tabela vendedores';
    ELSE
        RAISE NOTICE 'Coluna cor_calendario já existe na tabela vendedores';
    END IF;
END $$;

-- 2. Atualizar vendedores com cores diferentes
WITH vendedores_numerados AS (
    SELECT 
        id,
        row_number() OVER (ORDER BY nome) as rn
    FROM vendedores 
    WHERE ativo = true
)
UPDATE vendedores 
SET cor_calendario = (
    CASE 
        WHEN vn.rn % 5 = 1 THEN '#3B82F6'  -- Azul
        WHEN vn.rn % 5 = 2 THEN '#EF4444'  -- Vermelho
        WHEN vn.rn % 5 = 3 THEN '#10B981'  -- Verde
        WHEN vn.rn % 5 = 4 THEN '#F59E0B'  -- Laranja
        ELSE '#8B5CF6'  -- Roxo
    END
)
FROM vendedores_numerados vn
WHERE vendedores.id = vn.id;

-- 3. Verificar vendedores
SELECT 'Vendedores com cores:' as info;
SELECT nome, cor_calendario FROM vendedores WHERE ativo = true ORDER BY nome;

-- 4. Dropar tabela folgas se existir
DROP TABLE IF EXISTS folgas CASCADE;

-- 5. Garantir que o enum existe
DO $$ BEGIN
    CREATE TYPE tipofolga AS ENUM ('FOLGA', 'FERIAS', 'LICENCA', 'FALTA', 'MEIO_PERIODO');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 6. Criar tabela folgas
CREATE TABLE folgas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendedor_id UUID NOT NULL REFERENCES vendedores(id) ON DELETE CASCADE,
    data DATE NOT NULL,
    tipo tipofolga DEFAULT 'FOLGA',
    periodo VARCHAR(20) DEFAULT 'COMPLETO',
    motivo TEXT,
    aprovado BOOLEAN DEFAULT FALSE,
    aprovado_por UUID REFERENCES usuarios(id),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(vendedor_id, data)
);

-- 7. Criar índices
CREATE INDEX idx_folgas_vendedor_data ON folgas(vendedor_id, data);
CREATE INDEX idx_folgas_data ON folgas(data);
CREATE INDEX idx_folgas_ativo ON folgas(ativo) WHERE ativo = true;

-- 8. Inserir folgas de exemplo
INSERT INTO folgas (vendedor_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    v.id,
    CURRENT_DATE + (generate_series(-10, 10)),
    (ARRAY['FOLGA', 'FERIAS', 'LICENCA'])[floor(random() * 3 + 1)]::tipofolga,
    (ARRAY['COMPLETO', 'MANHA', 'TARDE'])[floor(random() * 3 + 1)],
    'Folga de exemplo para ' || v.nome,
    random() > 0.2,
    true
FROM vendedores v
WHERE v.ativo = true
ORDER BY random()
LIMIT 30
ON CONFLICT (vendedor_id, data) DO NOTHING;

-- 9. Resultados finais
SELECT 'SISTEMA DE FOLGAS CONFIGURADO!' as status;

SELECT 'Vendedores cadastrados:' as info;
SELECT COUNT(*) as total FROM vendedores WHERE ativo = true;

SELECT 'Folgas criadas:' as info;
SELECT COUNT(*) as total FROM folgas WHERE ativo = true;

SELECT 'Resumo por vendedor:' as info;
SELECT 
    v.nome,
    v.cor_calendario,
    COUNT(f.id) as total_folgas,
    COUNT(CASE WHEN f.aprovado THEN 1 END) as aprovadas,
    COUNT(CASE WHEN NOT f.aprovado THEN 1 END) as pendentes
FROM vendedores v
LEFT JOIN folgas f ON v.id = f.vendedor_id AND f.ativo = true
WHERE v.ativo = true
GROUP BY v.id, v.nome, v.cor_calendario
ORDER BY total_folgas DESC;

SELECT 'Folgas dos próximos dias:' as info;
SELECT 
    v.nome as vendedor,
    v.cor_calendario as cor,
    f.data,
    f.tipo,
    f.periodo,
    CASE WHEN f.aprovado THEN 'APROVADA' ELSE 'PENDENTE' END as status
FROM folgas f
JOIN vendedores v ON f.vendedor_id = v.id
WHERE f.ativo = true 
  AND f.data >= CURRENT_DATE
  AND f.data <= CURRENT_DATE + 15
ORDER BY f.data, v.nome;

COMMIT;