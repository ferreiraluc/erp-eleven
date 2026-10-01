-- MIGRATION 005: Add image_data column to inventory_items
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS image_data TEXT;
