-- 🚀 SCRIPT DE DEPLOY PARA RENDER - Sistema de Rastreamento
-- Copie e cole este script completo no CLI do PostgreSQL do Render

-- Etapa 1: Habilitar extensão UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Etapa 2: Criar ENUM para status
DO $$ BEGIN
    CREATE TYPE rastreamento_status AS ENUM ('PENDENTE', 'EM_TRANSITO', 'ENTREGUE', 'ERRO', 'NAO_ENCONTRADO');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Etapa 3: Criar tabela de rastreamentos
CREATE TABLE IF NOT EXISTS rastreamentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_rastreio VARCHAR(100) NOT NULL UNIQUE,
    status rastreamento_status DEFAULT 'PENDENTE',
    servico_provedor VARCHAR(100),
    ultima_atualizacao TIMESTAMP,
    descricao TEXT,
    destinatario VARCHAR(200),
    origem VARCHAR(200),
    destino VARCHAR(200),
    historico_eventos JSONB DEFAULT '[]'::jsonb,
    pedido_id UUID,
    data_criacao DATE DEFAULT CURRENT_DATE,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID
);

-- Etapa 4: Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_rastreamentos_codigo ON rastreamentos(codigo_rastreio);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_status ON rastreamentos(status);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_ativo ON rastreamentos(ativo);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_created_at ON rastreamentos(created_at);

-- Etapa 5: Verificar criação
SELECT 'Sistema de rastreamento instalado com sucesso!' as status;
SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_name = 'rastreamentos' ORDER BY ordinal_position;