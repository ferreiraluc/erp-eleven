-- =============================================
-- BANCO DE DADOS ERP LOJA DE ROUPAS
-- Estrutura inicial baseada na planilha atual
-- =============================================

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================
-- ENUMS
-- =============================================

CREATE TYPE moeda_tipo AS ENUM ('G$', 'R$', 'U$', 'EUR');
CREATE TYPE pagamento_metodo AS ENUM ('DEBITO', 'CREDITO', 'PIX', 'DINHEIRO', 'TRANSFERENCIA');
CREATE TYPE pedido_status AS ENUM ('PENDENTE', 'PROCESSANDO', 'ENVIADO', 'ENTREGUE', 'CANCELADO');
CREATE TYPE transportadora_tipo AS ENUM ('CORREIOS', 'AZUL_CARGO', 'PARTICULAR', 'SUPERFRETE');
CREATE TYPE usuario_role AS ENUM ('ADMIN', 'GERENTE', 'VENDEDOR', 'FINANCEIRO', 'OPERACIONAL');

-- =============================================
-- TABELA DE USUÁRIOS E AUTENTICAÇÃO
-- =============================================

CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    role usuario_role NOT NULL DEFAULT 'VENDEDOR',
    ativo BOOLEAN DEFAULT TRUE,
    ultimo_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- VENDEDORES
-- =============================================

CREATE TABLE vendedores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome VARCHAR(100) NOT NULL,
    usuario_id UUID REFERENCES usuarios(id),
    taxa_comissao DECIMAL(5,2) DEFAULT 10.00, -- Porcentagem
    meta_semanal DECIMAL(12,2) DEFAULT 0,
    conta_bancaria VARCHAR(50),
    telefone VARCHAR(20),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inserir vendedores atuais baseados na planilha
INSERT INTO vendedores (nome, ativo) VALUES 
    ('Junior', TRUE),
    ('Denis', TRUE), 
    ('Sol', TRUE),
    ('Wiss', TRUE),
    ('Lucas', TRUE);

-- =============================================
-- CAMBISTAS
-- =============================================

CREATE TABLE cambistas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome VARCHAR(100) NOT NULL,
    taxa_g_para_r DECIMAL(8,4) DEFAULT 5.65, -- Taxa atual G$ para R$
    taxa_u_para_r DECIMAL(8,4) DEFAULT 5.50, -- Taxa U$ para R$
    taxa_eur_para_r DECIMAL(8,4) DEFAULT 6.20, -- Taxa EUR para R$
    conta_bancaria VARCHAR(50),
    telefone VARCHAR(20),
    ativo BOOLEAN DEFAULT TRUE,
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- VENDAS (TABELA PRINCIPAL)
-- =============================================

CREATE TABLE vendas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    data_venda DATE NOT NULL DEFAULT CURRENT_DATE,
    vendedor_id UUID NOT NULL REFERENCES vendedores(id),
    
    -- Dados da venda
    moeda moeda_tipo NOT NULL,
    valor_bruto DECIMAL(15,4) NOT NULL,
    metodo_pagamento pagamento_metodo NOT NULL,
    
    -- Cálculos para cambistas
    cambista_id UUID REFERENCES cambistas(id),
    taxa_cambio_usada DECIMAL(8,4),
    valor_cambista DECIMAL(15,4), -- Valor que fica com o cambista
    valor_liquido DECIMAL(15,4) NOT NULL, -- Valor final para a empresa
    
    -- Dados do produto/serviço
    descricao_produto TEXT,
    observacoes TEXT,
    
    -- Controle de fechamento semanal
    semana_fechamento DATE, -- Data do sábado da semana
    fechado BOOLEAN DEFAULT FALSE,
    
    -- Auditoria
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES usuarios(id)
);

-- Índices para performance
CREATE INDEX idx_vendas_data ON vendas(data_venda);
CREATE INDEX idx_vendas_vendedor ON vendas(vendedor_id);
CREATE INDEX idx_vendas_moeda ON vendas(moeda);
CREATE INDEX idx_vendas_semana ON vendas(semana_fechamento);

-- =============================================
-- COMPROVANTES
-- =============================================

CREATE TABLE comprovantes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    venda_id UUID NOT NULL REFERENCES vendas(id) ON DELETE CASCADE,
    
    -- Dados do arquivo
    nome_arquivo VARCHAR(255) NOT NULL,
    arquivo_url VARCHAR(500) NOT NULL,
    tipo_arquivo VARCHAR(10) NOT NULL, -- jpg, png, pdf
    tamanho_bytes BIGINT,
    
    -- Controle
    aprovado BOOLEAN DEFAULT FALSE,
    aprovado_por UUID REFERENCES usuarios(id),
    aprovado_em TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by UUID REFERENCES usuarios(id)
);

-- =============================================
-- PEDIDOS E LOGÍSTICA
-- =============================================

CREATE TABLE pedidos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    numero_pedido VARCHAR(50) UNIQUE NOT NULL,
    
    -- Dados do cliente
    cliente_nome VARCHAR(200) NOT NULL,
    cliente_telefone VARCHAR(20),
    cliente_email VARCHAR(100),
    
    -- Endereço completo
    endereco_rua VARCHAR(300) NOT NULL,
    endereco_numero VARCHAR(20),
    endereco_complemento VARCHAR(100),
    endereco_bairro VARCHAR(100),
    endereco_cidade VARCHAR(100) NOT NULL,
    endereco_uf CHAR(2) NOT NULL,
    endereco_cep VARCHAR(10) NOT NULL,
    
    -- Logística
    transportadora transportadora_tipo NOT NULL,
    codigo_rastreio VARCHAR(100),
    valor_frete DECIMAL(10,2),
    peso_kg DECIMAL(8,3),
    
    -- Status e datas
    status pedido_status DEFAULT 'PENDENTE',
    data_pedido DATE DEFAULT CURRENT_DATE,
    data_envio DATE,
    data_entrega DATE,
    
    -- Observações
    observacoes TEXT,
    instrucoes_entrega TEXT,
    
    -- Auditoria
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES usuarios(id)
);

-- Gerar número do pedido automaticamente
CREATE SEQUENCE seq_pedido_numero START 1000;

-- Trigger para gerar número do pedido
CREATE OR REPLACE FUNCTION generate_pedido_numero()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.numero_pedido IS NULL THEN
        NEW.numero_pedido := 'PED' || LPAD(nextval('seq_pedido_numero')::TEXT, 6, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_pedido_numero
    BEFORE INSERT ON pedidos
    FOR EACH ROW
    EXECUTE FUNCTION generate_pedido_numero();

-- =============================================
-- FUNCIONÁRIOS E RH
-- =============================================

CREATE TABLE funcionarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome VARCHAR(100) NOT NULL,
    cpf VARCHAR(14) UNIQUE,
    usuario_id UUID REFERENCES usuarios(id),
    
    -- Dados trabalhistas
    cargo VARCHAR(100),
    salario DECIMAL(10,2),
    data_admissao DATE,
    data_demissao DATE,
    
    -- Horários (formato JSON para flexibilidade)
    horarios JSONB, -- Ex: {"seg": "08:00-18:00", "ter": "08:00-18:00"}
    
    -- Dados pessoais
    telefone VARCHAR(20),
    endereco TEXT,
    
    -- Controle
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- CONTROLE DE PONTO
-- =============================================

CREATE TABLE pontos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    funcionario_id UUID NOT NULL REFERENCES funcionarios(id),
    data_ponto DATE NOT NULL,
    
    -- Horários
    entrada_manha TIME,
    saida_almoco TIME,
    entrada_tarde TIME,
    saida_noite TIME,
    
    -- Cálculos
    horas_trabalhadas INTERVAL,
    horas_extras INTERVAL,
    
    -- Observações
    observacoes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES usuarios(id)
);

-- =============================================
-- FECHAMENTO SEMANAL (COMISSÕES)
-- =============================================

CREATE TABLE fechamentos_semanais (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    semana_inicio DATE NOT NULL, -- Domingo
    semana_fim DATE NOT NULL,    -- Sábado
    
    -- Status
    fechado BOOLEAN DEFAULT FALSE,
    fechado_em TIMESTAMP,
    fechado_por UUID REFERENCES usuarios(id),
    
    -- Totais gerais
    total_vendas_g DECIMAL(15,4) DEFAULT 0,
    total_vendas_r DECIMAL(15,4) DEFAULT 0,
    total_vendas_u DECIMAL(15,4) DEFAULT 0,
    total_vendas_eur DECIMAL(15,4) DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- COMISSÕES POR VENDEDOR
-- =============================================

CREATE TABLE comissoes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fechamento_id UUID NOT NULL REFERENCES fechamentos_semanais(id),
    vendedor_id UUID NOT NULL REFERENCES vendedores(id),
    
    -- Totais por moeda
    total_g DECIMAL(15,4) DEFAULT 0,
    total_r DECIMAL(15,4) DEFAULT 0,
    total_u DECIMAL(15,4) DEFAULT 0,
    total_eur DECIMAL(15,4) DEFAULT 0,
    
    -- Comissão calculada
    percentual_comissao DECIMAL(5,2),
    valor_comissao DECIMAL(12,2),
    
    -- Status do pagamento
    pago BOOLEAN DEFAULT FALSE,
    data_pagamento DATE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- TRIGGERS PARA UPDATED_AT
-- =============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Aplicar trigger em todas as tabelas relevantes
CREATE TRIGGER update_usuarios_updated_at BEFORE UPDATE ON usuarios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_vendedores_updated_at BEFORE UPDATE ON vendedores FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_cambistas_updated_at BEFORE UPDATE ON cambistas FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_vendas_updated_at BEFORE UPDATE ON vendas FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_pedidos_updated_at BEFORE UPDATE ON pedidos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_funcionarios_updated_at BEFORE UPDATE ON funcionarios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- VIEWS ÚTEIS
-- =============================================

-- View para relatório de vendas por vendedor
CREATE VIEW vw_vendas_por_vendedor AS
SELECT 
    v.nome as vendedor,
    vd.data_venda,
    vd.moeda,
    SUM(vd.valor_bruto) as total_bruto,
    SUM(vd.valor_liquido) as total_liquido,
    COUNT(*) as quantidade_vendas
FROM vendas vd
JOIN vendedores v ON vd.vendedor_id = v.id
GROUP BY v.nome, vd.data_venda, vd.moeda
ORDER BY vd.data_venda DESC;

-- View para dashboard semanal
CREATE VIEW vw_vendas_semana_atual AS
SELECT 
    v.nome as vendedor,
    vd.moeda,
    SUM(vd.valor_bruto) as total_bruto,
    SUM(vd.valor_liquido) as total_liquido,
    COUNT(*) as quantidade
FROM vendas vd
JOIN vendedores v ON vd.vendedor_id = v.id
WHERE vd.data_venda >= date_trunc('week', CURRENT_DATE)
  AND vd.data_venda < date_trunc('week', CURRENT_DATE) + INTERVAL '7 days'
GROUP BY v.nome, vd.moeda
ORDER BY v.nome, vd.moeda;

-- =============================================
-- DADOS INICIAIS DE TESTE
-- =============================================

-- Usuário administrador inicial
INSERT INTO usuarios (nome, email, senha_hash, role) VALUES 
    ('Administrador', 'admin@loja.com', '$2b$12$exemplo_hash_senha', 'ADMIN');

-- Cambista inicial com taxa atual
INSERT INTO cambistas (nome, taxa_g_para_r, ativo) VALUES 
    ('Cambista Principal', 5.65, TRUE);