-- =============================================
-- MIGRAÇÃO 003: Substituir unique constraint de folgas
-- por partial unique index (apenas registros ativos)
--
-- Problema: UNIQUE(vendedor_id, data) bloqueava
-- reinserção após soft-delete (ativo=False)
--
-- Executar no Render DB via psql
-- =============================================

-- 1) Remover a constraint existente
ALTER TABLE folgas DROP CONSTRAINT IF EXISTS folgas_vendedor_id_data_key;

-- 2) Criar partial unique index (só aplica quando ativo=TRUE)
CREATE UNIQUE INDEX IF NOT EXISTS idx_folgas_vendedor_data_ativo
    ON folgas(vendedor_id, data)
    WHERE ativo = TRUE;
