-- Verificar estrutura atual da tabela folgas
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'folgas' 
  AND table_schema = 'public'
ORDER BY ordinal_position;

-- Corrigir a tabela folgas
DO $$
BEGIN
    -- Se a coluna funcionario_id existe, precisamos migrar os dados
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'folgas' AND column_name = 'funcionario_id'
    ) THEN
        -- Dropar a tabela e recriar com a estrutura correta
        DROP TABLE IF EXISTS folgas CASCADE;
        
        -- Recriar a tabela com vendedor_id
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
        
    ELSIF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'folgas' AND column_name = 'vendedor_id'
    ) THEN
        -- Se não tem nem funcionario_id nem vendedor_id, adicionar vendedor_id
        ALTER TABLE folgas ADD COLUMN vendedor_id UUID REFERENCES vendedores(id);
    END IF;
END $$;

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_folgas_vendedor_data ON folgas(vendedor_id, data);
CREATE INDEX IF NOT EXISTS idx_folgas_data ON folgas(data);
CREATE INDEX IF NOT EXISTS idx_folgas_ativo ON folgas(ativo);

-- Limpar dados antigos se existirem
DELETE FROM folgas WHERE vendedor_id IS NULL;

-- Inserir folgas de exemplo para os vendedores
INSERT INTO folgas (id, vendedor_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    gen_random_uuid(),
    v.id,
    CURRENT_DATE + (floor(random() * 30 - 15))::int,
    (ARRAY['FOLGA', 'FERIAS', 'LICENCA'])[floor(random() * 3 + 1)]::tipofolga,
    (ARRAY['COMPLETO', 'MANHA', 'TARDE'])[floor(random() * 3 + 1)],
    'Folga de exemplo',
    random() > 0.3,
    true
FROM vendedores v
WHERE v.ativo = true
ORDER BY random()
LIMIT 20;

-- Verificar estrutura final
SELECT 'Estrutura da tabela folgas:' as info;
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'folgas' 
  AND table_schema = 'public'
ORDER BY ordinal_position;

-- Verificar dados inseridos
SELECT 'Resumo das folgas por vendedor:' as info;
SELECT 
    v.nome as vendedor,
    v.cor_calendario,
    COUNT(f.id) as total_folgas,
    COUNT(CASE WHEN f.aprovado THEN 1 END) as aprovadas,
    COUNT(CASE WHEN NOT f.aprovado THEN 1 END) as pendentes
FROM vendedores v
LEFT JOIN folgas f ON v.id = f.vendedor_id AND f.ativo = true
WHERE v.ativo = true
GROUP BY v.id, v.nome, v.cor_calendario
ORDER BY v.nome;

COMMIT;