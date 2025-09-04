-- Forçar recriação da tabela folgas com estrutura correta

-- 1. Dropar a tabela folgas existente
DROP TABLE IF EXISTS folgas CASCADE;

-- 2. Garantir que o enum existe
DO $$ BEGIN
    CREATE TYPE tipofolga AS ENUM ('FOLGA', 'FERIAS', 'LICENCA', 'FALTA', 'MEIO_PERIODO');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 3. Recriar a tabela folgas com vendedor_id
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
    
    -- Constraint para evitar folgas duplicadas no mesmo dia
    UNIQUE(vendedor_id, data)
);

-- 4. Criar índices
CREATE INDEX idx_folgas_vendedor_data ON folgas(vendedor_id, data);
CREATE INDEX idx_folgas_data ON folgas(data);
CREATE INDEX idx_folgas_ativo ON folgas(ativo WHERE ativo = true);
CREATE INDEX idx_folgas_aprovado ON folgas(aprovado);

-- 5. Inserir folgas de exemplo para os vendedores
INSERT INTO folgas (vendedor_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    v.id,
    CURRENT_DATE + (generate_series(1, 5) - 3), -- 5 dias para cada vendedor
    (ARRAY['FOLGA', 'FERIAS', 'LICENCA'])[floor(random() * 3 + 1)]::tipofolga,
    (ARRAY['COMPLETO', 'MANHA', 'TARDE'])[floor(random() * 3 + 1)],
    'Folga de exemplo - ' || v.nome,
    random() > 0.2, -- 80% aprovadas
    true
FROM vendedores v
WHERE v.ativo = true;

-- 6. Inserir mais algumas folgas espalhadas no mês
INSERT INTO folgas (vendedor_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    v.id,
    CURRENT_DATE + (floor(random() * 30 - 15))::int,
    (ARRAY['FOLGA', 'FERIAS'])[floor(random() * 2 + 1)]::tipofolga,
    'COMPLETO',
    'Folga adicional',
    random() > 0.3,
    true
FROM vendedores v
WHERE v.ativo = true
ORDER BY random()
LIMIT 10
ON CONFLICT (vendedor_id, data) DO NOTHING;

-- 7. Verificar resultado
SELECT 'Tabela folgas recriada com sucesso!' as status;

SELECT 'Estrutura da tabela:' as info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'folgas' 
  AND table_schema = 'public'
ORDER BY ordinal_position;

SELECT 'Dados inseridos:' as info;
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

-- Mostrar algumas folgas como exemplo
SELECT 'Exemplos de folgas:' as info;
SELECT 
    v.nome as vendedor,
    f.data,
    f.tipo,
    f.periodo,
    f.aprovado,
    f.motivo
FROM folgas f
JOIN vendedores v ON f.vendedor_id = v.id
WHERE f.ativo = true
ORDER BY f.data DESC
LIMIT 10;

COMMIT;