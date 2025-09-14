--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.vendedores DROP CONSTRAINT IF EXISTS vendedores_usuario_id_fkey;
ALTER TABLE IF EXISTS ONLY public.vendas DROP CONSTRAINT IF EXISTS vendas_vendedor_id_fkey;
ALTER TABLE IF EXISTS ONLY public.vendas DROP CONSTRAINT IF EXISTS vendas_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.vendas DROP CONSTRAINT IF EXISTS vendas_cambista_id_fkey;
ALTER TABLE IF EXISTS ONLY public.rastreamentos DROP CONSTRAINT IF EXISTS rastreamentos_pedido_id_fkey;
ALTER TABLE IF EXISTS ONLY public.rastreamentos DROP CONSTRAINT IF EXISTS rastreamentos_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.pontos DROP CONSTRAINT IF EXISTS pontos_funcionario_id_fkey;
ALTER TABLE IF EXISTS ONLY public.pontos DROP CONSTRAINT IF EXISTS pontos_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.pedidos DROP CONSTRAINT IF EXISTS pedidos_separado_por_fkey;
ALTER TABLE IF EXISTS ONLY public.pedidos DROP CONSTRAINT IF EXISTS pedidos_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.funcionarios DROP CONSTRAINT IF EXISTS funcionarios_usuario_id_fkey;
ALTER TABLE IF EXISTS ONLY public.folgas DROP CONSTRAINT IF EXISTS folgas_vendedor_id_fkey;
ALTER TABLE IF EXISTS ONLY public.folgas DROP CONSTRAINT IF EXISTS folgas_aprovado_por_fkey;
ALTER TABLE IF EXISTS ONLY public.fechamentos_semanais DROP CONSTRAINT IF EXISTS fechamentos_semanais_fechado_por_fkey;
ALTER TABLE IF EXISTS ONLY public.envios DROP CONSTRAINT IF EXISTS envios_pedido_id_fkey;
ALTER TABLE IF EXISTS ONLY public.envios DROP CONSTRAINT IF EXISTS envios_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.comprovantes DROP CONSTRAINT IF EXISTS comprovantes_venda_id_fkey;
ALTER TABLE IF EXISTS ONLY public.comprovantes DROP CONSTRAINT IF EXISTS comprovantes_uploaded_by_fkey;
ALTER TABLE IF EXISTS ONLY public.comprovantes DROP CONSTRAINT IF EXISTS comprovantes_aprovado_por_fkey;
ALTER TABLE IF EXISTS ONLY public.comissoes DROP CONSTRAINT IF EXISTS comissoes_vendedor_id_fkey;
ALTER TABLE IF EXISTS ONLY public.comissoes DROP CONSTRAINT IF EXISTS comissoes_fechamento_id_fkey;
DROP TRIGGER IF EXISTS update_vendedores_updated_at ON public.vendedores;
DROP TRIGGER IF EXISTS update_vendas_updated_at ON public.vendas;
DROP TRIGGER IF EXISTS update_usuarios_updated_at ON public.usuarios;
DROP TRIGGER IF EXISTS update_pedidos_updated_at ON public.pedidos;
DROP TRIGGER IF EXISTS update_funcionarios_updated_at ON public.funcionarios;
DROP TRIGGER IF EXISTS update_cambistas_updated_at ON public.cambistas;
DROP TRIGGER IF EXISTS trigger_pedido_numero ON public.pedidos;
DROP INDEX IF EXISTS public.ix_rastreamentos_codigo_rastreio;
DROP INDEX IF EXISTS public.ix_envios_codigo_rastreio;
DROP INDEX IF EXISTS public.idx_vendas_vendedor;
DROP INDEX IF EXISTS public.idx_vendas_semana;
DROP INDEX IF EXISTS public.idx_vendas_moeda;
DROP INDEX IF EXISTS public.idx_vendas_data;
DROP INDEX IF EXISTS public.idx_folgas_vendedor_data;
DROP INDEX IF EXISTS public.idx_folgas_data;
DROP INDEX IF EXISTS public.idx_folgas_ativo;
ALTER TABLE IF EXISTS ONLY public.vendedores DROP CONSTRAINT IF EXISTS vendedores_pkey;
ALTER TABLE IF EXISTS ONLY public.vendas DROP CONSTRAINT IF EXISTS vendas_pkey;
ALTER TABLE IF EXISTS ONLY public.usuarios DROP CONSTRAINT IF EXISTS usuarios_pkey;
ALTER TABLE IF EXISTS ONLY public.usuarios DROP CONSTRAINT IF EXISTS usuarios_email_key;
ALTER TABLE IF EXISTS ONLY public.rastreamentos DROP CONSTRAINT IF EXISTS rastreamentos_pkey;
ALTER TABLE IF EXISTS ONLY public.pontos DROP CONSTRAINT IF EXISTS pontos_pkey;
ALTER TABLE IF EXISTS ONLY public.pedidos DROP CONSTRAINT IF EXISTS pedidos_pkey;
ALTER TABLE IF EXISTS ONLY public.pedidos DROP CONSTRAINT IF EXISTS pedidos_numero_pedido_key;
ALTER TABLE IF EXISTS ONLY public.money_transfers DROP CONSTRAINT IF EXISTS money_transfers_pkey;
ALTER TABLE IF EXISTS ONLY public.funcionarios DROP CONSTRAINT IF EXISTS funcionarios_pkey;
ALTER TABLE IF EXISTS ONLY public.funcionarios DROP CONSTRAINT IF EXISTS funcionarios_cpf_key;
ALTER TABLE IF EXISTS ONLY public.folgas DROP CONSTRAINT IF EXISTS folgas_vendedor_id_data_key;
ALTER TABLE IF EXISTS ONLY public.folgas DROP CONSTRAINT IF EXISTS folgas_pkey;
ALTER TABLE IF EXISTS ONLY public.fechamentos_semanais DROP CONSTRAINT IF EXISTS fechamentos_semanais_pkey;
ALTER TABLE IF EXISTS ONLY public.exchange_rates DROP CONSTRAINT IF EXISTS exchange_rates_pkey;
ALTER TABLE IF EXISTS ONLY public.envios DROP CONSTRAINT IF EXISTS envios_pkey;
ALTER TABLE IF EXISTS ONLY public.comprovantes DROP CONSTRAINT IF EXISTS comprovantes_pkey;
ALTER TABLE IF EXISTS ONLY public.comissoes DROP CONSTRAINT IF EXISTS comissoes_pkey;
ALTER TABLE IF EXISTS ONLY public.cambistas DROP CONSTRAINT IF EXISTS cambistas_pkey;
ALTER TABLE IF EXISTS ONLY public.alembic_version DROP CONSTRAINT IF EXISTS alembic_version_pkc;
DROP VIEW IF EXISTS public.vw_vendas_semana_atual;
DROP VIEW IF EXISTS public.vw_vendas_por_vendedor;
DROP TABLE IF EXISTS public.vendedores;
DROP TABLE IF EXISTS public.vendas;
DROP TABLE IF EXISTS public.usuarios;
DROP SEQUENCE IF EXISTS public.seq_pedido_numero;
DROP TABLE IF EXISTS public.rastreamentos;
DROP TABLE IF EXISTS public.pontos;
DROP TABLE IF EXISTS public.pedidos;
DROP TABLE IF EXISTS public.money_transfers;
DROP TABLE IF EXISTS public.funcionarios;
DROP TABLE IF EXISTS public.folgas;
DROP TABLE IF EXISTS public.fechamentos_semanais;
DROP TABLE IF EXISTS public.exchange_rates;
DROP TABLE IF EXISTS public.envios;
DROP TABLE IF EXISTS public.comprovantes;
DROP TABLE IF EXISTS public.comissoes;
DROP TABLE IF EXISTS public.cambistas;
DROP TABLE IF EXISTS public.alembic_version;
DROP FUNCTION IF EXISTS public.update_updated_at_column();
DROP FUNCTION IF EXISTS public.generate_pedido_numero();
DROP TYPE IF EXISTS public.usuariorole;
DROP TYPE IF EXISTS public.usuario_role;
DROP TYPE IF EXISTS public.transportadoratipo;
DROP TYPE IF EXISTS public.transportadora_tipo;
DROP TYPE IF EXISTS public.transferstatus;
DROP TYPE IF EXISTS public.tipofolga;
DROP TYPE IF EXISTS public.rastreamento_status;
DROP TYPE IF EXISTS public.pedidostatus;
DROP TYPE IF EXISTS public.pedido_status;
DROP TYPE IF EXISTS public.pagamentometodo;
DROP TYPE IF EXISTS public.pagamento_metodo;
DROP TYPE IF EXISTS public.moedatipo;
DROP TYPE IF EXISTS public.moeda_tipo;
DROP TYPE IF EXISTS public.envio_status;
DROP TYPE IF EXISTS public.currencypair;
DROP EXTENSION IF EXISTS "uuid-ossp";
DROP EXTENSION IF EXISTS pg_trgm;
--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: currencypair; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.currencypair AS ENUM (
    'USD_TO_PYG',
    'USD_TO_BRL',
    'EUR_TO_PYG',
    'EUR_TO_BRL',
    'EUR_TO_USD'
);


--
-- Name: envio_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.envio_status AS ENUM (
    'PENDENTE',
    'EM_TRANSITO',
    'ENTREGUE',
    'ERRO',
    'NAO_ENCONTRADO'
);


--
-- Name: moeda_tipo; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.moeda_tipo AS ENUM (
    'G$',
    'R$',
    'U$',
    'EUR'
);


--
-- Name: moedatipo; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.moedatipo AS ENUM (
    'G_DOLLAR',
    'R_DOLLAR',
    'U_DOLLAR',
    'EUR'
);


--
-- Name: pagamento_metodo; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.pagamento_metodo AS ENUM (
    'DEBITO',
    'CREDITO',
    'PIX',
    'DINHEIRO',
    'TRANSFERENCIA',
    'PIX_POWER',
    'PIX_THAIS',
    'PIX_MERCADO_PAGO',
    'PY_TRANSFER_SUDAMERIS',
    'PY_TRANSFER_INTERFISA'
);


--
-- Name: pagamentometodo; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.pagamentometodo AS ENUM (
    'DEBITO',
    'CREDITO',
    'PIX',
    'DINHEIRO',
    'TRANSFERENCIA'
);


--
-- Name: pedido_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.pedido_status AS ENUM (
    'PENDENTE',
    'PROCESSANDO',
    'ENVIADO',
    'ENTREGUE',
    'CANCELADO',
    'VENDIDO',
    'SEPARANDO',
    'SEPARADO_PAGO',
    'SEPARADO_NAO_PAGO',
    'CONCLUIDO'
);


--
-- Name: pedidostatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.pedidostatus AS ENUM (
    'PENDENTE',
    'PROCESSANDO',
    'ENVIADO',
    'ENTREGUE',
    'CANCELADO'
);


--
-- Name: rastreamento_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.rastreamento_status AS ENUM (
    'PENDENTE',
    'EM_TRANSITO',
    'ENTREGUE',
    'ERRO',
    'NAO_ENCONTRADO'
);


--
-- Name: tipofolga; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tipofolga AS ENUM (
    'FOLGA',
    'FERIAS',
    'LICENCA',
    'FALTA',
    'MEIO_PERIODO'
);


--
-- Name: transferstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transferstatus AS ENUM (
    'PENDING',
    'DELIVERED',
    'CANCELLED'
);


--
-- Name: transportadora_tipo; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transportadora_tipo AS ENUM (
    'CORREIOS',
    'AZUL_CARGO',
    'PARTICULAR',
    'SUPERFRETE'
);


--
-- Name: transportadoratipo; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transportadoratipo AS ENUM (
    'CORREIOS',
    'AZUL_CARGO',
    'PARTICULAR',
    'SUPERFRETE'
);


--
-- Name: usuario_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.usuario_role AS ENUM (
    'ADMIN',
    'GERENTE',
    'VENDEDOR',
    'FINANCEIRO',
    'OPERACIONAL',
    'LIMPEZA'
);


--
-- Name: usuariorole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.usuariorole AS ENUM (
    'ADMIN',
    'GERENTE',
    'VENDEDOR',
    'FINANCEIRO',
    'OPERACIONAL'
);


--
-- Name: generate_pedido_numero(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.generate_pedido_numero() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.numero_pedido IS NULL THEN
        NEW.numero_pedido := 'PED' || LPAD(nextval('seq_pedido_numero')::TEXT, 6, '0');
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: cambistas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cambistas (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    nome character varying(100) NOT NULL,
    taxa_g_para_r numeric(8,4) DEFAULT 5.65,
    taxa_u_para_r numeric(8,4) DEFAULT 5.50,
    taxa_eur_para_r numeric(8,4) DEFAULT 6.20,
    conta_bancaria character varying(50),
    telefone character varying(20),
    ativo boolean DEFAULT true,
    observacoes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: comissoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comissoes (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    fechamento_id uuid NOT NULL,
    vendedor_id uuid NOT NULL,
    total_g numeric(15,4) DEFAULT 0,
    total_r numeric(15,4) DEFAULT 0,
    total_u numeric(15,4) DEFAULT 0,
    total_eur numeric(15,4) DEFAULT 0,
    percentual_comissao numeric(5,2),
    valor_comissao numeric(12,2),
    pago boolean DEFAULT false,
    data_pagamento date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: comprovantes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comprovantes (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    venda_id uuid NOT NULL,
    nome_arquivo character varying(255) NOT NULL,
    arquivo_url character varying(500) NOT NULL,
    tipo_arquivo character varying(10) NOT NULL,
    tamanho_bytes bigint,
    aprovado boolean DEFAULT false,
    aprovado_por uuid,
    aprovado_em timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    uploaded_by uuid
);


--
-- Name: envios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.envios (
    id uuid NOT NULL,
    codigo_rastreio character varying(100) NOT NULL,
    status public.envio_status,
    servico_provedor character varying(100),
    ultima_atualizacao timestamp without time zone,
    descricao text,
    destinatario character varying(200),
    origem character varying(200),
    destino character varying(200),
    historico_eventos jsonb,
    cliente_nome character varying(200),
    observacoes text,
    pedido_id uuid,
    data_criacao date,
    ativo boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    created_by uuid
);


--
-- Name: exchange_rates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exchange_rates (
    id uuid NOT NULL,
    currency_pair public.currencypair NOT NULL,
    rate numeric(12,4) NOT NULL,
    source character varying(100),
    is_active boolean,
    notes text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    updated_by character varying(100)
);


--
-- Name: fechamentos_semanais; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fechamentos_semanais (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    semana_inicio date NOT NULL,
    semana_fim date NOT NULL,
    fechado boolean DEFAULT false,
    fechado_em timestamp without time zone,
    fechado_por uuid,
    total_vendas_g numeric(15,4) DEFAULT 0,
    total_vendas_r numeric(15,4) DEFAULT 0,
    total_vendas_u numeric(15,4) DEFAULT 0,
    total_vendas_eur numeric(15,4) DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: folgas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.folgas (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    vendedor_id uuid NOT NULL,
    data date NOT NULL,
    tipo public.tipofolga DEFAULT 'FOLGA'::public.tipofolga,
    periodo character varying(20) DEFAULT 'COMPLETO'::character varying,
    motivo text,
    aprovado boolean DEFAULT false,
    aprovado_por uuid,
    ativo boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: funcionarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.funcionarios (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    nome character varying(100) NOT NULL,
    cpf character varying(14),
    usuario_id uuid,
    cargo character varying(100),
    salario numeric(10,2),
    data_admissao date,
    data_demissao date,
    horarios jsonb,
    telefone character varying(20),
    endereco text,
    ativo boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    cor_calendario character varying(7) DEFAULT '#3B82F6'::character varying
);


--
-- Name: money_transfers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.money_transfers (
    id uuid NOT NULL,
    transfer_date date NOT NULL,
    amount_sent numeric(15,4) NOT NULL,
    thais_fee_percentage numeric(5,2),
    thais_fee_amount numeric(15,4) NOT NULL,
    net_amount numeric(15,4) NOT NULL,
    status public.transferstatus,
    delivery_confirmed_at timestamp without time zone,
    delivery_confirmed_by character varying(100),
    currency character varying(10),
    transfer_method character varying(50),
    reference_number character varying(100),
    notes text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    created_by character varying(100)
);


--
-- Name: pedidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pedidos (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    numero_pedido character varying(50) NOT NULL,
    cliente_nome character varying(200) NOT NULL,
    cliente_telefone character varying(20),
    cliente_email character varying(100),
    endereco_rua character varying(300) NOT NULL,
    endereco_numero character varying(20),
    endereco_complemento character varying(100),
    endereco_bairro character varying(100),
    endereco_cidade character varying(100) NOT NULL,
    endereco_uf character(2) NOT NULL,
    endereco_cep character varying(10) NOT NULL,
    transportadora public.transportadora_tipo NOT NULL,
    codigo_rastreio character varying(100),
    valor_frete numeric(10,2),
    peso_kg numeric(8,3),
    status public.pedido_status DEFAULT 'PENDENTE'::public.pedido_status,
    data_pedido date DEFAULT CURRENT_DATE,
    data_envio date,
    data_entrega date,
    observacoes text,
    instrucoes_entrega text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by uuid,
    data_separacao date,
    data_pagamento date,
    data_conclusao date,
    valor_total numeric(10,2) DEFAULT 0 NOT NULL,
    valor_pago numeric(10,2) DEFAULT 0,
    forma_pagamento character varying(50),
    pago character varying(10) DEFAULT 'NAO'::character varying,
    separado_por uuid,
    prioridade character varying(10) DEFAULT 'NORMAL'::character varying
);


--
-- Name: pontos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pontos (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    funcionario_id uuid NOT NULL,
    data_ponto date NOT NULL,
    entrada_manha time without time zone,
    saida_almoco time without time zone,
    entrada_tarde time without time zone,
    saida_noite time without time zone,
    horas_trabalhadas interval,
    horas_extras interval,
    observacoes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by uuid
);


--
-- Name: rastreamentos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rastreamentos (
    id uuid NOT NULL,
    codigo_rastreio character varying(100) NOT NULL,
    status public.rastreamento_status,
    servico_provedor character varying(100),
    ultima_atualizacao timestamp without time zone,
    descricao text,
    destinatario character varying(200),
    origem character varying(200),
    destino character varying(200),
    historico_eventos jsonb,
    pedido_id uuid,
    data_criacao date,
    ativo boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    created_by uuid
);


--
-- Name: seq_pedido_numero; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seq_pedido_numero
    START WITH 1000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    nome character varying(100) NOT NULL,
    email character varying(100) NOT NULL,
    senha_hash character varying(255) NOT NULL,
    role public.usuario_role DEFAULT 'VENDEDOR'::public.usuario_role NOT NULL,
    ativo boolean DEFAULT true,
    ultimo_login timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vendas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendas (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    data_venda date DEFAULT CURRENT_DATE NOT NULL,
    vendedor_id uuid NOT NULL,
    moeda public.moeda_tipo NOT NULL,
    valor_bruto numeric(15,4) NOT NULL,
    metodo_pagamento public.pagamento_metodo NOT NULL,
    cambista_id uuid,
    taxa_cambio_usada numeric(8,4),
    valor_cambista numeric(15,4),
    valor_liquido numeric(15,4) NOT NULL,
    descricao_produto text,
    observacoes text,
    semana_fechamento date,
    fechado boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by uuid,
    taxa_desconto_pagamento numeric(5,4) DEFAULT '0'::numeric,
    pending_transfer_id uuid,
    requires_thais_transfer boolean DEFAULT false
);


--
-- Name: vendedores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendedores (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    nome character varying(100) NOT NULL,
    usuario_id uuid,
    taxa_comissao numeric(5,2) DEFAULT 10.00,
    meta_semanal numeric(12,2) DEFAULT 0,
    conta_bancaria character varying(50),
    telefone character varying(20),
    ativo boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    cor_calendario character varying(7) DEFAULT '#3B82F6'::character varying
);


--
-- Name: vw_vendas_por_vendedor; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_vendas_por_vendedor AS
 SELECT v.nome AS vendedor,
    vd.data_venda,
    vd.moeda,
    sum(vd.valor_bruto) AS total_bruto,
    sum(vd.valor_liquido) AS total_liquido,
    count(*) AS quantidade_vendas
   FROM (public.vendas vd
     JOIN public.vendedores v ON ((vd.vendedor_id = v.id)))
  GROUP BY v.nome, vd.data_venda, vd.moeda
  ORDER BY vd.data_venda DESC;


--
-- Name: vw_vendas_semana_atual; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_vendas_semana_atual AS
 SELECT v.nome AS vendedor,
    vd.moeda,
    sum(vd.valor_bruto) AS total_bruto,
    sum(vd.valor_liquido) AS total_liquido,
    count(*) AS quantidade
   FROM (public.vendas vd
     JOIN public.vendedores v ON ((vd.vendedor_id = v.id)))
  WHERE ((vd.data_venda >= date_trunc('week'::text, (CURRENT_DATE)::timestamp with time zone)) AND (vd.data_venda < (date_trunc('week'::text, (CURRENT_DATE)::timestamp with time zone) + '7 days'::interval)))
  GROUP BY v.nome, vd.moeda
  ORDER BY v.nome, vd.moeda;


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
9572ac0c4129
\.


--
-- Data for Name: cambistas; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.cambistas (id, nome, taxa_g_para_r, taxa_u_para_r, taxa_eur_para_r, conta_bancaria, telefone, ativo, observacoes, created_at, updated_at) FROM stdin;
cff146d6-e781-4de1-8456-8aa8264f85d2	Cambista Principal	5.6500	5.5000	6.2000	\N	\N	t	\N	2025-08-03 21:50:00.57657	2025-08-03 21:50:00.57657
77be4479-74ea-4590-97ed-5e5d3d2230d1	Casa de Câmbio Central	5.6500	5.5000	6.2000	987654-3	11955555555	t	\N	2025-08-04 23:25:31.282224	2025-08-04 23:25:31.282224
9aae2643-498f-4a16-a888-48a41185dbbc	Câmbio Express	5.7000	5.4500	6.1500	876543-2	11944444444	t	\N	2025-08-04 23:25:31.283795	2025-08-04 23:25:31.283795
\.


--
-- Data for Name: comissoes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.comissoes (id, fechamento_id, vendedor_id, total_g, total_r, total_u, total_eur, percentual_comissao, valor_comissao, pago, data_pagamento, created_at) FROM stdin;
\.


--
-- Data for Name: comprovantes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.comprovantes (id, venda_id, nome_arquivo, arquivo_url, tipo_arquivo, tamanho_bytes, aprovado, aprovado_por, aprovado_em, created_at, uploaded_by) FROM stdin;
\.


--
-- Data for Name: envios; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.envios (id, codigo_rastreio, status, servico_provedor, ultima_atualizacao, descricao, destinatario, origem, destino, historico_eventos, cliente_nome, observacoes, pedido_id, data_criacao, ativo, created_at, updated_at, created_by) FROM stdin;
\.


--
-- Data for Name: exchange_rates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.exchange_rates (id, currency_pair, rate, source, is_active, notes, created_at, updated_at, updated_by) FROM stdin;
571468ac-336b-440c-b8eb-c6039eb464ae	EUR_TO_USD	1.0850	Dashboard	t	Updated from dashboard	2025-08-09 23:35:43.143585	2025-08-10 20:05:46.774298	Administrador
724a8ef2-7469-4e90-81b0-c93fe78de5bd	EUR_TO_BRL	6.2000	Dashboard	f	Updated from dashboard	2025-08-07 21:59:02.876358	2025-08-08 19:54:06.205671	Administrador
f30df410-4976-403b-b09b-5482aac88302	USD_TO_PYG	7500.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:54:06.205671	2025-08-08 19:54:22.918799	Administrador
09508adb-8a5e-4023-bc74-6f02f9192220	USD_TO_BRL	5.6500	Dashboard	f	Updated from dashboard	2025-08-08 19:54:06.205671	2025-08-08 19:54:22.918799	Administrador
ceed2701-f1df-47ad-aa41-00179dd10c14	USD_TO_BRL	5.9000	Painel de Gerenciamento	f		2025-08-09 22:37:09.038273	2025-08-11 22:37:52.459888	Administrador
bcdd79d2-a978-486a-b3fe-66078e3dfd5e	EUR_TO_BRL	6.2000	Dashboard	f	Updated from dashboard	2025-08-08 19:54:06.205671	2025-08-08 19:54:22.918799	Administrador
af7b49df-808c-465b-b781-668c25e6a1d4	USD_TO_PYG	7500.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:54:22.918799	2025-08-08 19:55:10.738122	Administrador
3c460ae4-abad-4e6a-bb48-178907a52508	USD_TO_BRL	5.8500	Dashboard	f	Updated from dashboard	2025-08-08 19:54:22.918799	2025-08-08 19:55:10.738122	Administrador
15d47ca4-7803-44f6-8e9a-34a64294e995	EUR_TO_BRL	6.2000	Dashboard	f	Updated from dashboard	2025-08-08 19:54:22.918799	2025-08-08 19:55:10.738122	Administrador
fb142eff-9e45-4b48-8da8-0de6fd37c27a	USD_TO_PYG	7500.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:10.738122	2025-08-08 19:55:16.902447	Administrador
dc08100e-0c6d-4b21-926d-02a12a27eb65	USD_TO_BRL	5.5700	Dashboard	f	Updated from dashboard	2025-08-08 19:55:10.738122	2025-08-08 19:55:16.902447	Administrador
d401252e-f009-481e-9c34-d34695e892c4	USD_TO_PYG	7500.0000	Manual Entry	f	Taxa atual USD para Guarani	2025-08-07 21:47:29.755298	2025-08-07 21:49:42.897575	System
b9bc92d0-5f60-4a0c-b664-af24dbcbc505	USD_TO_BRL	5.8500	Manual Entry	f	Taxa atual USD para BRL	2025-08-07 21:47:29.755298	2025-08-07 21:49:42.897575	System
4dbad2c7-588c-4b46-b952-59f92177605c	USD_TO_BRL	5.8000	Management Panel	f		2025-08-11 22:37:52.459888	2025-08-19 18:20:22.317126	Administrador
df9cbbd9-0b11-494c-9bbb-653b69b31301	EUR_TO_BRL	6.2000	Manual Entry	f	Taxa atual EUR para BRL	2025-08-07 21:47:29.755298	2025-08-07 21:49:42.897575	System
f47b7186-8486-4793-b65b-6b5d3c913b9d	USD_TO_PYG	7500.0000	Test Script	f	Teste automatizado do sistema	2025-08-07 21:49:42.897575	2025-08-07 21:55:46.854813	Test Admin
bdeabb2b-7b36-41e9-8968-0e5992e8594b	USD_TO_BRL	5.8500	Test Script	f	Teste automatizado do sistema	2025-08-07 21:49:42.897575	2025-08-07 21:55:46.854813	Test Admin
5b39ae1d-c4ee-4ca6-82c7-ddcc0bf8375c	USD_TO_PYG	6400.0000	Dashboard	t	Updated from dashboard	2025-08-09 22:37:09.038273	2025-08-19 18:20:22.317126	Administrador
ee3ec0b6-dd34-4026-afe1-4a19066d9ce1	EUR_TO_BRL	6.2000	Test Script	f	Teste automatizado do sistema	2025-08-07 21:49:42.897575	2025-08-07 21:55:46.854813	Test Admin
5380a613-c1f8-40da-a121-8ea2811e5d47	USD_TO_PYG	7500.0000	Test Script	f	Teste automatizado do sistema	2025-08-07 21:55:46.854813	2025-08-07 21:59:02.876358	Test Admin
19bbaab5-5dc2-441b-b4be-c8dc2cdf1392	USD_TO_BRL	5.8500	Test Script	f	Teste automatizado do sistema	2025-08-07 21:55:46.854813	2025-08-07 21:59:02.876358	Test Admin
d095ade0-d652-4e69-811e-1f6af8f4bda0	USD_TO_BRL	5.4500	Dashboard	t	Updated from dashboard	2025-08-19 18:20:22.317126	2025-08-19 18:20:22.317126	Administrador
c7b806f4-32aa-4ef3-8f37-985eb5cdd8f4	EUR_TO_BRL	6.2000	Test Script	f	Teste automatizado do sistema	2025-08-07 21:55:46.854813	2025-08-07 21:59:02.876358	Test Admin
6614a0db-f288-46f9-a019-32ba7a04c885	USD_TO_PYG	7500.0000	Dashboard	f	Updated from dashboard	2025-08-07 21:59:02.876358	2025-08-08 19:54:06.205671	Administrador
cf713b2e-ce4a-48f9-8f33-a6aac0a85da2	USD_TO_BRL	5.6500	Dashboard	f	Updated from dashboard	2025-08-07 21:59:02.876358	2025-08-08 19:54:06.205671	Administrador
86acd0aa-36a5-4006-96fe-962b5f2669bc	EUR_TO_BRL	6.2000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:10.738122	2025-08-08 19:55:16.902447	Administrador
e00a9376-0fed-45c6-bfb8-a891117bfd00	USD_TO_PYG	7600.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:16.902447	2025-08-08 19:55:55.92117	Administrador
f8dca08c-0c99-477c-b8bb-fdb974792264	USD_TO_BRL	5.5700	Dashboard	f	Updated from dashboard	2025-08-08 19:55:16.902447	2025-08-08 19:55:55.92117	Administrador
d0fc129c-703a-472a-a4cc-6ceb90423712	EUR_TO_BRL	6.2000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:16.902447	2025-08-08 19:55:55.92117	Administrador
90080f07-1313-41a7-aebf-891772ddf7f9	USD_TO_PYG	7600.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:55.92117	2025-08-08 20:11:09.888334	Administrador
13f9e7e3-22b9-4355-adde-fc6472895901	USD_TO_BRL	5.2000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:55.92117	2025-08-08 20:11:09.888334	Administrador
42489b9e-4cd0-487c-9429-6d98f1193278	EUR_TO_BRL	6.2000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:55.92117	2025-08-08 20:11:09.888334	Administrador
9dd4e97e-6d69-4f5c-ae93-ea6d2e982e21	USD_TO_PYG	7600.0000	Dashboard	f	Updated from dashboard	2025-08-08 20:11:09.888334	2025-08-09 19:44:31.070351	Administrador
10e1b1d1-8091-4d92-ac19-b0a0fe990d4f	USD_TO_BRL	5.6000	Dashboard	f	Updated from dashboard	2025-08-08 20:11:09.888334	2025-08-09 19:44:31.070351	Administrador
fdaeda9f-531a-4305-a37a-14d18ef1c92e	EUR_TO_BRL	6.2000	Dashboard	f	Updated from dashboard	2025-08-08 20:11:09.888334	2025-08-09 19:44:31.070351	Administrador
590fe2ab-d73d-4973-8cd8-2c646c724b0f	USD_TO_PYG	7600.0000	Dashboard	f	Updated from dashboard	2025-08-09 19:44:31.070351	2025-08-09 22:37:09.038273	Administrador
5316f7cb-0a8f-4fda-9409-4bebe63a6c93	USD_TO_BRL	5.8500	Dashboard	f	Updated from dashboard	2025-08-09 19:44:31.070351	2025-08-09 22:37:09.038273	Administrador
cffee696-ad60-49ba-b9ad-507cd11b6d8b	EUR_TO_BRL	6.2000	Dashboard	f	Updated from dashboard	2025-08-09 19:44:31.070351	2025-08-09 22:37:09.038273	Administrador
4510d682-f84c-4414-b61a-d554f23dc2c2	EUR_TO_BRL	6.2000	Dashboard	t	Updated from dashboard	2025-08-09 22:37:09.038273	2025-08-09 22:37:09.038273	Administrador
931eea1d-9721-42f4-9009-30e80cff9109	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-07 21:59:02.876358	2025-08-09 23:35:43.143585	Administrador
05fe1304-bfb6-4a1e-87e5-159d8ceeb7d9	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:54:06.205671	2025-08-09 23:35:43.143585	Administrador
67277558-382a-44be-96c9-6d39b1f0f4bb	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:54:22.918799	2025-08-09 23:35:43.143585	Administrador
fc4b30f7-1187-467b-9916-7f6349b7f37f	EUR_TO_PYG	8200.0000	Manual Entry	f	Taxa atual EUR para Guarani	2025-08-07 21:47:29.755298	2025-08-09 23:35:43.143585	System
fb818d40-efde-4770-a058-09c9d5715b51	EUR_TO_PYG	8200.0000	Test Script	f	Teste automatizado do sistema	2025-08-07 21:49:42.897575	2025-08-09 23:35:43.143585	Test Admin
b59162a4-b419-4310-9441-22661455298b	EUR_TO_PYG	8200.0000	Test Script	f	Teste automatizado do sistema	2025-08-07 21:55:46.854813	2025-08-09 23:35:43.143585	Test Admin
3d786197-0b84-4709-ac01-966775892a5a	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:10.738122	2025-08-09 23:35:43.143585	Administrador
daad75d8-c080-4f87-a293-c2c4ca456ca5	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:16.902447	2025-08-09 23:35:43.143585	Administrador
f691537d-4d37-4520-b21f-3b07059adc67	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-08 19:55:55.92117	2025-08-09 23:35:43.143585	Administrador
d09a6efe-7088-4ea5-80c2-8ce0587c1ed4	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-08 20:11:09.888334	2025-08-09 23:35:43.143585	Administrador
987c852d-3f3a-4a7b-93ba-85abc7058e9f	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-09 19:44:31.070351	2025-08-09 23:35:43.143585	Administrador
d9ae9890-044d-45b7-8f0d-7786a812b48b	EUR_TO_PYG	8200.0000	Dashboard	f	Updated from dashboard	2025-08-09 22:37:09.038273	2025-08-09 23:35:43.143585	Administrador
\.


--
-- Data for Name: fechamentos_semanais; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fechamentos_semanais (id, semana_inicio, semana_fim, fechado, fechado_em, fechado_por, total_vendas_g, total_vendas_r, total_vendas_u, total_vendas_eur, created_at) FROM stdin;
\.


--
-- Data for Name: folgas; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.folgas (id, vendedor_id, data, tipo, periodo, motivo, aprovado, aprovado_por, ativo, created_at, updated_at) FROM stdin;
2454e8f7-1d3d-4420-ba79-a9008c1ded6e	a0491166-dd55-4c44-814e-248f52e65755	2025-08-24	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
b82fe931-623e-4315-85f1-ee915312f00c	a0491166-dd55-4c44-814e-248f52e65755	2025-08-25	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
12a97003-fdef-432c-a286-549f7f02ec1c	a0491166-dd55-4c44-814e-248f52e65755	2025-08-26	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
4e402ff4-18b7-4394-871d-76e1e22be3b9	a0491166-dd55-4c44-814e-248f52e65755	2025-08-27	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
7a5552d7-45ba-4319-8049-8744d91d1114	a0491166-dd55-4c44-814e-248f52e65755	2025-08-28	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
1709a99f-3edc-4473-b47c-d36c212c979c	a0491166-dd55-4c44-814e-248f52e65755	2025-08-29	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
3e7d8db7-4586-4380-b593-a877ae28aa4a	a0491166-dd55-4c44-814e-248f52e65755	2025-08-30	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
5a65faa9-eb79-46d5-9ee3-abb6c0f084bb	a0491166-dd55-4c44-814e-248f52e65755	2025-08-31	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
20731964-e68d-4ef4-a5d6-e5b34cb390cd	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-08-24	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
ac1051df-9242-49e4-91bf-6bcb71cb413b	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-08-25	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
a45f20da-8225-438d-8898-7acff6283e40	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-08-26	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
43fd1d83-b54e-421d-9568-2fc76eb22546	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-08-27	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
7f538d40-2bed-4b6b-8691-0fe9d7057cc3	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-08-28	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
21adac60-e749-4967-8e46-a10e158ec557	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-08-29	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
bcd6c8a2-45d5-4fd0-b752-5fb9b262f6d8	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-08-30	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
20c58966-4843-4be2-ba2a-468d6336eb4c	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-08-31	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	t	2025-09-03 21:31:44.767274	2025-09-03 21:31:44.767274
265bc8fa-4975-4c75-b6de-2587e89a171b	57180009-1a3f-437d-9401-bdfb1ffed375	2025-09-03	FOLGA	COMPLETO	\N	t	\N	t	2025-09-03 22:06:32.640119	2025-09-03 22:06:46.274873
46eaa559-8c60-4b62-b02a-827fede4e135	a0491166-dd55-4c44-814e-248f52e65755	2025-09-01	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:15.944521
ca2c9349-3add-4ece-a462-c6e2c22bbda3	a0491166-dd55-4c44-814e-248f52e65755	2025-09-02	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:18.377633
bbd714c8-c4ff-481f-b040-8cadec1607e4	a0491166-dd55-4c44-814e-248f52e65755	2025-09-04	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:21.352342
97f747b3-d1fd-4fae-8f6c-60881054f4cf	a0491166-dd55-4c44-814e-248f52e65755	2025-09-05	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:23.036144
652d00d6-c5ef-4e3f-a290-5dd9860e7f74	a0491166-dd55-4c44-814e-248f52e65755	2025-09-06	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:24.702006
e159836c-4be7-4a2c-ac0d-ccc5e3a1f972	a0491166-dd55-4c44-814e-248f52e65755	2025-09-03	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:27.768553
2ab2d034-3ce8-4197-ac11-b1713acc3818	35d0522b-83ca-41d3-8e1e-1c6b742807c4	2025-09-01	FERIAS	MANHA	Folga de exemplo para Wiss	t	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:29.851648
dc23da64-9c46-4545-acb4-745a9f395b65	a0491166-dd55-4c44-814e-248f52e65755	2025-09-07	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:32.152604
1d012f69-893a-44e1-bded-f515295bf230	a0491166-dd55-4c44-814e-248f52e65755	2025-09-08	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:33.970051
551221d6-9b04-4af6-b942-e3f3f0c63443	a0491166-dd55-4c44-814e-248f52e65755	2025-09-09	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:35.998135
0596fda3-9928-4495-a65a-10b1c75156e5	a0491166-dd55-4c44-814e-248f52e65755	2025-09-10	FOLGA	COMPLETO	Folga de exemplo para Sol	t	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:41.145395
b09f4380-4c57-498a-ac18-586c44c57464	a0491166-dd55-4c44-814e-248f52e65755	2025-09-11	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:42.751932
c9fbdc91-2570-4af9-8049-c587f2b69585	a0491166-dd55-4c44-814e-248f52e65755	2025-09-12	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:44.187612
fb2efa10-efa2-4aea-b40f-d16696b6e833	a0491166-dd55-4c44-814e-248f52e65755	2025-09-13	FOLGA	COMPLETO	Folga de exemplo para Sol	f	\N	f	2025-09-03 21:31:44.767274	2025-09-03 22:07:45.614751
225513c6-2d81-4e72-88f2-a0fe63b20e8a	a0491166-dd55-4c44-814e-248f52e65755	2025-09-14	FOLGA	COMPLETO	\N	f	\N	f	2025-09-03 21:32:17.690904	2025-09-03 22:07:47.985274
034ab2f9-d128-4dbb-892b-c8e11aa8ad34	57180009-1a3f-437d-9401-bdfb1ffed375	2025-09-04	FOLGA	COMPLETO	\N	t	\N	t	2025-09-03 22:16:28.538927	2025-09-03 22:16:31.970942
\.


--
-- Data for Name: funcionarios; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.funcionarios (id, nome, cpf, usuario_id, cargo, salario, data_admissao, data_demissao, horarios, telefone, endereco, ativo, created_at, updated_at, cor_calendario) FROM stdin;
ac1a11f2-4329-40a4-ae4e-301bae94deec	Ana Silva	123.456.789-01	91c70214-bc82-4c52-b440-466ca6733e8f	Gerente de Loja	3500.00	2024-01-15	\N	\N	11987654321	Rua das Flores, 123 - São Paulo, SP	t	2025-08-05 19:49:45.784606	2025-08-05 19:49:45.784606	#3B82F6
2f07ac66-5449-415a-b712-9a460e2ddb00	Carlos Santos	987.654.321-01	f1029c04-a9ba-4c80-be08-01e319d26ebf	Auxiliar de Limpeza	1500.00	2024-02-01	\N	\N	11976543210	Av. Central, 456 - São Paulo, SP	t	2025-08-05 19:49:45.789635	2025-08-05 19:49:45.789635	#3B82F6
209f2376-7f9a-460a-a0ca-a60c0f650e20	Lucas Adriano Ferreira Gimenez	107.006.749-00	\N	Gerente	3000.00	\N	\N	\N	(45) 99953-2052	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#3B82F6
10d66401-8744-4192-8683-831688013757	Denis Christopher	234.567.890-12	\N	Vendedor	2500.00	\N	\N	\N	(11) 98765-4322	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#EF4444
695390ab-8a6f-4512-9a54-8d99b32c0d9d	Junior Favretto	345.678.901-23	\N	Vendedor	4500.00	\N	\N	\N	(11) 98765-4323	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#10B981
9483a97d-5af8-4930-9210-5aa4e523c88a	Sol Perez	456.789.012-34	\N	Vendedor	2000.00	\N	\N	\N	(11) 98765-4324	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#F59E0B
7b5c2582-16b7-4807-a5aa-b471e1356f75	Lourdes	567.890.123-45	\N	Supervisora de Limpeza	3500.00	\N	\N	\N	(11) 98765-4325	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#8B5CF6
\.


--
-- Data for Name: money_transfers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.money_transfers (id, transfer_date, amount_sent, thais_fee_percentage, thais_fee_amount, net_amount, status, delivery_confirmed_at, delivery_confirmed_by, currency, transfer_method, reference_number, notes, created_at, updated_at, created_by) FROM stdin;
\.


--
-- Data for Name: pedidos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pedidos (id, numero_pedido, cliente_nome, cliente_telefone, cliente_email, endereco_rua, endereco_numero, endereco_complemento, endereco_bairro, endereco_cidade, endereco_uf, endereco_cep, transportadora, codigo_rastreio, valor_frete, peso_kg, status, data_pedido, data_envio, data_entrega, observacoes, instrucoes_entrega, created_at, updated_at, created_by, data_separacao, data_pagamento, data_conclusao, valor_total, valor_pago, forma_pagamento, pago, separado_por, prioridade) FROM stdin;
245f7183-62ca-46bc-b93e-a474105e6668	PED-001	João Silva	(11) 99999-0001	joao.silva@email.com	Rua das Flores, 123	123	\N	Centro	São Paulo	SP	01234-567	CORREIOS	BR123456789	15.50	1.200	VENDIDO	2025-08-27	\N	\N	Cliente solicitou entrega rápida	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	\N	\N	\N	150.00	0.00	PIX	NAO	\N	ALTA
6083e915-f280-4d3b-80e2-100db398a55f	PED-002	Maria Santos	(11) 99999-0002	maria.santos@email.com	Av. Paulista, 1000	1000	\N	Bela Vista	São Paulo	SP	01310-100	AZUL_CARGO	AC987654321	25.00	2.500	SEPARANDO	2025-08-27	\N	\N	Pedido especial VIP	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	2025-08-27	\N	\N	280.50	280.50	CARTAO	SIM	\N	URGENTE
345d9e7a-f438-4f1e-94b4-db8cd34cc7ee	PED-003	Carlos Oliveira	(21) 99999-0003	carlos.oliveira@email.com	Rua Copacabana, 456	456	\N	Copacabana	Rio de Janeiro	RJ	22070-000	CORREIOS	BR555666777	18.90	1.800	SEPARADO_PAGO	2025-08-27	\N	\N	\N	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	2025-08-27	2025-08-27	\N	320.00	320.00	PIX	SIM	1db754f2-7d80-4f87-8b1f-3b501775c4ab	NORMAL
a443a94f-fd98-4a0d-9ec0-7d7f14ce338a	PED-004	Ana Costa	(31) 99999-0004	ana.costa@email.com	Rua da Liberdade, 789	789	\N	Centro	Belo Horizonte	MG	30112-000	SUPERFRETE	SF111222333	22.00	3.000	SEPARADO_NAO_PAGO	2025-08-27	\N	\N	Aguardando pagamento do boleto	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	2025-08-27	\N	\N	450.75	0.00	BOLETO	NAO	1db754f2-7d80-4f87-8b1f-3b501775c4ab	NORMAL
9ed1bb60-3d56-4da7-a698-0421a15c22ea	PED-005	Pedro Ferreira	(85) 99999-0005	pedro.ferreira@email.com	Av. Beira Mar, 321	321	\N	Meireles	Fortaleza	CE	60165-121	CORREIOS	BR999888777	30.00	2.200	ENTREGUE	2025-08-27	2025-08-27	2025-08-27	\N	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	2025-08-27	2025-08-27	\N	199.90	199.90	CARTAO	SIM	1db754f2-7d80-4f87-8b1f-3b501775c4ab	BAIXA
\.


--
-- Data for Name: pontos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pontos (id, funcionario_id, data_ponto, entrada_manha, saida_almoco, entrada_tarde, saida_noite, horas_trabalhadas, horas_extras, observacoes, created_at, created_by) FROM stdin;
\.


--
-- Data for Name: rastreamentos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.rastreamentos (id, codigo_rastreio, status, servico_provedor, ultima_atualizacao, descricao, destinatario, origem, destino, historico_eventos, pedido_id, data_criacao, ativo, created_at, updated_at, created_by) FROM stdin;
6027c71c-bf0d-4e69-b13a-7d9165ab12ce	AC957865542BR	ENTREGUE	linkcorreios	2025-08-17 17:27:09.634065	\N	\N	\N	\N	[{"data": "17/08/2025 17:27", "local": "", "origem": null, "destino": null, "detalhes": "Objeto -", "situacao": "Objeto -"}]	\N	2025-08-17	f	2025-08-17 17:27:09.155138	2025-08-17 17:32:27.248431	1db754f2-7d80-4f87-8b1f-3b501775c4ab
f9be4eb1-dc0d-4b14-9643-2fee3a5f1ad0	AC958117356BR	ENTREGUE	linkcorreios	2025-08-17 17:26:36.184311	\N	\N	\N	\N	[{"data": "17/08/2025 17:26", "local": "", "origem": null, "destino": null, "detalhes": "Objeto -", "situacao": "Objeto -"}]	\N	2025-08-17	f	2025-08-17 17:26:35.688869	2025-08-17 17:32:28.870007	1db754f2-7d80-4f87-8b1f-3b501775c4ab
99e2a9b5-3db1-48fb-87ad-f9ff6cbcab48	OY589707119BR	PENDENTE	linkcorreios	2025-08-13 00:31:21.552825	\N	\N	\N	\N	[]	\N	2025-08-12	f	2025-08-12 23:41:35.413597	2025-08-13 00:55:02.556296	1db754f2-7d80-4f87-8b1f-3b501775c4ab
ad0abedf-7c9b-49eb-ba2b-11e206a36d01	OY559435068BR	ENTREGUE	linkcorreios	2025-08-17 17:26:02.297807	\N	\N	\N	\N	[{"data": "17/08/2025 17:26", "local": "", "origem": null, "destino": null, "detalhes": "Objeto -", "situacao": "Objeto -"}]	\N	2025-08-13	f	2025-08-13 00:28:33.951874	2025-08-17 17:32:30.395911	1db754f2-7d80-4f87-8b1f-3b501775c4ab
a5cbcb08-5571-4700-8a25-2ad8a808174b	OY589706250BR	ENTREGUE	linkcorreios	2025-08-17 17:26:02.297765	\N	\N	\N	\N	[{"data": "17/08/2025 17:26", "local": "", "origem": null, "destino": null, "detalhes": "Objeto -", "situacao": "Objeto -"}]	\N	2025-08-13	f	2025-08-13 00:28:03.208685	2025-08-17 17:32:32.129387	1db754f2-7d80-4f87-8b1f-3b501775c4ab
7cc0607f-0527-4245-bc85-03d33e0957cf	AC950573845BR	PENDENTE	correios_website	2025-08-17 16:52:40.354587	\N	\N	\N	\N	[]	\N	2025-08-17	f	2025-08-17 16:52:38.920435	2025-08-17 16:55:41.748562	1db754f2-7d80-4f87-8b1f-3b501775c4ab
1a50b35f-0db1-4341-86a5-038a7386f986	AM822099295BR	PENDENTE	correios_website	2025-08-17 17:14:34.281569	\N	\N	\N	\N	[]	\N	2025-08-17	f	2025-08-17 16:51:44.987059	2025-08-17 17:23:48.374033	1db754f2-7d80-4f87-8b1f-3b501775c4ab
8920a102-4654-46bc-a39d-f8647c5d18df	AC950973423BR	ENTREGUE	linkcorreios	2025-08-19 18:18:35.718895	Camisetas	Anderson Faria Silva	Foz	SP	[]	\N	2025-08-17	t	2025-08-17 17:34:11.245304	2025-08-28 18:53:23.943763	1db754f2-7d80-4f87-8b1f-3b501775c4ab
9759f6a4-79a7-48a5-9560-e609ec93cb7e	AC958114099BR	EM_TRANSITO	linkcorreios	2025-08-19 18:18:35.718833	\N	\N	\N	\N	[]	\N	2025-08-17	t	2025-08-17 21:09:09.668375	2025-08-28 18:53:27.922088	1db754f2-7d80-4f87-8b1f-3b501775c4ab
bed26efb-8f7f-46df-ab89-8f1c48d98055	AC950605565BR	ENTREGUE	linkcorreios	2025-08-19 18:18:35.718862	\N	\N	\N	\N	[]	\N	2025-08-17	t	2025-08-17 17:33:48.52633	2025-08-26 22:23:21.962508	1db754f2-7d80-4f87-8b1f-3b501775c4ab
d79aa1e9-5b84-4bd8-94a0-ab74954fe4af	AC950668168BR	EM_TRANSITO	linkcorreios	2025-08-19 18:18:35.718878	\N	\N	\N	\N	[]	\N	2025-08-17	t	2025-08-17 21:09:32.076826	2025-08-28 18:54:35.489296	1db754f2-7d80-4f87-8b1f-3b501775c4ab
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.usuarios (id, nome, email, senha_hash, role, ativo, ultimo_login, created_at, updated_at) FROM stdin;
542e05b5-6a0d-4186-bba9-8810089bafb6	João Silva	joao@loja.com	$2b$12$emhohGRigur59IgI0FyCkOU8p98v3uLpTQwr091c2s77FsXrOmGaq	GERENTE	t	\N	2025-08-04 23:24:26.767431	2025-08-04 23:24:26.767431
91c70214-bc82-4c52-b440-466ca6733e8f	Maria Santos	maria@loja.com	$2b$12$SYfiTXFv5Tu0gvRtygIv2eWhRJSFuchHuXkf1tZBBT789y7yupSNq	VENDEDOR	t	\N	2025-08-04 23:24:26.956192	2025-08-04 23:24:26.956192
f1029c04-a9ba-4c80-be08-01e319d26ebf	Carlos Oliveira	carlos@loja.com	$2b$12$zmWE72YIgGtmVPh9WFnHUO6S.rqLFaV/ySoqsPe1F508QsK9LdT/6	LIMPEZA	t	2025-08-05 02:43:18.109345	2025-08-04 23:24:27.124804	2025-08-05 19:49:41.052132
1db754f2-7d80-4f87-8b1f-3b501775c4ab	Administrador	admin@loja.com	$2b$12$vG.shwiROZz7xX5fJ.Zl3OibD0jbq9W/VqIvvxiqrRIqL/1M.IB3m	ADMIN	t	2025-09-03 23:45:32.265356	2025-08-03 21:50:00.57657	2025-09-03 20:45:32.055644
\.


--
-- Data for Name: vendas; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.vendas (id, data_venda, vendedor_id, moeda, valor_bruto, metodo_pagamento, cambista_id, taxa_cambio_usada, valor_cambista, valor_liquido, descricao_produto, observacoes, semana_fechamento, fechado, created_at, updated_at, created_by, taxa_desconto_pagamento, pending_transfer_id, requires_thais_transfer) FROM stdin;
e8036da5-6fa6-4a50-b887-d3ec0550bb7e	2025-08-05	dda6b75c-717d-48be-a823-66b61d17e222	R$	150.0000	PIX_POWER	\N	\N	\N	150.0000	Camiseta básica	\N	\N	f	2025-08-05 19:54:25.710577	2025-08-05 19:54:25.710577	542e05b5-6a0d-4186-bba9-8810089bafb6	0.0000	\N	f
d2b6f55d-81ec-4b99-a8c2-e7f246b5ab2d	2025-08-05	dda6b75c-717d-48be-a823-66b61d17e222	G$	25.0000	CREDITO	77be4479-74ea-4590-97ed-5e5d3d2230d1	5.6500	141.2500	141.2500	Calça jeans	\N	\N	f	2025-08-05 19:54:25.715249	2025-08-05 19:54:25.715249	542e05b5-6a0d-4186-bba9-8810089bafb6	0.0000	\N	f
404990a7-52b6-4fa4-82f7-d2557c0fa1e8	2025-08-05	dda6b75c-717d-48be-a823-66b61d17e222	R$	150.0000	PIX_POWER	\N	\N	\N	150.0000	Camiseta básica	\N	\N	f	2025-08-05 19:56:38.127912	2025-08-05 19:56:38.127912	542e05b5-6a0d-4186-bba9-8810089bafb6	0.0000	\N	f
d2c5f85f-83cb-4a35-981a-50529d632495	2025-08-05	dda6b75c-717d-48be-a823-66b61d17e222	G$	25.0000	CREDITO	77be4479-74ea-4590-97ed-5e5d3d2230d1	5.6500	141.2500	141.2500	Calça jeans	\N	\N	f	2025-08-05 19:56:38.132073	2025-08-05 19:56:38.132073	542e05b5-6a0d-4186-bba9-8810089bafb6	0.0000	\N	f
\.


--
-- Data for Name: vendedores; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.vendedores (id, nome, usuario_id, taxa_comissao, meta_semanal, conta_bancaria, telefone, ativo, created_at, updated_at, cor_calendario) FROM stdin;
c0a69ae4-0ab9-4def-b70a-7217ad1fe230	José Santos	f1029c04-a9ba-4c80-be08-01e319d26ebf	15.00	3000.00	234567-8	11976543210	f	2025-08-04 23:25:31.279988	2025-08-28 23:20:52.127984	#3B82F6
dda6b75c-717d-48be-a823-66b61d17e222	Maria Vendedora	91c70214-bc82-4c52-b440-466ca6733e8f	12.50	2500.00	123456-7	11987654321	f	2025-08-04 23:25:31.275162	2025-08-28 23:21:00.355325	#3B82F6
32dbeb18-bbd0-4aec-bbd2-812a4996cd83	Denis	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 21:31:44.767274	#3B82F6
a0491166-dd55-4c44-814e-248f52e65755	Sol	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 21:31:44.767274	#F59E0B
35d0522b-83ca-41d3-8e1e-1c6b742807c4	Wiss	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 21:31:44.767274	#8B5CF6
e2ebb4af-1387-401b-98ed-c8d7c1bd81c1	Lucas	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 21:31:44.767274	#10B981
57180009-1a3f-437d-9401-bdfb1ffed375	Junior	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 22:16:02.240341	#e392fe
\.


--
-- Name: seq_pedido_numero; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.seq_pedido_numero', 1000, false);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: cambistas cambistas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cambistas
    ADD CONSTRAINT cambistas_pkey PRIMARY KEY (id);


--
-- Name: comissoes comissoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comissoes
    ADD CONSTRAINT comissoes_pkey PRIMARY KEY (id);


--
-- Name: comprovantes comprovantes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprovantes
    ADD CONSTRAINT comprovantes_pkey PRIMARY KEY (id);


--
-- Name: envios envios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.envios
    ADD CONSTRAINT envios_pkey PRIMARY KEY (id);


--
-- Name: exchange_rates exchange_rates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exchange_rates
    ADD CONSTRAINT exchange_rates_pkey PRIMARY KEY (id);


--
-- Name: fechamentos_semanais fechamentos_semanais_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fechamentos_semanais
    ADD CONSTRAINT fechamentos_semanais_pkey PRIMARY KEY (id);


--
-- Name: folgas folgas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folgas
    ADD CONSTRAINT folgas_pkey PRIMARY KEY (id);


--
-- Name: folgas folgas_vendedor_id_data_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folgas
    ADD CONSTRAINT folgas_vendedor_id_data_key UNIQUE (vendedor_id, data);


--
-- Name: funcionarios funcionarios_cpf_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_cpf_key UNIQUE (cpf);


--
-- Name: funcionarios funcionarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_pkey PRIMARY KEY (id);


--
-- Name: money_transfers money_transfers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.money_transfers
    ADD CONSTRAINT money_transfers_pkey PRIMARY KEY (id);


--
-- Name: pedidos pedidos_numero_pedido_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_numero_pedido_key UNIQUE (numero_pedido);


--
-- Name: pedidos pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_pkey PRIMARY KEY (id);


--
-- Name: pontos pontos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pontos
    ADD CONSTRAINT pontos_pkey PRIMARY KEY (id);


--
-- Name: rastreamentos rastreamentos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rastreamentos
    ADD CONSTRAINT rastreamentos_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: vendas vendas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendas
    ADD CONSTRAINT vendas_pkey PRIMARY KEY (id);


--
-- Name: vendedores vendedores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendedores
    ADD CONSTRAINT vendedores_pkey PRIMARY KEY (id);


--
-- Name: idx_folgas_ativo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_folgas_ativo ON public.folgas USING btree (ativo) WHERE (ativo = true);


--
-- Name: idx_folgas_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_folgas_data ON public.folgas USING btree (data);


--
-- Name: idx_folgas_vendedor_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_folgas_vendedor_data ON public.folgas USING btree (vendedor_id, data);


--
-- Name: idx_vendas_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendas_data ON public.vendas USING btree (data_venda);


--
-- Name: idx_vendas_moeda; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendas_moeda ON public.vendas USING btree (moeda);


--
-- Name: idx_vendas_semana; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendas_semana ON public.vendas USING btree (semana_fechamento);


--
-- Name: idx_vendas_vendedor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendas_vendedor ON public.vendas USING btree (vendedor_id);


--
-- Name: ix_envios_codigo_rastreio; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_envios_codigo_rastreio ON public.envios USING btree (codigo_rastreio);


--
-- Name: ix_rastreamentos_codigo_rastreio; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_rastreamentos_codigo_rastreio ON public.rastreamentos USING btree (codigo_rastreio);


--
-- Name: pedidos trigger_pedido_numero; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_pedido_numero BEFORE INSERT ON public.pedidos FOR EACH ROW EXECUTE FUNCTION public.generate_pedido_numero();


--
-- Name: cambistas update_cambistas_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_cambistas_updated_at BEFORE UPDATE ON public.cambistas FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: funcionarios update_funcionarios_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_funcionarios_updated_at BEFORE UPDATE ON public.funcionarios FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: pedidos update_pedidos_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_pedidos_updated_at BEFORE UPDATE ON public.pedidos FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: usuarios update_usuarios_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_usuarios_updated_at BEFORE UPDATE ON public.usuarios FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: vendas update_vendas_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_vendas_updated_at BEFORE UPDATE ON public.vendas FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: vendedores update_vendedores_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_vendedores_updated_at BEFORE UPDATE ON public.vendedores FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: comissoes comissoes_fechamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comissoes
    ADD CONSTRAINT comissoes_fechamento_id_fkey FOREIGN KEY (fechamento_id) REFERENCES public.fechamentos_semanais(id);


--
-- Name: comissoes comissoes_vendedor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comissoes
    ADD CONSTRAINT comissoes_vendedor_id_fkey FOREIGN KEY (vendedor_id) REFERENCES public.vendedores(id);


--
-- Name: comprovantes comprovantes_aprovado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprovantes
    ADD CONSTRAINT comprovantes_aprovado_por_fkey FOREIGN KEY (aprovado_por) REFERENCES public.usuarios(id);


--
-- Name: comprovantes comprovantes_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprovantes
    ADD CONSTRAINT comprovantes_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.usuarios(id);


--
-- Name: comprovantes comprovantes_venda_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprovantes
    ADD CONSTRAINT comprovantes_venda_id_fkey FOREIGN KEY (venda_id) REFERENCES public.vendas(id) ON DELETE CASCADE;


--
-- Name: envios envios_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.envios
    ADD CONSTRAINT envios_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: envios envios_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.envios
    ADD CONSTRAINT envios_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id);


--
-- Name: fechamentos_semanais fechamentos_semanais_fechado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fechamentos_semanais
    ADD CONSTRAINT fechamentos_semanais_fechado_por_fkey FOREIGN KEY (fechado_por) REFERENCES public.usuarios(id);


--
-- Name: folgas folgas_aprovado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folgas
    ADD CONSTRAINT folgas_aprovado_por_fkey FOREIGN KEY (aprovado_por) REFERENCES public.usuarios(id);


--
-- Name: folgas folgas_vendedor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folgas
    ADD CONSTRAINT folgas_vendedor_id_fkey FOREIGN KEY (vendedor_id) REFERENCES public.vendedores(id) ON DELETE CASCADE;


--
-- Name: funcionarios funcionarios_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: pedidos pedidos_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: pedidos pedidos_separado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_separado_por_fkey FOREIGN KEY (separado_por) REFERENCES public.usuarios(id);


--
-- Name: pontos pontos_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pontos
    ADD CONSTRAINT pontos_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: pontos pontos_funcionario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pontos
    ADD CONSTRAINT pontos_funcionario_id_fkey FOREIGN KEY (funcionario_id) REFERENCES public.funcionarios(id);


--
-- Name: rastreamentos rastreamentos_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rastreamentos
    ADD CONSTRAINT rastreamentos_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: rastreamentos rastreamentos_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rastreamentos
    ADD CONSTRAINT rastreamentos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id);


--
-- Name: vendas vendas_cambista_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendas
    ADD CONSTRAINT vendas_cambista_id_fkey FOREIGN KEY (cambista_id) REFERENCES public.cambistas(id);


--
-- Name: vendas vendas_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendas
    ADD CONSTRAINT vendas_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: vendas vendas_vendedor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendas
    ADD CONSTRAINT vendas_vendedor_id_fkey FOREIGN KEY (vendedor_id) REFERENCES public.vendedores(id);


--
-- Name: vendedores vendedores_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendedores
    ADD CONSTRAINT vendedores_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- PostgreSQL database dump complete
--

