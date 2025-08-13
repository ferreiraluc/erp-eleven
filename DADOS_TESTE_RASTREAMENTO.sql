-- 📦 DADOS DE TESTE - Sistema de Rastreamento
-- Execute após criar a tabela para ter dados para testar

-- Inserir rastreamentos de exemplo
INSERT INTO rastreamentos (
    codigo_rastreio, 
    status, 
    servico_provedor, 
    descricao, 
    destinatario, 
    origem, 
    destino,
    historico_eventos
) VALUES 
(
    'BR123456789BR', 
    'EM_TRANSITO', 
    'correios_api', 
    'Smartphone Samsung Galaxy', 
    'João Silva', 
    'São Paulo - SP', 
    'Rio de Janeiro - RJ',
    '[
        {"data": "2025-08-10 09:00:00", "situacao": "Objeto postado", "detalhes": "Objeto postado nos Correios", "local": "São Paulo - SP"},
        {"data": "2025-08-11 14:30:00", "situacao": "Objeto em trânsito", "detalhes": "Objeto em processo de entrega", "local": "Centro de Distribuição SP"}
    ]'::jsonb
),
(
    'PX987654321BR', 
    'PENDENTE', 
    'rastreio_pro', 
    'Notebook Dell Inspiron', 
    'Maria Santos', 
    'Curitiba - PR', 
    'Porto Alegre - RS',
    '[]'::jsonb
),
(
    'OY555444333BR', 
    'ENTREGUE', 
    'correios_oficial', 
    'Livros de programação', 
    'Carlos Ferreira', 
    'Brasília - DF', 
    'Belo Horizonte - MG',
    '[
        {"data": "2025-08-05 08:00:00", "situacao": "Objeto postado", "detalhes": "Objeto postado", "local": "Brasília - DF"},
        {"data": "2025-08-06 12:00:00", "situacao": "Objeto em trânsito", "detalhes": "Em rota de entrega", "local": "Centro Distribuição MG"},
        {"data": "2025-08-07 16:45:00", "situacao": "Objeto entregue", "detalhes": "Entregue ao destinatário", "local": "Belo Horizonte - MG"}
    ]'::jsonb
),
(
    'AB111222333BR', 
    'EM_TRANSITO', 
    'muambator', 
    'Roupas da Shein', 
    'Ana Costa', 
    'Recife - PE', 
    'Salvador - BA',
    '[
        {"data": "2025-08-12 10:15:00", "situacao": "Objeto postado", "detalhes": "Postado para entrega", "local": "Recife - PE"}
    ]'::jsonb
),
(
    'CD999888777BR', 
    'ERRO', 
    'correios_api', 
    'Peças de computador', 
    'Pedro Oliveira', 
    'Fortaleza - CE', 
    'Manaus - AM',
    '[
        {"data": "2025-08-11 09:00:00", "situacao": "Erro na entrega", "detalhes": "Destinatário ausente", "local": "Manaus - AM"}
    ]'::jsonb
);

-- Verificar dados inseridos
SELECT 'Dados de teste inseridos com sucesso!' as resultado;
SELECT COUNT(*) as total_rastreamentos FROM rastreamentos;
SELECT codigo_rastreio, status, destinatario FROM rastreamentos ORDER BY created_at DESC;