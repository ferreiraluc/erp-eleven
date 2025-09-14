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

