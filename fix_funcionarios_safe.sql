-- =============================================
-- CORRIGIR ESTRUTURA DA TABELA FUNCIONARIOS (SEGURO)
-- Remove dependências primeiro
-- =============================================

-- Primeiro limpar tabela pontos que depende de funcionarios
TRUNCATE TABLE pontos;

-- Agora limpar funcionarios
TRUNCATE TABLE funcionarios;

-- Recriar a tabela funcionarios com estrutura correta
DROP TABLE IF EXISTS funcionarios CASCADE;

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
    
    -- Horários (formato JSON)
    horarios JSONB,
    
    -- Dados pessoais
    telefone VARCHAR(20),
    endereco TEXT,
    
    -- Controle
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Cor do calendário (última coluna)
    cor_calendario VARCHAR(7) DEFAULT '#3B82F6'
);

-- Recriar tabela pontos se necessário
CREATE TABLE IF NOT EXISTS pontos (
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

-- Recriar triggers
CREATE TRIGGER update_funcionarios_updated_at 
    BEFORE UPDATE ON funcionarios 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Dados básicos para teste
INSERT INTO funcionarios (nome, cargo, ativo) VALUES
('João Silva', 'Gerente', TRUE),
('Maria Santos', 'Vendedor', TRUE);