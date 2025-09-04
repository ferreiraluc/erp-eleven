-- Complete Production Database Fix
-- Date: 2025-09-04
-- Issues: 
-- 1. Add cor_calendario to vendedores
-- 2. Fix folgas table with vendedor_id instead of funcionario_id
-- 3. Ensure proper indexes and constraints

BEGIN;

-- ========================================
-- 1. FIX VENDEDORES TABLE
-- ========================================

-- Add cor_calendario column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vendedores' 
        AND column_name = 'cor_calendario'
    ) THEN
        ALTER TABLE vendedores 
        ADD COLUMN cor_calendario VARCHAR(7) DEFAULT '#3B82F6';
        
        -- Assign different colors to existing vendors
        UPDATE vendedores 
        SET cor_calendario = CASE 
            WHEN (ROW_NUMBER() OVER (ORDER BY created_at)) % 8 = 1 THEN '#3B82F6'  -- Blue
            WHEN (ROW_NUMBER() OVER (ORDER BY created_at)) % 8 = 2 THEN '#EF4444'  -- Red  
            WHEN (ROW_NUMBER() OVER (ORDER BY created_at)) % 8 = 3 THEN '#10B981'  -- Green
            WHEN (ROW_NUMBER() OVER (ORDER BY created_at)) % 8 = 4 THEN '#F59E0B'  -- Orange
            WHEN (ROW_NUMBER() OVER (ORDER BY created_at)) % 8 = 5 THEN '#8B5CF6'  -- Purple
            WHEN (ROW_NUMBER() OVER (ORDER BY created_at)) % 8 = 6 THEN '#06B6D4'  -- Cyan
            WHEN (ROW_NUMBER() OVER (ORDER BY created_at)) % 8 = 7 THEN '#F97316'  -- Orange Dark
            ELSE '#84CC16'  -- Lime
        END;
        
        RAISE NOTICE 'Added cor_calendario column to vendedores table';
    ELSE
        RAISE NOTICE 'cor_calendario column already exists in vendedores table';
    END IF;
END $$;

-- ========================================
-- 2. FIX FOLGAS TABLE
-- ========================================

-- Check if folgas table has the wrong structure
DO $$ 
DECLARE
    has_funcionario_id BOOLEAN;
    has_vendedor_id BOOLEAN;
BEGIN
    -- Check for funcionario_id column
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'folgas' AND column_name = 'funcionario_id'
    ) INTO has_funcionario_id;
    
    -- Check for vendedor_id column
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'folgas' AND column_name = 'vendedor_id'
    ) INTO has_vendedor_id;
    
    -- If table has funcionario_id but not vendedor_id, we need to fix it
    IF has_funcionario_id AND NOT has_vendedor_id THEN
        RAISE NOTICE 'Fixing folgas table structure - replacing funcionario_id with vendedor_id';
        
        -- Drop existing folgas table (it's wrong)
        DROP TABLE IF EXISTS folgas CASCADE;
        
        -- Create new folgas table with correct structure
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
        
        -- Create indexes
        CREATE INDEX idx_folgas_vendedor_id ON folgas(vendedor_id);
        CREATE INDEX idx_folgas_data ON folgas(data);
        CREATE INDEX idx_folgas_tipo ON folgas(tipo);
        CREATE INDEX idx_folgas_ativo ON folgas(ativo);
        CREATE INDEX idx_folgas_active ON folgas(vendedor_id, data) WHERE ativo = TRUE;
        
        RAISE NOTICE 'Folgas table recreated with correct structure';
        
    ELSIF NOT has_funcionario_id AND has_vendedor_id THEN
        RAISE NOTICE 'Folgas table already has correct structure';
        
    ELSIF NOT has_funcionario_id AND NOT has_vendedor_id THEN
        RAISE NOTICE 'Creating folgas table with correct structure';
        
        -- Create folgas table
        CREATE TABLE IF NOT EXISTS folgas (
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
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_folgas_vendedor_id ON folgas(vendedor_id);
        CREATE INDEX IF NOT EXISTS idx_folgas_data ON folgas(data);
        CREATE INDEX IF NOT EXISTS idx_folgas_tipo ON folgas(tipo);
        CREATE INDEX IF NOT EXISTS idx_folgas_ativo ON folgas(ativo);
        CREATE INDEX IF NOT EXISTS idx_folgas_active ON folgas(vendedor_id, data) WHERE ativo = TRUE;
        
    END IF;
END $$;

-- ========================================
-- 3. CREATE UPDATE TRIGGER FOR FOLGAS
-- ========================================

-- Create or replace the update trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists and recreate
DROP TRIGGER IF EXISTS update_folgas_updated_at ON folgas;
CREATE TRIGGER update_folgas_updated_at 
    BEFORE UPDATE ON folgas 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- 4. VERIFICATION
-- ========================================

-- Show vendedores table structure
SELECT 'VENDEDORES TABLE STRUCTURE:' as info;
SELECT column_name, data_type, column_default, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'vendedores' 
ORDER BY ordinal_position;

-- Show folgas table structure
SELECT 'FOLGAS TABLE STRUCTURE:' as info;
SELECT column_name, data_type, column_default, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'folgas' 
ORDER BY ordinal_position;

-- Show sample vendor data
SELECT 'SAMPLE VENDEDORES DATA:' as info;
SELECT id, nome, cor_calendario, ativo FROM vendedores LIMIT 3;

-- Show constraints
SELECT 'FOLGAS CONSTRAINTS:' as info;
SELECT 
    tc.constraint_name, 
    tc.constraint_type, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
LEFT JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.table_name = 'folgas';

COMMIT;

SELECT 'DATABASE MIGRATION COMPLETED SUCCESSFULLY!' as status;