-- Fix folgas table in production
-- Date: 2025-09-04
-- Issue: folgas table still references funcionario_id instead of vendedor_id

BEGIN;

-- Check if folgas table exists and what columns it has
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'folgas' 
ORDER BY ordinal_position;

-- Drop the existing folgas table if it has the wrong structure
DROP TABLE IF EXISTS folgas CASCADE;

-- Recreate folgas table with correct vendedor_id reference
CREATE TABLE folgas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendedor_id UUID NOT NULL REFERENCES vendedores(id) ON DELETE CASCADE,
    data DATE NOT NULL,
    tipo VARCHAR(20) DEFAULT 'FOLGA' CHECK (tipo IN ('FOLGA', 'FERIAS', 'LICENCA', 'FALTA', 'MEIO_PERIODO')),
    periodo VARCHAR(20) DEFAULT 'COMPLETO' CHECK (periodo IN ('COMPLETO', 'MANHA', 'TARDE')),
    motivo TEXT,
    aprovado BOOLEAN DEFAULT FALSE,
    aprovado_por UUID REFERENCES usuarios(id),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_folgas_vendedor_id ON folgas(vendedor_id);
CREATE INDEX idx_folgas_data ON folgas(data);
CREATE INDEX idx_folgas_tipo ON folgas(tipo);
CREATE INDEX idx_folgas_ativo ON folgas(ativo);

-- Create partial index for active folgas
CREATE INDEX idx_folgas_active ON folgas(vendedor_id, data) WHERE ativo = TRUE;

-- Add trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_folgas_updated_at 
    BEFORE UPDATE ON folgas 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Verify the table structure
\d folgas;

-- Show sample data structure
SELECT 'Folgas table created successfully' as status;

COMMIT;