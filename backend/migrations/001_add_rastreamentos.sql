-- =============================================
-- MIGRAÇÃO: Adicionar tabela de rastreamentos
-- Data: 2025-08-13
-- =============================================

-- Enum para status de rastreamento
CREATE TYPE rastreamento_status AS ENUM ('PENDENTE', 'EM_TRANSITO', 'ENTREGUE', 'ERRO', 'NAO_ENCONTRADO');

-- Tabela para armazenar rastreamentos
CREATE TABLE rastreamentos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo_rastreio VARCHAR(100) NOT NULL UNIQUE,
    
    -- Dados do rastreamento
    status rastreamento_status DEFAULT 'PENDENTE',
    servico_provedor VARCHAR(100), -- melhorrastreio, encomenda.io, etc
    ultima_atualizacao TIMESTAMP,
    
    -- Dados do objeto
    descricao TEXT,
    destinatario VARCHAR(200),
    origem VARCHAR(200),
    destino VARCHAR(200),
    
    -- Dados históricos (JSON para flexibilidade)
    historico_eventos JSONB DEFAULT '[]'::jsonb,
    
    -- Relacionamento com pedidos
    pedido_id UUID REFERENCES pedidos(id),
    
    -- Metadados
    data_criacao DATE DEFAULT CURRENT_DATE,
    ativo BOOLEAN DEFAULT TRUE,
    
    -- Auditoria
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES usuarios(id)
);

-- Índices para performance
CREATE INDEX idx_rastreamentos_codigo ON rastreamentos(codigo_rastreio);
CREATE INDEX idx_rastreamentos_status ON rastreamentos(status);
CREATE INDEX idx_rastreamentos_pedido ON rastreamentos(pedido_id);
CREATE INDEX idx_rastreamentos_data ON rastreamentos(data_criacao);

-- Trigger para updated_at
CREATE TRIGGER update_rastreamentos_updated_at 
    BEFORE UPDATE ON rastreamentos 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- View para rastreamentos ativos com dados do pedido
CREATE VIEW vw_rastreamentos_ativos AS
SELECT 
    r.id,
    r.codigo_rastreio,
    r.status,
    r.servico_provedor,
    r.ultima_atualizacao,
    r.descricao,
    r.destinatario,
    r.origem,
    r.destino,
    r.data_criacao,
    p.numero_pedido,
    p.cliente_nome,
    p.cliente_telefone,
    p.endereco_cidade,
    p.endereco_uf
FROM rastreamentos r
LEFT JOIN pedidos p ON r.pedido_id = p.id
WHERE r.ativo = TRUE
ORDER BY r.updated_at DESC;

-- Inserir dados de exemplo
INSERT INTO rastreamentos (codigo_rastreio, status, descricao, destinatario, created_by) 
VALUES 
    ('BR123456789BR', 'EM_TRANSITO', 'Pacote de roupas', 'João Silva', (SELECT id FROM usuarios WHERE role = 'ADMIN' LIMIT 1)),
    ('BR987654321BR', 'ENTREGUE', 'Encomenda de acessórios', 'Maria Santos', (SELECT id FROM usuarios WHERE role = 'ADMIN' LIMIT 1));