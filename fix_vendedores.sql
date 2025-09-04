-- Verificar se a coluna cor_calendario existe
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'vendedores' 
  AND table_schema = 'public';

-- Adicionar a coluna cor_calendario se não existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vendedores' 
          AND column_name = 'cor_calendario'
          AND table_schema = 'public'
    ) THEN
        ALTER TABLE vendedores ADD COLUMN cor_calendario VARCHAR(7) DEFAULT '#3B82F6';
    END IF;
END $$;

-- Atualizar vendedores existentes com cores diferentes usando CTE
WITH vendedores_numerados AS (
    SELECT 
        id,
        row_number() OVER (ORDER BY nome) as rn
    FROM vendedores 
    WHERE ativo = true AND (cor_calendario IS NULL OR cor_calendario = '#3B82F6')
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

-- Verificar resultado
SELECT nome, cor_calendario FROM vendedores WHERE ativo = true;

COMMIT;