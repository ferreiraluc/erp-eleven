-- =============================================
-- CORRIGIR ERROS DE FOREIGN KEY NA RESTAURAÇÃO
-- Inserir usuários necessários primeiro
-- =============================================

-- Desabilitar triggers temporariamente para evitar conflitos
SET session_replication_role = replica;

-- Inserir usuários essenciais primeiro (se não existirem)
INSERT INTO usuarios (id, nome, email, senha_hash, role, ativo, ultimo_login, created_at, updated_at) 
VALUES 
    ('1db754f2-7d80-4f87-8b1f-3b501775c4ab', 'Administrador', 'admin@loja.com', '$2b$12$vG.shwiROZz7xX5fJ.Zl3OibD0jbq9W/VqIvvxiqrRIqL/1M.IB3m', 'ADMIN', TRUE, '2025-09-03 23:45:32.265356', '2025-08-03 21:50:00.57657', '2025-09-03 20:45:32.055644'),
    ('542e05b5-6a0d-4186-bba9-8810089bafb6', 'João Silva', 'joao@loja.com', '$2b$12$emhohGRigur59IgI0FyCkOU8p98v3uLpTQwr091c2s77FsXrOmGaq', 'GERENTE', TRUE, NULL, '2025-08-04 23:24:26.767431', '2025-08-04 23:24:26.767431'),
    ('91c70214-bc82-4c52-b440-466ca6733e8f', 'Maria Santos', 'maria@loja.com', '$2b$12$SYfiTXFv5Tu0gvRtygIv2eWhRJSFuchHuXkf1tZBBT789y7yupSNq', 'VENDEDOR', TRUE, NULL, '2025-08-04 23:24:26.956192', '2025-08-04 23:24:26.956192'),
    ('f1029c04-a9ba-4c80-be08-01e319d26ebf', 'Carlos Oliveira', 'carlos@loja.com', '$2b$12$zmWE72YIgGtmVPh9WFnHUO6S.rqLFaV/ySoqsPe1F508QsK9LdT/6', 'LIMPEZA', TRUE, '2025-08-05 02:43:18.109345', '2025-08-04 23:24:27.124804', '2025-08-05 19:49:41.052132')
ON CONFLICT (id) DO UPDATE SET
    nome = EXCLUDED.nome,
    email = EXCLUDED.email,
    senha_hash = EXCLUDED.senha_hash,
    role = EXCLUDED.role,
    ativo = EXCLUDED.ativo,
    ultimo_login = EXCLUDED.ultimo_login,
    updated_at = CURRENT_TIMESTAMP;

-- Reabilitar triggers
SET session_replication_role = DEFAULT;

-- Limpar dados órfãos em rastreamentos (se ainda existirem)
DELETE FROM rastreamentos 
WHERE created_by NOT IN (SELECT id FROM usuarios);

-- Limpar dados órfãos em outras tabelas também
DELETE FROM pedidos 
WHERE created_by NOT IN (SELECT id FROM usuarios);

DELETE FROM comprovantes 
WHERE uploaded_by NOT IN (SELECT id FROM usuarios) 
   OR aprovado_por NOT IN (SELECT id FROM usuarios WHERE id IS NOT NULL);

DELETE FROM pontos 
WHERE created_by NOT IN (SELECT id FROM usuarios);

DELETE FROM envios 
WHERE created_by NOT IN (SELECT id FROM usuarios);

-- Verificar se ainda há problemas
SELECT 'Verificando rastreamentos órfãos:' as status;
SELECT COUNT(*) as orfaos_rastreamentos 
FROM rastreamentos r 
WHERE r.created_by NOT IN (SELECT id FROM usuarios);

SELECT 'Verificando pedidos órfãos:' as status;
SELECT COUNT(*) as orfaos_pedidos 
FROM pedidos p 
WHERE p.created_by NOT IN (SELECT id FROM usuarios);

SELECT 'Total de usuários:' as status;
SELECT COUNT(*) as total_usuarios FROM usuarios;

-- Mostrar todos os usuários
SELECT id, nome, email, role FROM usuarios ORDER BY nome;