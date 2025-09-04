-- Criar enum para tipos de folga se não existir
DO $$ BEGIN
    CREATE TYPE tipofolga AS ENUM ('FOLGA', 'FERIAS', 'LICENCA', 'FALTA', 'MEIO_PERIODO');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Criar tabela folgas se não existir
CREATE TABLE IF NOT EXISTS folgas (
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

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_folgas_vendedor_data ON folgas(vendedor_id, data);
CREATE INDEX IF NOT EXISTS idx_folgas_data ON folgas(data);
CREATE INDEX IF NOT EXISTS idx_folgas_ativo ON folgas(ativo);

-- Inserir algumas folgas de exemplo para os vendedores existentes
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
  AND NOT EXISTS (
    SELECT 1 FROM folgas f WHERE f.vendedor_id = v.id
  )
ORDER BY random()
LIMIT 15;

-- Verificar resultado
SELECT 'Total de vendedores:' as info, COUNT(*) as count FROM vendedores WHERE ativo = true;
SELECT 'Total de folgas:' as info, COUNT(*) as count FROM folgas WHERE ativo = true;

SELECT v.nome, v.cor_calendario, COUNT(f.id) as total_folgas
FROM vendedores v
LEFT JOIN folgas f ON v.id = f.vendedor_id AND f.ativo = true
WHERE v.ativo = true
GROUP BY v.id, v.nome, v.cor_calendario
ORDER BY v.nome;

COMMIT;