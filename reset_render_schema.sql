-- =============================================
-- RESET COMPLETO DO SCHEMA RENDER
-- Execute este script se quiser começar do zero
-- =============================================

-- Drop all tables (cuidado - isso apaga todos os dados!)
DROP TABLE IF EXISTS comprovantes CASCADE;
DROP TABLE IF EXISTS vendas CASCADE;
DROP TABLE IF EXISTS pontos CASCADE;
DROP TABLE IF EXISTS funcionarios CASCADE;
DROP TABLE IF EXISTS pedidos CASCADE;
DROP TABLE IF EXISTS comissoes CASCADE;
DROP TABLE IF EXISTS fechamentos_semanais CASCADE;
DROP TABLE IF EXISTS cambistas CASCADE;
DROP TABLE IF EXISTS vendedores CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;

-- Drop sequences
DROP SEQUENCE IF EXISTS seq_pedido_numero;

-- Drop views
DROP VIEW IF EXISTS vw_vendas_por_vendedor;
DROP VIEW IF EXISTS vw_vendas_semana_atual;

-- Drop functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS generate_pedido_numero() CASCADE;

-- Drop enums
DROP TYPE IF EXISTS moeda_tipo CASCADE;
DROP TYPE IF EXISTS pagamento_metodo CASCADE;
DROP TYPE IF EXISTS pedido_status CASCADE;
DROP TYPE IF EXISTS transportadora_tipo CASCADE;
DROP TYPE IF EXISTS usuario_role CASCADE;

-- Agora execute o conteúdo do arquivo postgres.sql