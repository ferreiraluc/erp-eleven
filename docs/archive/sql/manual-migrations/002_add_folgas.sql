-- =============================================
-- MIGRAÇÃO 002: Adicionar tabela folgas e
-- coluna cor_calendario em vendedores
-- Executar no Render DB via psql ou dashboard
-- =============================================

-- 1) Adicionar cor_calendario em vendedores (idempotente)
ALTER TABLE vendedores ADD COLUMN IF NOT EXISTS cor_calendario VARCHAR(7) DEFAULT '#3B82F6';

-- 2) Criar enum tipo_folga (idempotente)
DO $$ BEGIN
    CREATE TYPE tipo_folga AS ENUM ('FOLGA', 'FERIAS', 'LICENCA', 'FALTA', 'MEIO_PERIODO');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 3) Criar tabela folgas (idempotente)
CREATE TABLE IF NOT EXISTS folgas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendedor_id UUID NOT NULL REFERENCES vendedores(id),
    data DATE NOT NULL,
    tipo tipo_folga DEFAULT 'FOLGA',
    periodo VARCHAR(20) DEFAULT 'COMPLETO',
    motivo TEXT,
    aprovado BOOLEAN DEFAULT FALSE,
    aprovado_por UUID REFERENCES usuarios(id),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4) Índices (idempotente)
CREATE INDEX IF NOT EXISTS idx_folgas_vendedor ON folgas(vendedor_id);
CREATE INDEX IF NOT EXISTS idx_folgas_data ON folgas(data);

-- 5) Trigger updated_at para folgas (idempotente)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_folgas_updated_at') THEN
        EXECUTE 'CREATE TRIGGER update_folgas_updated_at BEFORE UPDATE ON folgas FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()';
    END IF;
END $$;
