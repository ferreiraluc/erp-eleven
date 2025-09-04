-- Migration: Add cor_calendario field to vendedores table
-- Date: 2025-09-04
-- Description: Adds color picker functionality for vendors

BEGIN;

-- Check if column already exists (safety check)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vendedores' 
        AND column_name = 'cor_calendario'
    ) THEN
        -- Add the new column
        ALTER TABLE vendedores 
        ADD COLUMN cor_calendario VARCHAR(7) DEFAULT '#3B82F6';
        
        -- Update existing records with default colors (optional - cycling through some colors)
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
        END
        WHERE cor_calendario IS NULL OR cor_calendario = '#3B82F6';
        
        RAISE NOTICE 'Column cor_calendario added successfully to vendedores table';
    ELSE
        RAISE NOTICE 'Column cor_calendario already exists in vendedores table';
    END IF;
END $$;

-- Verify the migration
SELECT 
    column_name, 
    data_type, 
    column_default,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'vendedores' 
AND column_name = 'cor_calendario';

COMMIT;