-- =============================================
-- SCRIPT DE DEBUG PARA FOLGAS EM PRODUÇÃO
-- Verifica se tabela existe e estrutura está correta
-- =============================================

-- 1. Verificar se tabela folgas existe
SELECT 
    'Tabela folgas existe:' as info,
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'folgas') 
        THEN 'SIM' 
        ELSE 'NÃO' 
    END as resultado;

-- 2. Verificar estrutura da tabela folgas
SELECT 
    'Colunas da tabela folgas:' as info;
    
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'folgas' 
ORDER BY ordinal_position;

-- 3. Verificar se enum tipofolga existe
SELECT 
    'Enum tipofolga existe:' as info,
    CASE 
        WHEN EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tipofolga') 
        THEN 'SIM' 
        ELSE 'NÃO' 
    END as resultado;

-- 4. Verificar valores do enum tipofolga
SELECT 
    'Valores do enum tipofolga:' as info;
    
SELECT 
    e.enumlabel as valores_enum
FROM pg_enum e
JOIN pg_type t ON e.enumtypid = t.oid
WHERE t.typname = 'tipofolga'
ORDER BY e.enumsortorder;

-- 5. Verificar constraints da tabela folgas
SELECT 
    'Constraints da tabela folgas:' as info;
    
SELECT 
    c.conname as constraint_name,
    c.contype as constraint_type,
    pg_get_constraintdef(c.oid) as constraint_definition
FROM pg_constraint c
JOIN pg_class t ON c.conrelid = t.oid
WHERE t.relname = 'folgas';

-- 6. Verificar índices da tabela folgas
SELECT 
    'Índices da tabela folgas:' as info;
    
SELECT 
    i.relname as index_name,
    pg_get_indexdef(i.oid) as index_definition
FROM pg_class t
JOIN pg_index ix ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
WHERE t.relname = 'folgas';

-- 7. Contar registros na tabela folgas
SELECT 
    'Total de registros em folgas:' as info,
    COUNT(*) as total
FROM folgas;

-- 8. Contar folgas ativas
SELECT 
    'Folgas ativas:' as info,
    COUNT(*) as total
FROM folgas 
WHERE ativo = true;

-- 9. Verificar tabela vendedores
SELECT 
    'Total de vendedores ativos:' as info,
    COUNT(*) as total
FROM vendedores 
WHERE ativo = true;

-- 10. Verificar se vendedores têm cor_calendario
SELECT 
    'Vendedores com cor_calendario:' as info;
    
SELECT 
    nome,
    cor_calendario,
    ativo
FROM vendedores 
WHERE ativo = true
ORDER BY nome
LIMIT 5;

-- 11. Testar query do endpoint calendario
SELECT 
    'Teste query endpoint calendario (Janeiro 2025):' as info;
    
SELECT 
    f.id,
    f.vendedor_id,
    f.data,
    f.tipo,
    f.periodo,
    f.motivo,
    f.aprovado,
    v.nome as vendedor_nome,
    v.cor_calendario as vendedor_cor
FROM folgas f
JOIN vendedores v ON f.vendedor_id = v.id
WHERE f.ativo = true 
  AND v.ativo = true
  AND EXTRACT('year' FROM f.data) = 2025
  AND EXTRACT('month' FROM f.data) = 1
ORDER BY f.data;

-- 12. Verificar owner da tabela
SELECT 
    'Owner da tabela folgas:' as info,
    pg_catalog.pg_get_userbyid(c.relowner) as owner
FROM pg_catalog.pg_class c
WHERE c.relname = 'folgas';

SELECT 'Debug da tabela folgas concluído!' as status;