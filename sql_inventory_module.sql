-- =============================================
-- MÓDULO DE ESTOQUE (INVENTORY) — ERP Eleven
-- Executar no banco Render após deploy
-- =============================================

-- Enums
CREATE TYPE movementtype AS ENUM ('entry', 'exit', 'adjustment', 'transfer');
CREATE TYPE sessionstatus AS ENUM ('open', 'counting', 'reviewing', 'applied', 'cancelled');

-- =============================================
-- FORNECEDORES
-- =============================================

CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    contact VARCHAR(200),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- ITENS DE ESTOQUE
-- =============================================

CREATE TABLE inventory_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    size VARCHAR(50),
    color VARCHAR(50),
    unit VARCHAR(20) NOT NULL DEFAULT 'un',
    location VARCHAR(100),
    barcode VARCHAR(200),
    sku_internal VARCHAR(50) UNIQUE NOT NULL,
    supplier_id UUID REFERENCES suppliers(id),
    cost_price DECIMAL(12,2) NOT NULL DEFAULT 0,
    sale_price DECIMAL(12,2) NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'PYG',
    min_stock INTEGER NOT NULL DEFAULT 0,
    max_stock INTEGER NOT NULL DEFAULT 0,
    current_stock INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES usuarios(id)
);

CREATE INDEX idx_inventory_items_barcode ON inventory_items(barcode);
CREATE INDEX idx_inventory_items_category ON inventory_items(category);

-- =============================================
-- MOVIMENTAÇÕES DE ESTOQUE
-- =============================================

CREATE TABLE stock_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_id UUID NOT NULL REFERENCES inventory_items(id),
    movement_type movementtype NOT NULL,
    quantity INTEGER NOT NULL,
    quantity_before INTEGER NOT NULL,
    quantity_after INTEGER NOT NULL,
    reason VARCHAR(500),
    reference_type VARCHAR(50),
    reference_id VARCHAR(100),
    unit_cost DECIMAL(12,2),
    location_from VARCHAR(100),
    location_to VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES usuarios(id)
);

CREATE INDEX idx_stock_movements_item ON stock_movements(item_id);
CREATE INDEX idx_stock_movements_created_at ON stock_movements(created_at);

-- =============================================
-- SESSÕES DE INVENTÁRIO FÍSICO
-- =============================================

CREATE TABLE inventory_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    status sessionstatus NOT NULL DEFAULT 'open',
    location_filter VARCHAR(100),
    category_filter VARCHAR(100),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    applied_at TIMESTAMP,
    created_by UUID REFERENCES usuarios(id),
    approved_by UUID REFERENCES usuarios(id),
    notes TEXT
);

CREATE TABLE inventory_session_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES inventory_sessions(id),
    item_id UUID NOT NULL REFERENCES inventory_items(id),
    system_quantity INTEGER NOT NULL,
    counted_quantity INTEGER,
    scanned_at TIMESTAMP,
    counted_by UUID REFERENCES usuarios(id)
);

-- =============================================
-- ALEMBIC: marcar migration como aplicada
-- (apenas se estiver usando alembic no projeto)
-- =============================================
-- INSERT INTO alembic_version (version_num) VALUES ('a1b2c3d4e5f6')
-- ON CONFLICT DO NOTHING;
