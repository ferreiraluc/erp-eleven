-- =============================================
-- SCRIPT PARA INSERIR FOLGAS DE EXEMPLO
-- Execute no pgAdmin do Render
-- =============================================

-- 1. Primeiro vamos ver os vendedores disponíveis
SELECT 'Vendedores disponíveis:' as info;
SELECT id, nome, cor_calendario, ativo FROM vendedores WHERE ativo = true ORDER BY nome;

-- 2. Inserir folgas de exemplo para Janeiro 2025
-- Usando os vendedores ativos existentes
INSERT INTO folgas (id, vendedor_id, data, tipo, periodo, motivo, aprovado, ativo, created_at, updated_at)
SELECT 
    gen_random_uuid() as id,
    v.id as vendedor_id,
    dates.data,
    tipos.tipo,
    periodos.periodo,
    'Folga de exemplo - ' || v.nome || ' em ' || dates.data,
    CASE WHEN random() > 0.3 THEN true ELSE false END as aprovado,
    true as ativo,
    CURRENT_TIMESTAMP as created_at,
    CURRENT_TIMESTAMP as updated_at
FROM 
    -- Vendedores ativos
    (SELECT id, nome FROM vendedores WHERE ativo = true LIMIT 10) v
CROSS JOIN 
    -- Datas de exemplo para Janeiro 2025
    (VALUES 
        ('2025-01-03'::date),
        ('2025-01-06'::date),
        ('2025-01-10'::date),
        ('2025-01-13'::date),
        ('2025-01-17'::date),
        ('2025-01-20'::date),
        ('2025-01-24'::date),
        ('2025-01-27'::date),
        ('2025-01-31'::date)
    ) AS dates(data)
CROSS JOIN
    -- Tipos de folga
    (VALUES 
        ('FOLGA'::tipofolga),
        ('FERIAS'::tipofolga),
        ('LICENCA'::tipofolga)
    ) AS tipos(tipo)
CROSS JOIN
    -- Períodos
    (VALUES 
        ('COMPLETO'),
        ('MANHA'),
        ('TARDE')
    ) AS periodos(periodo)
WHERE random() < 0.1  -- Só 10% das combinações para não criar muitas folgas
ON CONFLICT (vendedor_id, data) DO NOTHING;  -- Evita duplicatas

-- 3. Inserir algumas folgas específicas para Fevereiro 2025
INSERT INTO folgas (vendedor_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    v.id,
    '2025-02-05'::date,
    'FOLGA'::tipofolga,
    'COMPLETO',
    'Folga para consulta médica',
    true,
    true
FROM vendedores v WHERE v.ativo = true LIMIT 1
ON CONFLICT (vendedor_id, data) DO NOTHING;

INSERT INTO folgas (vendedor_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    v.id,
    '2025-02-12'::date,
    'FERIAS'::tipofolga,
    'COMPLETO',
    'Férias programadas',
    true,
    true
FROM vendedores v WHERE v.ativo = true OFFSET 1 LIMIT 1
ON CONFLICT (vendedor_id, data) DO NOTHING;

INSERT INTO folgas (vendedor_id, data, tipo, periodo, motivo, aprovado, ativo)
SELECT 
    v.id,
    '2025-02-19'::date,
    'MEIO_PERIODO'::tipofolga,
    'MANHA',
    'Compromisso pessoal',
    false,  -- Esta ainda não foi aprovada
    true
FROM vendedores v WHERE v.ativo = true OFFSET 2 LIMIT 1
ON CONFLICT (vendedor_id, data) DO NOTHING;

-- 4. Verificar quantas folgas foram inseridas
SELECT 'Total de folgas inseridas:' as info, COUNT(*) as total FROM folgas WHERE ativo = true;

-- 5. Verificar folgas por mês
SELECT 'Folgas por mês:' as info;
SELECT 
    TO_CHAR(data, 'YYYY-MM') as mes,
    COUNT(*) as total_folgas,
    COUNT(CASE WHEN aprovado THEN 1 END) as aprovadas,
    COUNT(CASE WHEN NOT aprovado THEN 1 END) as pendentes
FROM folgas 
WHERE ativo = true
GROUP BY TO_CHAR(data, 'YYYY-MM')
ORDER BY mes;

-- 6. Verificar folgas por vendedor
SELECT 'Folgas por vendedor:' as info;
SELECT 
    v.nome,
    v.cor_calendario,
    COUNT(f.id) as total_folgas,
    COUNT(CASE WHEN f.aprovado THEN 1 END) as aprovadas,
    COUNT(CASE WHEN NOT f.aprovado THEN 1 END) as pendentes
FROM vendedores v
LEFT JOIN folgas f ON v.id = f.vendedor_id AND f.ativo = true
WHERE v.ativo = true
GROUP BY v.id, v.nome, v.cor_calendario
ORDER BY total_folgas DESC;

-- 7. Mostrar algumas folgas detalhadas
SELECT 'Exemplos de folgas criadas:' as info;
SELECT 
    v.nome as vendedor,
    f.data,
    f.tipo,
    f.periodo,
    f.motivo,
    CASE WHEN f.aprovado THEN 'APROVADA' ELSE 'PENDENTE' END as status,
    f.created_at
FROM folgas f
JOIN vendedores v ON f.vendedor_id = v.id
WHERE f.ativo = true
ORDER BY f.data DESC, v.nome
LIMIT 15;

SELECT 'Folgas de exemplo inseridas com sucesso!' as resultado;