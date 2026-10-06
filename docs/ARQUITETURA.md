# Arquitetura e mapa do código

## Organização

Monólito modular: Vue 3/TypeScript/Pinia no frontend, FastAPI/Pydantic/SQLAlchemy no
backend e PostgreSQL como estado persistente. Os endpoints usam serviços e/ou sessões
SQLAlchemy diretamente; não há uma camada universal de repositórios, Redis ou Celery.

- `frontend/src/main.ts` inicia Vue, Pinia, router e i18n; `App.vue` contém as telas e notificações.
- `frontend/src/assets/buttons.css` define os botões de ação: `erp-button` com
  variantes `--primary`, `--secondary`, `--danger` e `--ghost`; `--sm` para ações
  compactas e `--icon` para ícones. Cor, tipografia, foco e desabilitado são centrais,
  inclusive em modais teleportados. Layout e visibilidade responsiva pertencem à tela.
  Abas, opções, filtros e cards clicáveis usam `erp-control`, conservando indicação
  de seleção e formato próprios. A navegação de conta e os dropdowns têm estilo próprio.
- `frontend/src/router/index.ts` declara rotas, autenticação e restrições de ADMIN/GERENTE na navegação.
- `frontend/src/services/api.ts` centraliza Axios e os contratos dos módulos; `salesBi.ts` isola o BI.
- `backend/app/main.py` registra routers, CORS, tratamento de erros, migrações e processos de fundo.
- `backend/app/config.py` lê ambiente/`.env`; `database.py` configura engine, Base e sessões.
- `backend/app/dependencies.py` verifica JWT, sessão persistida, versão de acesso e usuário ativo; fornece as permissões aos endpoints.
- `backend/app/models/`, `schemas/`, `api/endpoints/`, `services/` representam persistência, contratos, transporte e regras.

## Onde alterar cada módulo

| Módulo | Frontend | API (prefixo `/api`) | Serviços/modelos principais |
| --- | --- | --- | --- |
| Login | `LoginView`, `stores/auth` | `auth` | `models/usuario`, `dependencies` |
| Acesso/auditoria | `AccountView`, `UserManagementView`, `AuditView`, `services/activity` | `auth`, `access` | `access_policy`, `user_sessions`, `user_audit`, `models/access`, CLI `user_access_setup` |
| Dashboard | `DashboardView`, `components/dashboard/*` | Resumos dos módulos | API de cada card; BI usa snapshots |
| Estoque | `views/inventory/`, `components/inventory/`, `stores/inventory` | `inventory`, `ocr` | `inventory_service`, `inventory_diagnostics`, `ocr_service`, `models/inventory`, `label_template` |
| Pedidos/clientes | `PedidosView`, `ClientesView`, componentes de pedidos/clientes | `pedidos`, `clientes`, `tags` | `models/pedido`, `cliente`, `pedido_tag`, `pedido_anexo` |
| Rastreio | `RastreamentoView`, `RastreamentoCard`, `stores/rastreamento` | `rastreamento` | `wonca_service`, `rastreamento_sync`, `models/rastreamento` |
| Equipe/folgas | `VendorManagement`, `FolgasCard`, `FolgasCalendarAdvanced` | `vendedores` | `models/vendedor`, `funcionario`, `folga`, `assistant_schedule` |
| Vendas operacionais | `VendasView`, `VendasImportCard` | `vendas`, `excel-import`, `dashboard` | `excel_import_service`, `models/venda` |
| Câmbio/transferências | `ExchangeRateManagement`, `stores/currency` | `exchange-rates`, `money-transfers`, `cambistas` | `thais_transfer_service`, modelos financeiros |
| PDV/fiado | `PDVView`, `FiadoView`, `components/pdv/`, `stores/pdv` | `pdv` | `models/pdv`, `inventory_service` para baixas/devoluções |
| Endereços/impressão | `AddressesView`, `components/addresses/` | `address-manager`, `printing` | `address_book`, `address_identity`, `address_usage`, `address_manager`, `assistant_printing`, `postal_codes`, modelos `address_book`/`printing` |
| Etiquetas | Aba SuperFrete em `AddressesView` | `freight` | `superfrete`, `superfrete_errors`, `assistant_freight`, `freight_recovery`, `freight_labels`, `freight_webhook` |
| Assistente | `AssistantView` | `assistant` | `assistant_*`, `models/assistant` |
| BI OneDrive | `SalesBiView`, `services/salesBi` | `sales-bi` | `sales_bi`, `sales_bi_parser`, `sales_bi_onedrive`, `sales_bi_sync`, `sales_bi_schedule` |

Nomes da tabela referem-se a arquivos em `frontend/src` e `backend/app`. O contrato
completo e atualizado é `/openapi.json`, gerado a partir dos routers, não uma lista
copiada manualmente para o README. Endpoints históricos continuam disponíveis enquanto
não houver uma migração explícita de seus consumidores.

## Processos e horários

| Processo | Entrada | Execução |
| --- | --- | --- |
| API | `uvicorn app.main:app` | Requisições HTTP e ciclo `lifespan` |
| Assistente | `assistant_worker.main` | Thread quando `ASSISTANT_EMBEDDED_WORKER=true`, ou CLI separada |
| Recuperação de etiquetas | `services.freight_labels.main` | Thread da API, independente do assistente |
| BI | `services.sales_bi_sync.main` | Thread da API; leitura às 18h Brasília ou pedido manual no banco |
| Atualização de rastreios | `_job_atualizar_rastreamentos` | APScheduler, às 19h Brasília |
| Impressão | `tools/eleven-print-agent/Agente.ps1` | PowerShell na sessão do Windows da loja |

Use uma instância/processo Uvicorn no arranjo atual. As filas do assistente/frete/BI
têm mecanismos de concorrência no PostgreSQL, mas o agendamento de rastreio é local
a cada processo da API. Escalar múltiplas instâncias requer revisar esse agendador.
O ciclo de desligamento sinaliza as threads e aguarda sua conclusão por prazo limitado.

## Caminhos de dados

**Conversa:** webhook validado → identidade ERP → mensagem persistida → worker →
DeepSeek/ferramentas → resposta ou prévia → confirmação humana → execução → fila de
entrega. `assistant_channels` isola os provedores; `assistant_tools` declara e despacha
ferramentas; `assistant_controls` vincula botões e confirmações às ações corretas.
`assistant_events` é importado por efeito de registro do evento transacional; não removê-lo
porque a variável importada não é referenciada diretamente.

**Endereço:** `address_identity` normaliza a identidade; `address_book` reutiliza ou
cria cadastro; `address_usage` reúne utilizações. `merged_into_id` preserva IDs antigos.
Snapshots de frete/impressão mantêm os dados usados na ocasião, mesmo após editar a agenda.

**Impressão:** `print_devices` identifica agentes; `print_jobs` mantém estado/idempotência;
`print_senders` e `print_layouts` definem remetentes/modelos. O agente consulta trabalhos,
baixa o PDF por autorização própria, chama Sumatra e comunica resultado. Estado incerto
não provoca reimpressão automática. Documentos avulsos têm um caminho temporário distinto
em `assistant_documents`, sem guardar conteúdo no banco.

**Frete:** `freight_orders` registra cotação/compra/etiqueta. Webhooks assinados apenas
agendam consulta autenticada. `freight_labels` recupera PDFs atrasados, persiste o documento,
enfileira impressão única e notificação; não repete pagamentos. `freight_recovery`
retenta cotações e criações comprovadamente recusadas, concilia criações incertas
pela identificação do pedido e devolve a confirmação do preço ao usuário.

**BI:** links configurados → OneDrive somente leitura → resultados XLSX salvos → parser →
`SalesBIWorkbook.snapshot` → agregação → frontend. Uma escolha por mês elimina sobreposição
entre atual/arquivo. `SalesBIConfig` contém fontes, agendamento, pedido manual e concessão
temporária de execução. Não passa pelo cadastro `Venda` ou pelo PDV.
`sales_bi_entry_parser` extrai linhas e `sales_bi_entries` agrega lançamentos/horários.
O filtro financeiro pessoal é aplicado antes de agregações ou paginação.

**Comprovante:** imagem Telegram autorizada → validação em memória → visão DeepSeek/Anthropic →
prévia com códigos/verificação → confirmação → rastreios e vínculos explícitos.
`receipt_vision` e `receipt_tracking` isolam leitura e gravação. Cadastro web e bot
compartilham locks por código normalizado; uma corrida não gera outro rastreio.

**Auditoria:** identidade autenticada → contexto da sessão SQLAlchemy → eventos das
mutações na mesma transação. Acessos HTTP são eventos separados. `AuthSession` controla
revogação e crédito de atividade; `ActivitySpan` agrega intervalos por módulo.

## Entidades que não são intercambiáveis

- `Usuario`: autenticação e perfil; `Vendedor`: vendas, apelidos e agenda; `Funcionario`: dados funcionais.
- `Cliente` e `PdvCliente`: cadastros separados, com IDs e relações próprios.
- `Venda`, `PdvSale` e `SalesBIWorkbook`: lançamento operacional, caixa/estoque e visão de planilha.
- `AssistantNote`: ocorrência confirmada; `AssistantAction`: autorização/execução de uma ação real.
- `AssistantKnowledge`: catálogo de capacidades e apelidos; não é cache de saldos ou rastreios.
- `SavedAddress`: endereço reutilizável; `PrintJob` e `FreightOrder`: utilizações independentes.

## Permissões e segredos

O frontend restringe navegação, mas a autorização efetiva deve estar no backend.
Somente Lucas tem ADMIN. Escopo financeiro pessoal é independente da permissão
operacional GERENTE; não é suficiente esconder filtros no frontend. Veja
[Acesso e auditoria](ACESSO_AUDITORIA.md).
Endereços e BI exigem ADMIN/GERENTE; administração do assistente, dispositivos e fontes
exige ADMIN. Cada identidade do bot se vincula a um usuário ERP e pode registrar apenas
se habilitada. Nem todo usuário com acesso ao grupo pode executar uma ação.

Chaves externas ficam no backend. Variáveis `VITE_*` são incorporadas ao JavaScript público
no build e nunca devem conter tokens. Credenciais do agente são protegidas no Windows e
armazenadas como hash no servidor. Segredo de webhook SuperFrete persistido usa cifra ligada
à `SECRET_KEY`; não rotacionar essa chave sem plano para os dados dependentes.
