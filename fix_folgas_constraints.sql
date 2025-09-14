-- =============================================
-- SCRIPT PARA CORRIGIR CONSTRAINT FOLGAS
-- Remove dados órfãos antes de aplicar FK constraint
-- =============================================

-- 1. Primeiro, verificar quais folgas têm vendedor_id inválido
SELECT 'Dados órfãos encontrados:' as info;
SELECT 
    f.id as folga_id,
    f.vendedor_id,
    f.data,
    f.tipo
FROM folgas f
LEFT JOIN vendedores v ON f.vendedor_id = v.id
WHERE v.id IS NULL;

-- 2. Contar total de folgas órfãs
SELECT 'Total de folgas órfãs:' as info, COUNT(*) as total
FROM folgas f
LEFT JOIN vendedores v ON f.vendedor_id = v.id
WHERE v.id IS NULL;

-- 3. Remover folgas órfãs (soft delete primeiro)
UPDATE folgas 
SET ativo = false,
    updated_at = CURRENT_TIMESTAMP
WHERE vendedor_id NOT IN (
    SELECT id FROM vendedores WHERE ativo = true
);

-- 4. Verificar se ainda existem folgas órfãs ativas
SELECT 'Folgas órfãs ativas restantes:' as info, COUNT(*) as total
FROM folgas f
LEFT JOIN vendedores v ON f.vendedor_id = v.id
WHERE v.id IS NULL AND f.ativo = true;

-- 5. Se necessário, deletar fisicamente as folgas órfãs inativas
-- (apenas se não houver mais referências ativas)
DELETE FROM folgas 
WHERE vendedor_id NOT IN (
    SELECT id FROM vendedores
) AND ativo = false;

-- 6. Verificar estado final
SELECT 'Folgas restantes por vendedor:' as info;
SELECT 
    v.nome,
    v.ativo as vendedor_ativo,
    COUNT(f.id) as total_folgas,
    COUNT(CASE WHEN f.ativo THEN 1 END) as folgas_ativas
FROM vendedores v
LEFT JOIN folgas f ON v.id = f.vendedor_id
WHERE v.ativo = true
GROUP BY v.id, v.nome, v.ativo
ORDER BY v.nome;

-- 7. Agora tentar aplicar a constraint FK novamente
DO $$
BEGIN
  -- Verificar se constraint já existe
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid
    WHERE t.relname = 'folgas' AND c.contype = 'f' AND c.conname = 'folgas_vendedor_id_fkey'
  ) THEN
    -- Aplicar constraint FK
    ALTER TABLE ONLY public.folgas 
    ADD CONSTRAINT folgas_vendedor_id_fkey 
    FOREIGN KEY (vendedor_id) REFERENCES public.vendedores(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Constraint folgas_vendedor_id_fkey criada com sucesso!';
  ELSE
    RAISE NOTICE 'Constraint folgas_vendedor_id_fkey já existe';
  END IF;
EXCEPTION 
  WHEN foreign_key_violation THEN
    RAISE EXCEPTION 'Ainda existem dados órfãos. Execute as consultas de verificação acima.';
  WHEN OTHERS THEN
    RAISE EXCEPTION 'Erro ao criar constraint: %', SQLERRM;
END $$;

SELECT 'Script de correção de folgas concluído!' as status;