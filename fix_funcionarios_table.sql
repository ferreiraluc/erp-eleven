-- =============================================
-- CORRIGIR ESTRUTURA DA TABELA FUNCIONARIOS
-- Problema: ordem das colunas está diferente
-- =============================================

-- Remover dados problemáticos se existirem (com CASCADE para tabelas dependentes)
TRUNCATE TABLE funcionarios, pontos CASCADE;

-- Verificar e corrigir a estrutura da tabela
-- Garantir que as colunas estão na ordem correta
ALTER TABLE funcionarios 
DROP COLUMN IF EXISTS cor_calendario,
ADD COLUMN IF NOT EXISTS cor_calendario VARCHAR(7) DEFAULT '#3B82F6';

-- Recriar a tabela com a estrutura correta se necessário
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
    
    -- Horários (formato JSON para flexibilidade)
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

-- Recriar trigger
DROP TRIGGER IF EXISTS update_funcionarios_updated_at ON funcionarios;
CREATE TRIGGER update_funcionarios_updated_at 
    BEFORE UPDATE ON funcionarios 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Dados de teste básicos (opcional)
INSERT INTO funcionarios (nome, cargo, ativo) VALUES
('João Silva', 'Gerente', TRUE),
('Maria Santos', 'Vendedor', TRUE)
ON CONFLICT (cpf) DO NOTHING;