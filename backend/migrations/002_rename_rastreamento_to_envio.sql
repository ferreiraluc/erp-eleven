-- Migration: Renomear tabela rastreamentos para envios e adicionar campos
-- Data: 2025-01-19

BEGIN;

-- Renomear tabela
ALTER TABLE rastreamentos RENAME TO envios;

-- Renomear enum type
ALTER TYPE rastreamento_status RENAME TO envio_status;

-- Adicionar novos campos
ALTER TABLE envios 
    ADD COLUMN cliente_nome VARCHAR(200),
    ADD COLUMN observacoes TEXT;

-- Atualizar relacionamentos se necessário
-- (Os relacionamentos já devem funcionar com o novo nome da tabela)

-- Atualizar índices se necessário
-- Recriar índice único com novo nome se existir
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_rastreamentos_codigo_rastreio') THEN
        DROP INDEX ix_rastreamentos_codigo_rastreio;
        CREATE INDEX ix_envios_codigo_rastreio ON envios(codigo_rastreio);
    END IF;
END $$;

COMMIT;