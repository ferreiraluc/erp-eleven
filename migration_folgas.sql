-- Migration para sistema de folgas
-- Execute estes comandos no seu PostgreSQL

-- 1. Adicionar coluna cor_calendario na tabela funcionarios
ALTER TABLE funcionarios ADD COLUMN IF NOT EXISTS cor_calendario VARCHAR(7) DEFAULT '#3B82F6';

-- 2. Criar enum para tipos de folga
DO $$ BEGIN
    CREATE TYPE tipofolga AS ENUM ('FOLGA', 'FERIAS', 'LICENCA', 'FALTA', 'MEIO_PERIODO');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 3. Criar tabela folgas
CREATE TABLE IF NOT EXISTS folgas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    funcionario_id UUID NOT NULL REFERENCES funcionarios(id),
    data DATE NOT NULL,
    tipo tipofolga DEFAULT 'FOLGA',
    periodo VARCHAR(20) DEFAULT 'COMPLETO',
    motivo TEXT,
    aprovado BOOLEAN DEFAULT FALSE,
    aprovado_por UUID REFERENCES usuarios(id),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_folgas_funcionario_data ON folgas(funcionario_id, data);
CREATE INDEX IF NOT EXISTS idx_folgas_data ON folgas(data);
CREATE INDEX IF NOT EXISTS idx_folgas_ativo ON folgas(ativo);

-- 5. Atualizar cores dos funcionários existentes (opcional)
UPDATE funcionarios SET cor_calendario = '#3B82F6' WHERE cor_calendario IS NULL;

-- 6. Inserir funcionários de exemplo (se não existirem)
INSERT INTO funcionarios (id, nome, cpf, cargo, cor_calendario, salario, telefone, ativo)
SELECT 
    gen_random_uuid(),
    'Ana Silva',
    '123.456.789-01',
    'Vendedora Senior',
    '#3B82F6',
    3000.00,
    '(11) 98765-4321',
    true
WHERE NOT EXISTS (SELECT 1 FROM funcionarios WHERE cpf = '123.456.789-01');

INSERT INTO funcionarios (id, nome, cpf, cargo, cor_calendario, salario, telefone, ativo)
SELECT 
    gen_random_uuid(),
    'Carlos Santos',
    '234.567.890-12',
    'Vendedor',
    '#EF4444',
    2500.00,
    '(11) 98765-4322',
    true
WHERE NOT EXISTS (SELECT 1 FROM funcionarios WHERE cpf = '234.567.890-12');

INSERT INTO funcionarios (id, nome, cpf, cargo, cor_calendario, salario, telefone, ativo)
SELECT 
    gen_random_uuid(),
    'Maria Oliveira',
    '345.678.901-23',
    'Gerente de Vendas',
    '#10B981',
    4500.00,
    '(11) 98765-4323',
    true
WHERE NOT EXISTS (SELECT 1 FROM funcionarios WHERE cpf = '345.678.901-23');

INSERT INTO funcionarios (id, nome, cpf, cargo, cor_calendario, salario, telefone, ativo)
SELECT 
    gen_random_uuid(),
    'João Pereira',
    '456.789.012-34',
    'Vendedor Junior',
    '#F59E0B',
    2000.00,
    '(11) 98765-4324',
    true
WHERE NOT EXISTS (SELECT 1 FROM funcionarios WHERE cpf = '456.789.012-34');

INSERT INTO funcionarios (id, nome, cpf, cargo, cor_calendario, salario, telefone, ativo)
SELECT 
    gen_random_uuid(),
    'Laura Costa',
    '567.890.123-45',
    'Supervisora',
    '#8B5CF6',
    3500.00,
    '(11) 98765-4325',
    true
WHERE NOT EXISTS (SELECT 1 FROM funcionarios WHERE cpf = '567.890.123-45');

-- 7. Inserir algumas folgas de exemplo para este mês
INSERT INTO folgas (id, funcionario_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    gen_random_uuid(),
    f.id,
    CURRENT_DATE + (random() * 30 - 15)::int,
    (ARRAY['FOLGA', 'FERIAS', 'LICENCA'])[floor(random() * 3 + 1)],
    'COMPLETO',
    'Folga de exemplo',
    random() > 0.3,
    true
FROM funcionarios f
WHERE f.ativo = true
ORDER BY random()
LIMIT 10;

COMMIT;