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
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

SET SESSION AUTHORIZATION DEFAULT;

ALTER TABLE public.alembic_version DISABLE TRIGGER ALL;

COPY public.alembic_version (version_num) FROM stdin;
9572ac0c4129
\.


ALTER TABLE public.alembic_version ENABLE TRIGGER ALL;

--
-- Data for Name: cambistas; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.cambistas DISABLE TRIGGER ALL;

COPY public.cambistas (id, nome, taxa_g_para_r, taxa_u_para_r, taxa_eur_para_r, conta_bancaria, telefone, ativo, observacoes, created_at, updated_at) FROM stdin;
cff146d6-e781-4de1-8456-8aa8264f85d2	Cambista Principal	5.6500	5.5000	6.2000	\N	\N	t	\N	2025-08-03 21:50:00.57657	2025-08-03 21:50:00.57657
77be4479-74ea-4590-97ed-5e5d3d2230d1	Casa de Câmbio Central	5.6500	5.5000	6.2000	987654-3	11955555555	t	\N	2025-08-04 23:25:31.282224	2025-08-04 23:25:31.282224
9aae2643-498f-4a16-a888-48a41185dbbc	Câmbio Express	5.7000	5.4500	6.1500	876543-2	11944444444	t	\N	2025-08-04 23:25:31.283795	2025-08-04 23:25:31.283795
\.


ALTER TABLE public.cambistas ENABLE TRIGGER ALL;

--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.usuarios DISABLE TRIGGER ALL;

COPY public.usuarios (id, nome, email, senha_hash, role, ativo, ultimo_login, created_at, updated_at) FROM stdin;
542e05b5-6a0d-4186-bba9-8810089bafb6	João Silva	joao@loja.com	$2b$12$emhohGRigur59IgI0FyCkOU8p98v3uLpTQwr091c2s77FsXrOmGaq	GERENTE	t	\N	2025-08-04 23:24:26.767431	2025-08-04 23:24:26.767431
91c70214-bc82-4c52-b440-466ca6733e8f	Maria Santos	maria@loja.com	$2b$12$SYfiTXFv5Tu0gvRtygIv2eWhRJSFuchHuXkf1tZBBT789y7yupSNq	VENDEDOR	t	\N	2025-08-04 23:24:26.956192	2025-08-04 23:24:26.956192
f1029c04-a9ba-4c80-be08-01e319d26ebf	Carlos Oliveira	carlos@loja.com	$2b$12$zmWE72YIgGtmVPh9WFnHUO6S.rqLFaV/ySoqsPe1F508QsK9LdT/6	LIMPEZA	t	2025-08-05 02:43:18.109345	2025-08-04 23:24:27.124804	2025-08-05 19:49:41.052132
1db754f2-7d80-4f87-8b1f-3b501775c4ab	Administrador	admin@loja.com	$2b$12$vG.shwiROZz7xX5fJ.Zl3OibD0jbq9W/VqIvvxiqrRIqL/1M.IB3m	ADMIN	t	2025-09-03 23:45:32.265356	2025-08-03 21:50:00.57657	2025-09-03 20:45:32.055644
\.


ALTER TABLE public.usuarios ENABLE TRIGGER ALL;

--
-- Data for Name: fechamentos_semanais; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.fechamentos_semanais DISABLE TRIGGER ALL;

COPY public.fechamentos_semanais (id, semana_inicio, semana_fim, fechado, fechado_em, fechado_por, total_vendas_g, total_vendas_r, total_vendas_u, total_vendas_eur, created_at) FROM stdin;
\.


ALTER TABLE public.fechamentos_semanais ENABLE TRIGGER ALL;

--
-- Data for Name: vendedores; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.vendedores DISABLE TRIGGER ALL;

COPY public.vendedores (id, nome, usuario_id, taxa_comissao, meta_semanal, conta_bancaria, telefone, ativo, created_at, updated_at, cor_calendario) FROM stdin;
c0a69ae4-0ab9-4def-b70a-7217ad1fe230	José Santos	f1029c04-a9ba-4c80-be08-01e319d26ebf	15.00	3000.00	234567-8	11976543210	f	2025-08-04 23:25:31.279988	2025-08-28 23:20:52.127984	#3B82F6
dda6b75c-717d-48be-a823-66b61d17e222	Maria Vendedora	91c70214-bc82-4c52-b440-466ca6733e8f	12.50	2500.00	123456-7	11987654321	f	2025-08-04 23:25:31.275162	2025-08-28 23:21:00.355325	#3B82F6
32dbeb18-bbd0-4aec-bbd2-812a4996cd83	Denis	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 21:31:44.767274	#3B82F6
a0491166-dd55-4c44-814e-248f52e65755	Sol	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 21:31:44.767274	#F59E0B
35d0522b-83ca-41d3-8e1e-1c6b742807c4	Wiss	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 21:31:44.767274	#8B5CF6
e2ebb4af-1387-401b-98ed-c8d7c1bd81c1	Lucas	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 21:31:44.767274	#10B981
57180009-1a3f-437d-9401-bdfb1ffed375	Junior	\N	10.00	0.00	\N	\N	t	2025-08-03 21:50:00.57657	2025-09-03 22:16:02.240341	#e392fe
\.


ALTER TABLE public.vendedores ENABLE TRIGGER ALL;

--
-- Data for Name: comissoes; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.comissoes DISABLE TRIGGER ALL;

COPY public.comissoes (id, fechamento_id, vendedor_id, total_g, total_r, total_u, total_eur, percentual_comissao, valor_comissao, pago, data_pagamento, created_at) FROM stdin;
\.


ALTER TABLE public.comissoes ENABLE TRIGGER ALL;

--
-- Data for Name: vendas; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.vendas DISABLE TRIGGER ALL;

COPY public.vendas (id, data_venda, vendedor_id, moeda, valor_bruto, metodo_pagamento, cambista_id, taxa_cambio_usada, valor_cambista, valor_liquido, descricao_produto, observacoes, semana_fechamento, fechado, created_at, updated_at, created_by, taxa_desconto_pagamento, pending_transfer_id, requires_thais_transfer) FROM stdin;
e8036da5-6fa6-4a50-b887-d3ec0550bb7e	2025-08-05	dda6b75c-717d-48be-a823-66b61d17e222	R$	150.0000	PIX_POWER	\N	\N	\N	150.0000	Camiseta básica	\N	\N	f	2025-08-05 19:54:25.710577	2025-08-05 19:54:25.710577	542e05b5-6a0d-4186-bba9-8810089bafb6	0.0000	\N	f
d2b6f55d-81ec-4b99-a8c2-e7f246b5ab2d	2025-08-05	dda6b75c-717d-48be-a823-66b61d17e222	G$	25.0000	CREDITO	77be4479-74ea-4590-97ed-5e5d3d2230d1	5.6500	141.2500	141.2500	Calça jeans	\N	\N	f	2025-08-05 19:54:25.715249	2025-08-05 19:54:25.715249	542e05b5-6a0d-4186-bba9-8810089bafb6	0.0000	\N	f
404990a7-52b6-4fa4-82f7-d2557c0fa1e8	2025-08-05	dda6b75c-717d-48be-a823-66b61d17e222	R$	150.0000	PIX_POWER	\N	\N	\N	150.0000	Camiseta básica	\N	\N	f	2025-08-05 19:56:38.127912	2025-08-05 19:56:38.127912	542e05b5-6a0d-4186-bba9-8810089bafb6	0.0000	\N	f
d2c5f85f-83cb-4a35-981a-50529d632495	2025-08-05	dda6b75c-717d-48be-a823-66b61d17e222	G$	25.0000	CREDITO	77be4479-74ea-4590-97ed-5e5d3d2230d1	5.6500	141.2500	141.2500	Calça jeans	\N	\N	f	2025-08-05 19:56:38.132073	2025-08-05 19:56:38.132073	542e05b5-6a0d-4186-bba9-8810089bafb6	0.0000	\N	f
\.


ALTER TABLE public.vendas ENABLE TRIGGER ALL;

--
-- Data for Name: comprovantes; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.comprovantes DISABLE TRIGGER ALL;

COPY public.comprovantes (id, venda_id, nome_arquivo, arquivo_url, tipo_arquivo, tamanho_bytes, aprovado, aprovado_por, aprovado_em, created_at, uploaded_by) FROM stdin;
\.


ALTER TABLE public.comprovantes ENABLE TRIGGER ALL;

--
-- Data for Name: pedidos; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.pedidos DISABLE TRIGGER ALL;

COPY public.pedidos (id, numero_pedido, cliente_nome, cliente_telefone, cliente_email, endereco_rua, endereco_numero, endereco_complemento, endereco_bairro, endereco_cidade, endereco_uf, endereco_cep, transportadora, codigo_rastreio, valor_frete, peso_kg, status, data_pedido, data_envio, data_entrega, observacoes, instrucoes_entrega, created_at, updated_at, created_by, data_separacao, data_pagamento, data_conclusao, valor_total, valor_pago, forma_pagamento, pago, separado_por, prioridade) FROM stdin;
245f7183-62ca-46bc-b93e-a474105e6668	PED-001	João Silva	(11) 99999-0001	joao.silva@email.com	Rua das Flores, 123	123	\N	Centro	São Paulo	SP	01234-567	CORREIOS	BR123456789	15.50	1.200	VENDIDO	2025-08-27	\N	\N	Cliente solicitou entrega rápida	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	\N	\N	\N	150.00	0.00	PIX	NAO	\N	ALTA
6083e915-f280-4d3b-80e2-100db398a55f	PED-002	Maria Santos	(11) 99999-0002	maria.santos@email.com	Av. Paulista, 1000	1000	\N	Bela Vista	São Paulo	SP	01310-100	AZUL_CARGO	AC987654321	25.00	2.500	SEPARANDO	2025-08-27	\N	\N	Pedido especial VIP	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	2025-08-27	\N	\N	280.50	280.50	CARTAO	SIM	\N	URGENTE
345d9e7a-f438-4f1e-94b4-db8cd34cc7ee	PED-003	Carlos Oliveira	(21) 99999-0003	carlos.oliveira@email.com	Rua Copacabana, 456	456	\N	Copacabana	Rio de Janeiro	RJ	22070-000	CORREIOS	BR555666777	18.90	1.800	SEPARADO_PAGO	2025-08-27	\N	\N	\N	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	2025-08-27	2025-08-27	\N	320.00	320.00	PIX	SIM	1db754f2-7d80-4f87-8b1f-3b501775c4ab	NORMAL
a443a94f-fd98-4a0d-9ec0-7d7f14ce338a	PED-004	Ana Costa	(31) 99999-0004	ana.costa@email.com	Rua da Liberdade, 789	789	\N	Centro	Belo Horizonte	MG	30112-000	SUPERFRETE	SF111222333	22.00	3.000	SEPARADO_NAO_PAGO	2025-08-27	\N	\N	Aguardando pagamento do boleto	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	2025-08-27	\N	\N	450.75	0.00	BOLETO	NAO	1db754f2-7d80-4f87-8b1f-3b501775c4ab	NORMAL
9ed1bb60-3d56-4da7-a698-0421a15c22ea	PED-005	Pedro Ferreira	(85) 99999-0005	pedro.ferreira@email.com	Av. Beira Mar, 321	321	\N	Meireles	Fortaleza	CE	60165-121	CORREIOS	BR999888777	30.00	2.200	ENTREGUE	2025-08-27	2025-08-27	2025-08-27	\N	\N	2025-08-27 19:21:51.758409	2025-08-27 19:21:51.758409	1db754f2-7d80-4f87-8b1f-3b501775c4ab	2025-08-27	2025-08-27	\N	199.90	199.90	CARTAO	SIM	1db754f2-7d80-4f87-8b1f-3b501775c4ab	BAIXA
\.


ALTER TABLE public.pedidos ENABLE TRIGGER ALL;

--
-- Data for Name: envios; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.envios DISABLE TRIGGER ALL;

COPY public.envios (id, codigo_rastreio, status, servico_provedor, ultima_atualizacao, descricao, destinatario, origem, destino, historico_eventos, cliente_nome, observacoes, pedido_id, data_criacao, ativo, created_at, updated_at, created_by) FROM stdin;
\.


ALTER TABLE public.envios ENABLE TRIGGER ALL;

--
-- Data for Name: exchange_rates; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.exchange_rates DISABLE TRIGGER ALL;

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


ALTER TABLE public.exchange_rates ENABLE TRIGGER ALL;

--
-- Data for Name: folgas; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.folgas DISABLE TRIGGER ALL;

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


ALTER TABLE public.folgas ENABLE TRIGGER ALL;

--
-- Data for Name: funcionarios; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.funcionarios DISABLE TRIGGER ALL;

COPY public.funcionarios (id, nome, cpf, usuario_id, cargo, salario, data_admissao, data_demissao, horarios, telefone, endereco, ativo, created_at, updated_at, cor_calendario) FROM stdin;
ac1a11f2-4329-40a4-ae4e-301bae94deec	Ana Silva	123.456.789-01	91c70214-bc82-4c52-b440-466ca6733e8f	Gerente de Loja	3500.00	2024-01-15	\N	\N	11987654321	Rua das Flores, 123 - São Paulo, SP	t	2025-08-05 19:49:45.784606	2025-08-05 19:49:45.784606	#3B82F6
2f07ac66-5449-415a-b712-9a460e2ddb00	Carlos Santos	987.654.321-01	f1029c04-a9ba-4c80-be08-01e319d26ebf	Auxiliar de Limpeza	1500.00	2024-02-01	\N	\N	11976543210	Av. Central, 456 - São Paulo, SP	t	2025-08-05 19:49:45.789635	2025-08-05 19:49:45.789635	#3B82F6
209f2376-7f9a-460a-a0ca-a60c0f650e20	Lucas Adriano Ferreira Gimenez	107.006.749-00	\N	Gerente	3000.00	\N	\N	\N	(45) 99953-2052	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#3B82F6
10d66401-8744-4192-8683-831688013757	Denis Christopher	234.567.890-12	\N	Vendedor	2500.00	\N	\N	\N	(11) 98765-4322	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#EF4444
695390ab-8a6f-4512-9a54-8d99b32c0d9d	Junior Favretto	345.678.901-23	\N	Vendedor	4500.00	\N	\N	\N	(11) 98765-4323	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#10B981
9483a97d-5af8-4930-9210-5aa4e523c88a	Sol Perez	456.789.012-34	\N	Vendedor	2000.00	\N	\N	\N	(11) 98765-4324	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#F59E0B
7b5c2582-16b7-4807-a5aa-b471e1356f75	Lourdes	567.890.123-45	\N	Supervisora de Limpeza	3500.00	\N	\N	\N	(11) 98765-4325	\N	t	2025-09-03 21:18:25.457513	2025-09-03 21:18:25.457513	#8B5CF6
\.


ALTER TABLE public.funcionarios ENABLE TRIGGER ALL;

--
-- Data for Name: money_transfers; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.money_transfers DISABLE TRIGGER ALL;

COPY public.money_transfers (id, transfer_date, amount_sent, thais_fee_percentage, thais_fee_amount, net_amount, status, delivery_confirmed_at, delivery_confirmed_by, currency, transfer_method, reference_number, notes, created_at, updated_at, created_by) FROM stdin;
\.


ALTER TABLE public.money_transfers ENABLE TRIGGER ALL;

--
-- Data for Name: pontos; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.pontos DISABLE TRIGGER ALL;

COPY public.pontos (id, funcionario_id, data_ponto, entrada_manha, saida_almoco, entrada_tarde, saida_noite, horas_trabalhadas, horas_extras, observacoes, created_at, created_by) FROM stdin;
\.


ALTER TABLE public.pontos ENABLE TRIGGER ALL;

--
-- Data for Name: rastreamentos; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.rastreamentos DISABLE TRIGGER ALL;

COPY public.rastreamentos (id, codigo_rastreio, status, servico_provedor, ultima_atualizacao, descricao, destinatario, origem, destino, historico_eventos, pedido_id, data_criacao, ativo, created_at, updated_at, created_by) FROM stdin;
6027c71c-bf0d-4e69-b13a-7d9165ab12ce	AC957865542BR	ENTREGUE	linkcorreios	2025-08-17 17:27:09.634065	\N	\N	\N	\N	[{"data": "17/08/2025 17:27", "local": "", "origem": null, "destino": null, "detalhes": "Objeto -", "situacao": "Objeto -"}]	\N	2025-08-17	f	2025-08-17 17:27:09.155138	2025-08-17 17:32:27.248431	1db754f2-7d80-4f87-8b1f-3b501775c4ab
f9be4eb1-dc0d-4b14-9643-2fee3a5f1ad0	AC958117356BR	ENTREGUE	linkcorreios	2025-08-17 17:26:36.184311	\N	\N	\N	\N	[{"data": "17/08/2025 17:26", "local": "", "origem": null, "destino": null, "detalhes": "Objeto -", "situacao": "Objeto -"}]	\N	2025-08-17	f	2025-08-17 17:26:35.688869	2025-08-17 17:32:28.870007	1db754f2-7d80-4f87-8b1f-3b501775c4ab
7cc0607f-0527-4245-bc85-03d33e0957cf	AC950573845BR	PENDENTE	correios_website	2025-08-17 16:52:40.354587	\N	\N	\N	\N	[]	\N	2025-08-17	f	2025-08-17 16:52:38.920435	2025-08-17 16:55:41.748562	1db754f2-7d80-4f87-8b1f-3b501775c4ab
1a50b35f-0db1-4341-86a5-038a7386f986	AM822099295BR	PENDENTE	correios_website	2025-08-17 17:14:34.281569	\N	\N	\N	\N	[]	\N	2025-08-17	f	2025-08-17 16:51:44.987059	2025-08-17 17:23:48.374033	1db754f2-7d80-4f87-8b1f-3b501775c4ab
8920a102-4654-46bc-a39d-f8647c5d18df	AC950973423BR	ENTREGUE	linkcorreios	2025-08-19 18:18:35.718895	Camisetas	Anderson Faria Silva	Foz	SP	[]	\N	2025-08-17	t	2025-08-17 17:34:11.245304	2025-08-28 18:53:23.943763	1db754f2-7d80-4f87-8b1f-3b501775c4ab
9759f6a4-79a7-48a5-9560-e609ec93cb7e	AC958114099BR	EM_TRANSITO	linkcorreios	2025-08-19 18:18:35.718833	\N	\N	\N	\N	[]	\N	2025-08-17	t	2025-08-17 21:09:09.668375	2025-08-28 18:53:27.922088	1db754f2-7d80-4f87-8b1f-3b501775c4ab
bed26efb-8f7f-46df-ab89-8f1c48d98055	AC950605565BR	ENTREGUE	linkcorreios	2025-08-19 18:18:35.718862	\N	\N	\N	\N	[]	\N	2025-08-17	t	2025-08-17 17:33:48.52633	2025-08-26 22:23:21.962508	1db754f2-7d80-4f87-8b1f-3b501775c4ab
d79aa1e9-5b84-4bd8-94a0-ab74954fe4af	AC950668168BR	EM_TRANSITO	linkcorreios	2025-08-19 18:18:35.718878	\N	\N	\N	\N	[]	\N	2025-08-17	t	2025-08-17 21:09:32.076826	2025-08-28 18:54:35.489296	1db754f2-7d80-4f87-8b1f-3b501775c4ab
\.


ALTER TABLE public.rastreamentos ENABLE TRIGGER ALL;

--
-- Name: seq_pedido_numero; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.seq_pedido_numero', 1000, false);


--
-- PostgreSQL database dump complete
--

