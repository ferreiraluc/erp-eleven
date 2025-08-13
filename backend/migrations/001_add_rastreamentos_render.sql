-- Migration para adicionar tabela de rastreamentos no Render
-- Execute este script no CLI do PostgreSQL do Render

-- Primeiro, habilitar a extensão UUID (se não estiver habilitada)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Criar o ENUM para status de rastreamento (se não existir)
DO $$ BEGIN
    CREATE TYPE rastreamento_status AS ENUM ('PENDENTE', 'EM_TRANSITO', 'ENTREGUE', 'ERRO', 'NAO_ENCONTRADO');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Criar tabela de rastreamentos
CREATE TABLE IF NOT EXISTS rastreamentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_rastreio VARCHAR(100) NOT NULL UNIQUE,
    
    -- Dados do rastreamento
    status rastreamento_status DEFAULT 'PENDENTE',
    servico_provedor VARCHAR(100), -- correios_api, rastreio_pro, etc
    ultima_atualizacao TIMESTAMP,
    
    -- Dados do objeto
    descricao TEXT,
    destinatario VARCHAR(200),
    origem VARCHAR(200),
    destino VARCHAR(200),
    
    -- Dados históricos (JSON para flexibilidade)
    historico_eventos JSONB DEFAULT '[]'::jsonb,
    
    -- Relacionamento com pedidos (opcional, pode ser NULL se não existir tabela pedidos)
    pedido_id UUID,
    
    -- Metadados
    data_criacao DATE DEFAULT CURRENT_DATE,
    ativo BOOLEAN DEFAULT TRUE,
    
    -- Auditoria
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID
);

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_rastreamentos_codigo ON rastreamentos(codigo_rastreio);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_status ON rastreamentos(status);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_ativo ON rastreamentos(ativo);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_created_at ON rastreamentos(created_at);

-- Verificar se a tabela foi criada
SELECT 'Tabela rastreamentos criada com sucesso!' as resultado;
SELECT COUNT(*) as total_rastreamentos FROM rastreamentos;