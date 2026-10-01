-- =============================================
-- MIGRAÇÃO INICIAL: Setup completo do banco de dados ERP Eleven
-- Data: 2025-08-19 - Versão 1.0
-- =============================================

-- Habilitar extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enum para status de rastreamento
DO $$ BEGIN
    CREATE TYPE rastreamento_status AS ENUM ('PENDENTE', 'EM_TRANSITO', 'ENTREGUE', 'ERRO', 'NAO_ENCONTRADO');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Tabela para armazenar rastreamentos
CREATE TABLE IF NOT EXISTS rastreamentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_rastreio VARCHAR(100) NOT NULL UNIQUE,
    
    -- Dados do rastreamento
    status rastreamento_status DEFAULT 'PENDENTE',
    servico_provedor VARCHAR(100),
    ultima_atualizacao TIMESTAMP,
    
    -- Dados do objeto
    descricao TEXT,
    destinatario VARCHAR(200),
    origem VARCHAR(200),
    destino VARCHAR(200),
    
    -- Dados históricos (JSON para flexibilidade)
    historico_eventos JSONB DEFAULT '[]'::jsonb,
    
    -- Relacionamento com pedidos (opcional)
    pedido_id UUID,
    
    -- Metadados
    data_criacao DATE DEFAULT CURRENT_DATE,
    ativo BOOLEAN DEFAULT TRUE,
    
    -- Auditoria
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_rastreamentos_codigo ON rastreamentos(codigo_rastreio);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_status ON rastreamentos(status);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_ativo ON rastreamentos(ativo);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_created_at ON rastreamentos(created_at);

-- Verificar se a migração foi aplicada com sucesso
SELECT 'Database migrated successfully - ERP Eleven v1.0!' as resultado;