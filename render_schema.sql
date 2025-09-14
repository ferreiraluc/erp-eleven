--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9 (Debian 16.9-1.pgdg120+1)
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

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: eleven_t7jn_user
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO eleven_t7jn_user;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: currencypair; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.currencypair AS ENUM (
    'USD_TO_PYG',
    'USD_TO_BRL',
    'EUR_TO_PYG',
    'EUR_TO_BRL',
    'EUR_TO_USD'
);


ALTER TYPE public.currencypair OWNER TO eleven_t7jn_user;

--
-- Name: envio_status; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.envio_status AS ENUM (
    'PENDENTE',
    'EM_TRANSITO',
    'ENTREGUE',
    'ERRO',
    'NAO_ENCONTRADO'
);


ALTER TYPE public.envio_status OWNER TO eleven_t7jn_user;

--
-- Name: moeda_tipo; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.moeda_tipo AS ENUM (
    'G$',
    'R$',
    'U$',
    'EUR'
);


ALTER TYPE public.moeda_tipo OWNER TO eleven_t7jn_user;

--
-- Name: moedatipo; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.moedatipo AS ENUM (
    'G_DOLLAR',
    'R_DOLLAR',
    'U_DOLLAR',
    'EUR'
);


ALTER TYPE public.moedatipo OWNER TO eleven_t7jn_user;

--
-- Name: pagamento_metodo; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TYPE public.pagamento_metodo OWNER TO eleven_t7jn_user;

--
-- Name: pagamentometodo; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.pagamentometodo AS ENUM (
    'DEBITO',
    'CREDITO',
    'PIX',
    'DINHEIRO',
    'TRANSFERENCIA'
);


ALTER TYPE public.pagamentometodo OWNER TO eleven_t7jn_user;

--
-- Name: pedido_status; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TYPE public.pedido_status OWNER TO eleven_t7jn_user;

--
-- Name: pedidostatus; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.pedidostatus AS ENUM (
    'PENDENTE',
    'PROCESSANDO',
    'ENVIADO',
    'ENTREGUE',
    'CANCELADO'
);


ALTER TYPE public.pedidostatus OWNER TO eleven_t7jn_user;

--
-- Name: rastreamento_status; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.rastreamento_status AS ENUM (
    'PENDENTE',
    'EM_TRANSITO',
    'ENTREGUE',
    'ERRO',
    'NAO_ENCONTRADO'
);


ALTER TYPE public.rastreamento_status OWNER TO eleven_t7jn_user;

--
-- Name: tipofolga; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.tipofolga AS ENUM (
    'FOLGA',
    'FERIAS',
    'LICENCA',
    'FALTA',
    'MEIO_PERIODO'
);


ALTER TYPE public.tipofolga OWNER TO eleven_t7jn_user;

--
-- Name: transferstatus; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.transferstatus AS ENUM (
    'PENDING',
    'DELIVERED',
    'CANCELLED'
);


ALTER TYPE public.transferstatus OWNER TO eleven_t7jn_user;

--
-- Name: transportadora_tipo; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.transportadora_tipo AS ENUM (
    'CORREIOS',
    'AZUL_CARGO',
    'PARTICULAR',
    'SUPERFRETE'
);


ALTER TYPE public.transportadora_tipo OWNER TO eleven_t7jn_user;

--
-- Name: transportadoratipo; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.transportadoratipo AS ENUM (
    'CORREIOS',
    'AZUL_CARGO',
    'PARTICULAR',
    'SUPERFRETE'
);


ALTER TYPE public.transportadoratipo OWNER TO eleven_t7jn_user;

--
-- Name: usuario_role; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.usuario_role AS ENUM (
    'ADMIN',
    'GERENTE',
    'VENDEDOR',
    'FINANCEIRO',
    'OPERACIONAL',
    'LIMPEZA'
);


ALTER TYPE public.usuario_role OWNER TO eleven_t7jn_user;

--
-- Name: usuariorole; Type: TYPE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TYPE public.usuariorole AS ENUM (
    'ADMIN',
    'GERENTE',
    'VENDEDOR',
    'LIMPEZA'
);


ALTER TYPE public.usuariorole OWNER TO eleven_t7jn_user;

--
-- Name: generate_pedido_numero(); Type: FUNCTION; Schema: public; Owner: eleven_t7jn_user
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


ALTER FUNCTION public.generate_pedido_numero() OWNER TO eleven_t7jn_user;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: eleven_t7jn_user
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO eleven_t7jn_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO eleven_t7jn_user;

--
-- Name: cambistas; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.cambistas OWNER TO eleven_t7jn_user;

--
-- Name: comissoes; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.comissoes OWNER TO eleven_t7jn_user;

--
-- Name: comprovantes; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.comprovantes OWNER TO eleven_t7jn_user;

--
-- Name: envios; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.envios OWNER TO eleven_t7jn_user;

--
-- Name: TABLE envios; Type: COMMENT; Schema: public; Owner: eleven_t7jn_user
--

COMMENT ON TABLE public.envios IS 'Tabela para gerenciar envios e entregas';


--
-- Name: exchange_rates; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.exchange_rates OWNER TO eleven_t7jn_user;

--
-- Name: TABLE exchange_rates; Type: COMMENT; Schema: public; Owner: eleven_t7jn_user
--

COMMENT ON TABLE public.exchange_rates IS 'Tabela para taxas de câmbio entre moedas';


--
-- Name: fechamentos_semanais; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.fechamentos_semanais OWNER TO eleven_t7jn_user;

--
-- Name: folgas; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.folgas OWNER TO eleven_t7jn_user;

--
-- Name: TABLE folgas; Type: COMMENT; Schema: public; Owner: eleven_t7jn_user
--

COMMENT ON TABLE public.folgas IS 'Tabela para gerenciar folgas, férias e ausências dos vendedores';


--
-- Name: funcionarios; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.funcionarios OWNER TO eleven_t7jn_user;

--
-- Name: money_transfers; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.money_transfers OWNER TO eleven_t7jn_user;

--
-- Name: TABLE money_transfers; Type: COMMENT; Schema: public; Owner: eleven_t7jn_user
--

COMMENT ON TABLE public.money_transfers IS 'Tabela para transferências de dinheiro internacionais';


--
-- Name: pedidos; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TABLE public.pedidos (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    numero_pedido character varying(50),
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
    data_separacao date,
    data_pagamento date,
    data_conclusao date,
    valor_total numeric(10,2) DEFAULT 0 NOT NULL,
    valor_pago numeric(10,2) DEFAULT 0,
    forma_pagamento character varying(50),
    pago character varying(10) DEFAULT 'NAO'::character varying,
    prioridade character varying(10) DEFAULT 'NORMAL'::character varying,
    observacoes text,
    instrucoes_entrega text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by uuid,
    separado_por uuid
);


ALTER TABLE public.pedidos OWNER TO eleven_t7jn_user;

--
-- Name: pontos; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.pontos OWNER TO eleven_t7jn_user;

--
-- Name: rastreamentos; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TABLE public.rastreamentos (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    codigo_rastreio character varying(100) NOT NULL,
    status public.rastreamento_status DEFAULT 'PENDENTE'::public.rastreamento_status,
    servico_provedor character varying(100),
    ultima_atualizacao timestamp without time zone,
    descricao text,
    destinatario character varying(200),
    origem character varying(200),
    destino character varying(200),
    historico_eventos jsonb DEFAULT '[]'::jsonb,
    pedido_id uuid,
    data_criacao date DEFAULT CURRENT_DATE,
    ativo boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by uuid
);


ALTER TABLE public.rastreamentos OWNER TO eleven_t7jn_user;

--
-- Name: TABLE rastreamentos; Type: COMMENT; Schema: public; Owner: eleven_t7jn_user
--

COMMENT ON TABLE public.rastreamentos IS 'Tabela para rastrear encomendas e pedidos';


--
-- Name: seq_pedido_numero; Type: SEQUENCE; Schema: public; Owner: eleven_t7jn_user
--

CREATE SEQUENCE public.seq_pedido_numero
    START WITH 1000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.seq_pedido_numero OWNER TO eleven_t7jn_user;

--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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


ALTER TABLE public.usuarios OWNER TO eleven_t7jn_user;

--
-- Name: vendas; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
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
    taxa_desconto_pagamento numeric(5,4) DEFAULT '0'::numeric,
    pending_transfer_id uuid,
    requires_thais_transfer boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by uuid
);


ALTER TABLE public.vendas OWNER TO eleven_t7jn_user;

--
-- Name: vendedores; Type: TABLE; Schema: public; Owner: eleven_t7jn_user
--

CREATE TABLE public.vendedores (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    nome character varying(100) NOT NULL,
    usuario_id uuid,
    taxa_comissao numeric(5,2) DEFAULT 10.00,
    meta_semanal numeric(12,2) DEFAULT 0,
    conta_bancaria character varying(50),
    telefone character varying(20),
    cor_calendario character varying(7) DEFAULT '#3B82F6'::character varying,
    ativo boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.vendedores OWNER TO eleven_t7jn_user;

--
-- Name: vw_vendas_por_vendedor; Type: VIEW; Schema: public; Owner: eleven_t7jn_user
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


ALTER VIEW public.vw_vendas_por_vendedor OWNER TO eleven_t7jn_user;

--
-- Name: vw_vendas_semana_atual; Type: VIEW; Schema: public; Owner: eleven_t7jn_user
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


ALTER VIEW public.vw_vendas_semana_atual OWNER TO eleven_t7jn_user;

--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: cambistas cambistas_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.cambistas
    ADD CONSTRAINT cambistas_pkey PRIMARY KEY (id);


--
-- Name: comissoes comissoes_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.comissoes
    ADD CONSTRAINT comissoes_pkey PRIMARY KEY (id);


--
-- Name: comprovantes comprovantes_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.comprovantes
    ADD CONSTRAINT comprovantes_pkey PRIMARY KEY (id);


--
-- Name: envios envios_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.envios
    ADD CONSTRAINT envios_pkey PRIMARY KEY (id);


--
-- Name: exchange_rates exchange_rates_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.exchange_rates
    ADD CONSTRAINT exchange_rates_pkey PRIMARY KEY (id);


--
-- Name: fechamentos_semanais fechamentos_semanais_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.fechamentos_semanais
    ADD CONSTRAINT fechamentos_semanais_pkey PRIMARY KEY (id);


--
-- Name: folgas folgas_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.folgas
    ADD CONSTRAINT folgas_pkey PRIMARY KEY (id);


--
-- Name: folgas folgas_vendedor_id_data_key; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.folgas
    ADD CONSTRAINT folgas_vendedor_id_data_key UNIQUE (vendedor_id, data);


--
-- Name: funcionarios funcionarios_cpf_key; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_cpf_key UNIQUE (cpf);


--
-- Name: funcionarios funcionarios_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_pkey PRIMARY KEY (id);


--
-- Name: money_transfers money_transfers_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.money_transfers
    ADD CONSTRAINT money_transfers_pkey PRIMARY KEY (id);


--
-- Name: pedidos pedidos_numero_pedido_key; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_numero_pedido_key UNIQUE (numero_pedido);


--
-- Name: pedidos pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_pkey PRIMARY KEY (id);


--
-- Name: pontos pontos_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.pontos
    ADD CONSTRAINT pontos_pkey PRIMARY KEY (id);


--
-- Name: rastreamentos rastreamentos_codigo_rastreio_key; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.rastreamentos
    ADD CONSTRAINT rastreamentos_codigo_rastreio_key UNIQUE (codigo_rastreio);


--
-- Name: rastreamentos rastreamentos_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.rastreamentos
    ADD CONSTRAINT rastreamentos_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: vendas vendas_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.vendas
    ADD CONSTRAINT vendas_pkey PRIMARY KEY (id);


--
-- Name: vendedores vendedores_pkey; Type: CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.vendedores
    ADD CONSTRAINT vendedores_pkey PRIMARY KEY (id);


--
-- Name: idx_folgas_ativo; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_folgas_ativo ON public.folgas USING btree (ativo) WHERE (ativo = true);


--
-- Name: idx_folgas_data; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_folgas_data ON public.folgas USING btree (data);


--
-- Name: idx_folgas_vendedor_data; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_folgas_vendedor_data ON public.folgas USING btree (vendedor_id, data);


--
-- Name: idx_rastreamentos_ativo; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_rastreamentos_ativo ON public.rastreamentos USING btree (ativo);


--
-- Name: idx_rastreamentos_codigo; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_rastreamentos_codigo ON public.rastreamentos USING btree (codigo_rastreio);


--
-- Name: idx_rastreamentos_created_at; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_rastreamentos_created_at ON public.rastreamentos USING btree (created_at);


--
-- Name: idx_rastreamentos_status; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_rastreamentos_status ON public.rastreamentos USING btree (status);


--
-- Name: idx_vendas_data; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_vendas_data ON public.vendas USING btree (data_venda);


--
-- Name: idx_vendas_moeda; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_vendas_moeda ON public.vendas USING btree (moeda);


--
-- Name: idx_vendas_semana; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_vendas_semana ON public.vendas USING btree (semana_fechamento);


--
-- Name: idx_vendas_vendedor; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE INDEX idx_vendas_vendedor ON public.vendas USING btree (vendedor_id);


--
-- Name: ix_envios_codigo_rastreio; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE UNIQUE INDEX ix_envios_codigo_rastreio ON public.envios USING btree (codigo_rastreio);


--
-- Name: ix_rastreamentos_codigo_rastreio; Type: INDEX; Schema: public; Owner: eleven_t7jn_user
--

CREATE UNIQUE INDEX ix_rastreamentos_codigo_rastreio ON public.rastreamentos USING btree (codigo_rastreio);


--
-- Name: pedidos trigger_pedido_numero; Type: TRIGGER; Schema: public; Owner: eleven_t7jn_user
--

CREATE TRIGGER trigger_pedido_numero BEFORE INSERT ON public.pedidos FOR EACH ROW EXECUTE FUNCTION public.generate_pedido_numero();


--
-- Name: cambistas update_cambistas_updated_at; Type: TRIGGER; Schema: public; Owner: eleven_t7jn_user
--

CREATE TRIGGER update_cambistas_updated_at BEFORE UPDATE ON public.cambistas FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: folgas update_folgas_updated_at; Type: TRIGGER; Schema: public; Owner: eleven_t7jn_user
--

CREATE TRIGGER update_folgas_updated_at BEFORE UPDATE ON public.folgas FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: funcionarios update_funcionarios_updated_at; Type: TRIGGER; Schema: public; Owner: eleven_t7jn_user
--

CREATE TRIGGER update_funcionarios_updated_at BEFORE UPDATE ON public.funcionarios FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: pedidos update_pedidos_updated_at; Type: TRIGGER; Schema: public; Owner: eleven_t7jn_user
--

CREATE TRIGGER update_pedidos_updated_at BEFORE UPDATE ON public.pedidos FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: usuarios update_usuarios_updated_at; Type: TRIGGER; Schema: public; Owner: eleven_t7jn_user
--

CREATE TRIGGER update_usuarios_updated_at BEFORE UPDATE ON public.usuarios FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: vendas update_vendas_updated_at; Type: TRIGGER; Schema: public; Owner: eleven_t7jn_user
--

CREATE TRIGGER update_vendas_updated_at BEFORE UPDATE ON public.vendas FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: vendedores update_vendedores_updated_at; Type: TRIGGER; Schema: public; Owner: eleven_t7jn_user
--

CREATE TRIGGER update_vendedores_updated_at BEFORE UPDATE ON public.vendedores FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: comissoes comissoes_fechamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.comissoes
    ADD CONSTRAINT comissoes_fechamento_id_fkey FOREIGN KEY (fechamento_id) REFERENCES public.fechamentos_semanais(id);


--
-- Name: comissoes comissoes_vendedor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.comissoes
    ADD CONSTRAINT comissoes_vendedor_id_fkey FOREIGN KEY (vendedor_id) REFERENCES public.vendedores(id);


--
-- Name: comprovantes comprovantes_aprovado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.comprovantes
    ADD CONSTRAINT comprovantes_aprovado_por_fkey FOREIGN KEY (aprovado_por) REFERENCES public.usuarios(id);


--
-- Name: comprovantes comprovantes_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.comprovantes
    ADD CONSTRAINT comprovantes_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.usuarios(id);


--
-- Name: comprovantes comprovantes_venda_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.comprovantes
    ADD CONSTRAINT comprovantes_venda_id_fkey FOREIGN KEY (venda_id) REFERENCES public.vendas(id) ON DELETE CASCADE;


--
-- Name: envios envios_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.envios
    ADD CONSTRAINT envios_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: envios envios_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.envios
    ADD CONSTRAINT envios_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id);


--
-- Name: fechamentos_semanais fechamentos_semanais_fechado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.fechamentos_semanais
    ADD CONSTRAINT fechamentos_semanais_fechado_por_fkey FOREIGN KEY (fechado_por) REFERENCES public.usuarios(id);


--
-- Name: folgas folgas_aprovado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.folgas
    ADD CONSTRAINT folgas_aprovado_por_fkey FOREIGN KEY (aprovado_por) REFERENCES public.usuarios(id);


--
-- Name: funcionarios funcionarios_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.funcionarios
    ADD CONSTRAINT funcionarios_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: pedidos pedidos_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: pedidos pedidos_separado_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_separado_por_fkey FOREIGN KEY (separado_por) REFERENCES public.usuarios(id);


--
-- Name: pontos pontos_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.pontos
    ADD CONSTRAINT pontos_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: rastreamentos rastreamentos_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.rastreamentos
    ADD CONSTRAINT rastreamentos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id);


--
-- Name: vendas vendas_cambista_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.vendas
    ADD CONSTRAINT vendas_cambista_id_fkey FOREIGN KEY (cambista_id) REFERENCES public.cambistas(id);


--
-- Name: vendas vendas_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.vendas
    ADD CONSTRAINT vendas_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.usuarios(id);


--
-- Name: vendas vendas_vendedor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.vendas
    ADD CONSTRAINT vendas_vendedor_id_fkey FOREIGN KEY (vendedor_id) REFERENCES public.vendedores(id);


--
-- Name: vendedores vendedores_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: eleven_t7jn_user
--

ALTER TABLE ONLY public.vendedores
    ADD CONSTRAINT vendedores_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: FUNCTION gtrgm_in(cstring); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_in(cstring) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_out(public.gtrgm); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_out(public.gtrgm) TO eleven_t7jn_user;


--
-- Name: TYPE gtrgm; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TYPE public.gtrgm TO eleven_t7jn_user;


--
-- Name: FUNCTION gin_extract_query_trgm(text, internal, smallint, internal, internal, internal, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gin_extract_query_trgm(text, internal, smallint, internal, internal, internal, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gin_extract_value_trgm(text, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gin_extract_value_trgm(text, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gin_trgm_consistent(internal, smallint, text, integer, internal, internal, internal, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gin_trgm_consistent(internal, smallint, text, integer, internal, internal, internal, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gin_trgm_triconsistent(internal, smallint, text, integer, internal, internal, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gin_trgm_triconsistent(internal, smallint, text, integer, internal, internal, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_compress(internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_compress(internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_consistent(internal, text, smallint, oid, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_consistent(internal, text, smallint, oid, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_decompress(internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_decompress(internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_distance(internal, text, smallint, oid, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_distance(internal, text, smallint, oid, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_options(internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_options(internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_penalty(internal, internal, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_penalty(internal, internal, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_picksplit(internal, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_picksplit(internal, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_same(public.gtrgm, public.gtrgm, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_same(public.gtrgm, public.gtrgm, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION gtrgm_union(internal, internal); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gtrgm_union(internal, internal) TO eleven_t7jn_user;


--
-- Name: FUNCTION set_limit(real); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.set_limit(real) TO eleven_t7jn_user;


--
-- Name: FUNCTION show_limit(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.show_limit() TO eleven_t7jn_user;


--
-- Name: FUNCTION show_trgm(text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.show_trgm(text) TO eleven_t7jn_user;


--
-- Name: FUNCTION similarity(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.similarity(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION similarity_dist(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.similarity_dist(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION similarity_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.similarity_op(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION strict_word_similarity(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.strict_word_similarity(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION strict_word_similarity_commutator_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.strict_word_similarity_commutator_op(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION strict_word_similarity_dist_commutator_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.strict_word_similarity_dist_commutator_op(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION strict_word_similarity_dist_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.strict_word_similarity_dist_op(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION strict_word_similarity_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.strict_word_similarity_op(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_generate_v1(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_generate_v1() TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_generate_v1mc(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_generate_v1mc() TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_generate_v3(namespace uuid, name text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_generate_v3(namespace uuid, name text) TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_generate_v4(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_generate_v4() TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_generate_v5(namespace uuid, name text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_generate_v5(namespace uuid, name text) TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_nil(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_nil() TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_ns_dns(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_ns_dns() TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_ns_oid(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_ns_oid() TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_ns_url(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_ns_url() TO eleven_t7jn_user;


--
-- Name: FUNCTION uuid_ns_x500(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.uuid_ns_x500() TO eleven_t7jn_user;


--
-- Name: FUNCTION word_similarity(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.word_similarity(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION word_similarity_commutator_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.word_similarity_commutator_op(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION word_similarity_dist_commutator_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.word_similarity_dist_commutator_op(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION word_similarity_dist_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.word_similarity_dist_op(text, text) TO eleven_t7jn_user;


--
-- Name: FUNCTION word_similarity_op(text, text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.word_similarity_op(text, text) TO eleven_t7jn_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: -; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT ALL ON SEQUENCES TO eleven_t7jn_user;


--
-- Name: DEFAULT PRIVILEGES FOR TYPES; Type: DEFAULT ACL; Schema: -; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT ALL ON TYPES TO eleven_t7jn_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: -; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT ALL ON FUNCTIONS TO eleven_t7jn_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: -; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT,INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,UPDATE ON TABLES TO eleven_t7jn_user;


--
-- PostgreSQL database dump complete
--

