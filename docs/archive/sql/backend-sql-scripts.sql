-- =============================================
-- ERP ELEVEN - Scripts SQL Úteis
-- Versão: 1.0.0
-- =============================================

-- =============================================
-- CRIAÇÃO DE USUÁRIOS
-- =============================================

-- Criar usuário administrador (substitua os valores)
-- IMPORTANTE: Use a API /api/auth/register ou a rota administrativa para gerar o hash da senha
INSERT INTO usuarios (email, hashed_password, full_name, role, is_active)
VALUES (
    'admin@eleven.com',                    -- Email do administrador
    '$2b$12$exemplo_hash_da_senha_aqui',   -- Hash da senha (gerar via API)
    'Administrador do Sistema',             -- Nome completo
    'ADMIN',                               -- Role (ADMIN, GERENTE, VENDEDOR, etc.)
    true                                   -- Ativo
);

-- Criar usuário gerente
INSERT INTO usuarios (email, hashed_password, full_name, role, is_active)
VALUES (
    'gerente@eleven.com',
    '$2b$12$exemplo_hash_da_senha_aqui',
    'Gerente da Loja',
    'GERENTE',
    true
);

-- Criar usuário vendedor
INSERT INTO usuarios (email, hashed_password, full_name, role, is_active)
VALUES (
    'vendedor@eleven.com',
    '$2b$12$exemplo_hash_da_senha_aqui',
    'Vendedor Principal',
    'VENDEDOR',
    true
);

-- =============================================
-- CONSULTAS ÚTEIS
-- =============================================

-- Listar todos os usuários ativos
SELECT 
    id,
    email,
    full_name,
    role,
    is_active,
    created_at
FROM usuarios 
WHERE is_active = true
ORDER BY created_at DESC;

-- Verificar status dos rastreamentos
SELECT 
    status,
    COUNT(*) as total,
    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER()), 2) as percentual
FROM rastreamentos 
WHERE ativo = true 
GROUP BY status
ORDER BY total DESC;

-- Rastreamentos criados nos últimos 30 dias
SELECT 
    DATE(created_at) as data,
    COUNT(*) as quantidade,
    status
FROM rastreamentos 
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    AND ativo = true
GROUP BY DATE(created_at), status
ORDER BY data DESC;

-- Usuários por role
SELECT 
    role,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE is_active = true) as ativos
FROM usuarios 
GROUP BY role
ORDER BY total DESC;

-- =============================================
-- MANUTENÇÃO E LIMPEZA
-- =============================================

-- Desativar rastreamentos antigos (mais de 6 meses)
UPDATE rastreamentos 
SET ativo = false 
WHERE created_at < CURRENT_DATE - INTERVAL '6 months'
    AND status IN ('ENTREGUE', 'ERRO')
    AND ativo = true;

-- Desativar usuários inativos há mais de 1 ano
UPDATE usuarios 
SET is_active = false 
WHERE updated_at < CURRENT_DATE - INTERVAL '1 year'
    AND is_active = true
    AND role NOT IN ('ADMIN');

-- Limpar histórico de eventos muito antigo (opcional)
UPDATE rastreamentos 
SET historico_eventos = '[]'::jsonb
WHERE created_at < CURRENT_DATE - INTERVAL '1 year'
    AND jsonb_array_length(historico_eventos) > 10;

-- =============================================
-- RELATÓRIOS
-- =============================================

-- Relatório de atividade por usuário (últimos 30 dias)
SELECT 
    u.full_name,
    u.email,
    u.role,
    COUNT(r.id) as rastreamentos_criados
FROM usuarios u
LEFT JOIN rastreamentos r ON u.id = r.created_by 
    AND r.created_at >= CURRENT_DATE - INTERVAL '30 days'
WHERE u.is_active = true
GROUP BY u.id, u.full_name, u.email, u.role
ORDER BY rastreamentos_criados DESC;

-- Status dos rastreamentos por período
SELECT 
    DATE_TRUNC('week', created_at) as semana,
    status,
    COUNT(*) as quantidade
FROM rastreamentos 
WHERE created_at >= CURRENT_DATE - INTERVAL '12 weeks'
    AND ativo = true
GROUP BY semana, status
ORDER BY semana DESC, status;

-- Rastreamentos com mais atualizações de status
SELECT 
    codigo_rastreio,
    destinatario,
    status,
    jsonb_array_length(historico_eventos) as total_eventos,
    created_at
FROM rastreamentos 
WHERE ativo = true
    AND jsonb_array_length(historico_eventos) > 5
ORDER BY total_eventos DESC
LIMIT 20;

-- =============================================
-- BACKUP E RESTORE
-- =============================================

-- Criar backup dos dados principais (execute no terminal)
/*
pg_dump -U postgres -h localhost \
    --table=usuarios \
    --table=rastreamentos \
    --data-only \
    eleven > backup_data_$(date +%Y%m%d).sql
*/

-- Backup completo (execute no terminal)
/*
pg_dump -U postgres -h localhost eleven > backup_complete_$(date +%Y%m%d).sql
*/

-- Restore (execute no terminal)
/*
psql -U postgres -h localhost -d eleven < backup_complete_20240101.sql
*/

-- =============================================
-- ÍNDICES PARA PERFORMANCE
-- =============================================

-- Verificar índices existentes
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename IN ('usuarios', 'rastreamentos')
ORDER BY tablename, indexname;

-- Criar índices adicionais se necessário
CREATE INDEX IF NOT EXISTS idx_rastreamentos_updated_at ON rastreamentos(updated_at);
CREATE INDEX IF NOT EXISTS idx_usuarios_role ON usuarios(role);
CREATE INDEX IF NOT EXISTS idx_rastreamentos_destinatario ON rastreamentos(destinatario);

-- =============================================
-- ESTATÍSTICAS DO SISTEMA
-- =============================================

-- Resumo geral do sistema
SELECT 
    'Usuários Ativos' as metrica,
    COUNT(*)::text as valor
FROM usuarios 
WHERE is_active = true

UNION ALL

SELECT 
    'Rastreamentos Ativos' as metrica,
    COUNT(*)::text as valor
FROM rastreamentos 
WHERE ativo = true

UNION ALL

SELECT 
    'Rastreamentos Entregues' as metrica,
    COUNT(*)::text as valor
FROM rastreamentos 
WHERE status = 'ENTREGUE' AND ativo = true

UNION ALL

SELECT 
    'Tamanho do Banco (MB)' as metrica,
    ROUND(pg_database_size(current_database()) / 1024.0 / 1024.0, 2)::text as valor;

-- =============================================
-- TROUBLESHOOTING
-- =============================================

-- Verificar conexões ativas
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    LEFT(query, 50) as query_preview
FROM pg_stat_activity 
WHERE datname = 'eleven'
    AND state = 'active';

-- Verificar locks
SELECT 
    relation::regclass,
    mode,
    granted,
    pid,
    query_start
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE a.datname = 'eleven';

-- Verificar tamanho das tabelas
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY size_bytes DESC;