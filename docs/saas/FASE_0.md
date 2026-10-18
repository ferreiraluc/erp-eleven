# Fase 0 — discovery, segurança e baseline

Data: 18/10/2026. Fonte: código fixado, documentação existente, Issues #70 e #51 e
documentação pública oficial do Render. Não houve consulta ao banco, painel, logs,
URLs operacionais ou segredos da loja. Informações sobre recursos ativos abaixo são
as documentadas no repositório, **não uma inspeção do estado atual de produção**.

## Snapshot e isolamento de trabalho

| Evidência | Valor |
| --- | --- |
| Commit | `a2f7178a56560924b39e91fa16ed744999a326bd` |
| Commit tree | `aa081f956c49fbf36c6763878bd6aea46c642114` |
| SHA-256 de `git archive --format=tar COMMIT` | `3a340c564a879cf9fec8fd6b86c985276764f5deee9f2e019d0c586d139b233d` |
| Origem | `main` remoto e checkout local coincidiam no início |
| Branch de documentação | `codex/issue-70-phase-0` em clone local sem hardlinks |
| Fonte inventariada | 709 arquivos rastreados, com SHA-256 individual em `phase-0/baseline.json` |
| Backend | 253 operações HTTP, 49 tabelas ORM, nenhuma com `tenant_id` |
| Alembic | 47 arquivos/revisões; bases `847cdc1e7e5a` e `9572ac0c4129`, head `m5b6c7d8e9f0` |

O diretório de trabalho original não foi trocado de branch nem editado. Arquivos
locais não rastreados e `.env` não entraram no clone. O snapshot inclui somente
conteúdo versionado; não inclui banco, PDFs operacionais, fotos de clientes, backups,
credenciais Windows, secret files do Render ou planilhas OneDrive.

Coordenar com [#51](https://github.com/ferreiraluc/erp-eleven/issues/51): manter no
produto novo o versionamento de assets e a recuperação de carregamento; não alterar
os dropdowns, teclados, categorias ou CI originais nesta missão. Avaliar futuros
commits da #51 por diff e testes em PR do novo repositório. Nunca promover a cópia de
volta ao ERP original por merge de branches.

## Inventário de serviços e efeitos

| Área / entrada | Persistência e fronteira atual | Tratamento para a cópia |
| --- | --- | --- |
| Vue 3, Pinia, router hash, Axios | JWT em session/local storage; estado por navegador | Origem própria, URL de API explícita; limpar estado ao trocar identidade; conservar guardas e traduções |
| FastAPI `app.main` | Engine e sessões globais; routers usam SQLAlchemy diretamente | Uma engine/processo/banco por empresa; contexto imutável de instância |
| Startup `lifespan` | Executa Alembic, escreve catálogo do assistente, inicia threads e cron | Não iniciar cópia bruta; migrations explícitas e flags separadas para cada processo |
| Autenticação e acesso | `usuarios`, `auth_sessions`, `login_throttles`; JWT HS256, versão e revogação | Segredo único por instância; remover proprietário fixo apenas na cópia; identidade superadmin separada |
| Estoque / OCR / fotos | Itens, fornecedores, contagens, movimentos, lotes; imagens em DB; miniaturas | Manter locks e snapshots; bloquear upload/OCR/edição IA quando módulo ou cota negado |
| Clientes, pedidos, anexos, tags | Vínculos explícitos; anexos e documentos com autorização | Testes de objeto estrangeiro, URL direta, download e cache |
| PDV / fiado / câmbio | `pdv_*`, taxas e pagamentos; revisão, baixa/devolução na transação | Não somar com BI ou `vendas`; nenhuma transação financeira real em smoke test |
| Vendas operacionais / importação | `vendas`; conector histórico Graph em `excel_import_service` | Fluxo próprio; não confundir com o conector BI somente leitura |
| BI / `sales_bi_sync` | Config singleton, leases, snapshots e fontes privadas no DB | 18h Brasília/manual; sem fontes reais; dashboard não dispara sincronização |
| Rastreamento | Wonca; endpoint legado de cálculo Correios em HTTP; `scheduled_runs` | `shipping.tracking` em API, agregações, bot, cron e refresh compartilhado; revisar protocolo legado antes de habilitar |
| Assistente / webhooks | Telegram e Twilio, identidades, mensagens, ações, outbox e memória | Desligado; sem setup/webhook real; catálogo e dispatch sujeitos a licença e RBAC |
| Etiquetas / SuperFrete | Compra, recuperação, webhook assinado, PDFs, confirmação e idempotência | Desligado; sandbox/mocks sem gastar saldo; não repetir compra incerta |
| `freight_labels` | Thread sempre inicia no original, mesmo sem assistente | Flag própria; nenhum acesso a provedor ou enfileiramento quando desativada |
| Impressão A4 / tickets | Dispositivos, jobs, snapshots; pull HTTPS por PowerShell Windows | Instância, credencial, diretório e fila novos; nunca instalar/acionar agente da loja |
| Equipe / folgas | Vendedores, funcionários e calendário; escopo financeiro distinto | Preservar acesso pessoal antes de somar/paginar; identidades sintéticas |
| Endereços / 4Devs / CEP | Agenda, aliases, remetentes e usos; ViaCEP/4Devs externos | Não chamar provedores durante smoke offline; PY e CPF ausente mantêm regras |
| Auditoria / logs | Eventos na transação, redação técnica; histórico de atividade preservado | Contexto de tenant e ator; nenhuma chave, prompt, CPF ou payload em logs centrais |
| Backup / recuperação | `tools/operations/recovery.py`, pg_dump/restore + age | Restore apenas em DB local novo; cifrar backup e guardar chave separadamente |
| Render / CI | Frontend estático, API Python, PostgreSQL; workflows sem deploy | Blueprint/pipeline novos, sem vincular infraestrutura ou hooks antigos |

Entradas ativas que não podem ser descartadas por falta de importadores:
`assistant_setup`, `superfrete_setup`, `user_access_setup`, manutenção/reconciliação
de clientes/endereços, `assistant_worker`, serviços de BI/frete e agente PowerShell.
`assistant_events` registra listeners transacionais por import; a cópia deve preservar
esse efeito e condicionar a execução à política da instância.

Os CSVs são inventários de contrato HTTP e metadados ORM, não provas de autorização.
`declared_dependencies` registra parâmetros `Depends` da função; não certifica todas
as checagens internas, dependências transitivas, jobs, listeners ou CLIs. A Fase 2
deve revisar cada superfície e ligar cada operação a permissão/módulo/tenant.

## Acoplamentos concretos encontrados

| Local | Acoplamento / consequência |
| --- | --- |
| `render.yaml` | Nomes `erp-eleven-*`, banco `eleven` e API da loja; nunca reaplicar para a cópia |
| `frontend/.env.production` | Build sem override aponta à API da loja; retirar no novo repo e exigir URL explícita |
| `backend/app/main.py` | CORS com domínios da loja; startup migra e inicia cron/BI/frete |
| `backend/app/config.py` | Procura `.env`, `/etc/secrets/superfrete.env` e `/etc/secrets/openai.env`; defaults de DB/segredo inadequados para SaaS |
| `services/access_policy.py`, auth e CLIs | `OWNER_EMAIL` fixo; um ADMIN arbitrário não é aceito; precisa política por empresa |
| `user_access_setup`, conhecimento e aliases do BI | Provisionamento e convenções da equipe Eleven; não usar como seed SaaS |
| `services/pdv_receipt_layout.py`, assets, manifest e traduções | Nome, localização e contato fixos; branding deve vir de configuração versionada |
| `tools/eleven-print-agent/Instalar.ps1` e `Agente.ps1` | Servidor fixo da loja; não basta trocar o frontend para isolar impressão |
| `database.py`, workers, cron, caches e locks | Banco/estado globais; ausência de tenant em todas as tabelas; isolamento atual é por instalação |
| Migrações e modelos | `models.__init__` não importa todos os modelos; `create_all` sozinho não inclui todo DDL de migrações |

## Matriz de riscos e gates

| ID | Severidade | Risco demonstrado ou previsto | Mitigação / critério de liberação |
| --- | --- | --- | --- |
| R01 | Crítica | Cópia usa URL, secret file, token ou DB da loja | Ambiente explícito sem dotenv implícito; denylist + allowlist de recursos novos; testes negativos antes de startup |
| R02 | Crítica | Startup dispara migração, BI, frete ou bot | Modo isolado com bloqueio de efeitos; flags de todos os workers/CLIs; teste sem egress |
| R03 | Crítica | Query por ID/exports/prints cruza empresas em banco compartilhado | Piloto com processos, DBs e segredos separados; sem schema compartilhado até revisão integral e testes adversariais |
| R04 | Alta | Migração não instala banco vazio | Novo baseline SaaS explícito, preservando migrações originais; PostgreSQL vazio e upgrade testados |
| R05 | Alta | ORM não reproduz triggers, índices, sequences e backfills | Inventariar DDL: pg_trgm, thumbnail trigger, códigos INV, índices parciais/únicos; não declarar `stamp head` como solução |
| R06 | Crítica | Agente entrega documento à loja ou duplica print/compra | Identidade/tenant/fila exclusivos, confirmação original e idempotência; estados incertos exigem conciliação |
| R07 | Alta | Esconder menu sem bloquear API/jobs/bot | Política central no backend e em cada efeito; testes Start por todos os caminhos de rastreio |
| R08 | Alta | Token admin de empresa vira superadmin | Aplicação, audience, chaves, sessões e MFA separados; sem login por e-mail fixo |
| R09 | Alta | Eventos billing duplicados/atrasados liberam licença indevida | Inbox única, assinatura, reconciliação, versões e outbox transacional; falha fechada |
| R10 | Alta | Cache conserva licença removida / job já enfileirado | Versão monotônica por tenant; checar novamente antes do efeito, não só no enqueue |
| R11 | Alta | Cópia perde dados em suspensão/rollback | Read-only/export autorizado; sem DELETE nem downgrade automático; backup e release compatível |
| R12 | Alta | Provisionamento aceita recurso antigo/arbitrário | Identidade Render sem acesso à loja + registry de ownership; rejeitar qualquer recurso desconhecido |
| R13 | Alta | OOM e custo inviabilizam Start de US$29 | Medir carga por tenant; orçamento conservador; não prometer margem/SLA com 512 MB |
| R14 | Alta | Vazamento em logs, IA, cache, anexos, suporte | Dados e chaves segregados; quotas transacionais; logs sem conteúdo; suporte autorizado com prazo/auditoria |
| R15 | Média | Mudanças #51 divergem da nova base | Snapshot fixo, registro de cherry-picks e testes; sem sincronização automática |
| R16 | Alta | Blueprint com nomes existentes reconfigura serviço original | Novo namespace e repositório; previews desligados; não executar Blueprint sem revisão de owner/IDs/custo |

## Testes e restauração executados

| Verificação | Resultado e limite |
| --- | --- |
| Backend completo | **1.332 passaram**, 46 avisos de depreciação, 80,55 s; Python 3.13 local; CI deve validar Python 3.11 |
| PostgreSQL | Cluster novo PostgreSQL 17, loopback porta 55470; `ACCESS_TEST_DATABASE_URL` explicitamente local; nenhum teste PG ignorado |
| Contenção de testes | Ambiente limpo, `PYTHON_DOTENV_DISABLED=1`, DB padrão SQLite; conexões socket fora de loopback recusadas no processo pytest |
| Frontend | **493 testes / 78 arquivos passaram**, Node 22; `type-check`, build e `check-build.mjs` passaram |
| Build isolado | `VITE_API_BASE_URL=http://127.0.0.1:8000`; sem servidor público ou chamada à API da loja |
| Restore cifrado | `pg_dump` → age → verificação → DB local novo → `pg_restore`; 50 tabelas, contagens esperadas iguais, zero constraints não validadas |
| Fonte do restore | 49 tabelas ORM, 3 registros sintéticos (usuário, cliente, produto), mais marcador `phase0_metadata_fixture`; sem senha utilizável |
| Bootstrap vazio | **Falhou como previsto**: revisão `9572ac0c4129` exige tabela `vendas` preexistente. Saída não zero registrada; não ocultada com stamp |
| CI Windows/security | Checks obrigatórios do PR; não executados por emulação local de impressão |

O ensaio comprova o mecanismo de backup/restore e a preservação das contagens de
uma fixture. **Não** comprova restauração de produção, paridade de todo o esquema
migrado, recuperação de credenciais, RTO de serviço, impressão física, integrações
reais ou isolamento entre tenants. `Base.metadata.create_all` foi usado somente
nessa fixture, nunca como bootstrap comercial. O marcador artificial não é o head
Alembic do ERP. O arquivo cifrado e sua chave sintética ficam fora do Git.

## Orçamento estimado e escolhas

Valores em USD/mês, referência pública consultada em 18/10/2026; estimativas de
infraestrutura, não cotação vinculante. Revalidar no plano de aprovação. O preço
do workspace é separado do compute. Preços de assinatura do SaaS continuam os
defaults configuráveis Start 29 / Pro 59 / Business 119 da Issue #70.

| Componente | Referência mensal | Hipótese |
| --- | --- | --- |
| API pequena | US$7 | `0.5c-512mb`; apenas baseline de custo, já há histórico de OOM na loja |
| API com mais memória | US$25 | `1c-2g`; sugestão para ensaio de carga, não garantia de capacidade |
| PostgreSQL pequeno | US$6 | `0.1c-256mb`, compute |
| PostgreSQL com mais memória | US$19 | `0.5c-1g`, compute |
| PostgreSQL storage | US$0,30/GB | Orçar 5 GB = US$1,50 por DB, sujeito a mínimo/condições na contratação |
| Frontend estático | US$0 de compute | Tráfego/build/domínios podem gerar cobranças |
| Workspace Hobby / Pro | US$0 / US$25 | Pro permite isolamento de rede por ambiente; não é o plano Pro do SaaS |
| Worker adicional | +US$7 ou mais | Se separado da API, por instância |

Fontes: [preços Render](https://render.com/pricing),
[modelo de custo e workspace](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses),
[IDs de compute](https://render.com/docs/compute-plans),
[isolamento e limites dos planos](https://render.com/docs/platform-features-by-plan).

| Cenário calculado | Compute + 5 GB por DB + workspace |
| --- | --- |
| Trabalho local atual | **US$0 de infraestrutura Render criada** |
| Staging mínimo, um ERP, Hobby | 7 + 6 + 1,50 = **US$14,50/mês** |
| Staging mais memória, Pro | 25 + 19 + 1,50 + 25 = **US$70,50/mês** |
| 2 tenants mínimos + Control Center mínimo + workspace Pro | 3 × 14,50 + 25 = **US$68,50/mês** |
| 3 tenants mínimos + Control Center mínimo + workspace Pro | 4 × 14,50 + 25 = **US$83/mês** |
| 2 tenants com mais memória + Control Center mínimo + Pro | 2 × 45,50 + 14,50 + 25 = **US$130,50/mês** |
| 3 tenants com mais memória + Control Center mínimo + Pro | 3 × 45,50 + 14,50 + 25 = **US$176/mês** |

Fórmula: `workspace + control_plane + N × (API + DB + storage + worker opcional)`.
Staging permanente é adicional se mantido durante o piloto. Não incluídos: impostos,
gateway, IA/OCR/imagens, fretes, domínios, builds excedentes, egress, backups externos,
monitoramento, suporte e contingência. Reservar 20–30% para variáveis de infra não é
um teto para IA; IA precisa de teto próprio configurável e bloqueio antes da chamada.
CI privado usa as franquias existentes; não habilitar cobrança extra de Actions.

Com o perfil de US$45,50 por tenant, o Start a US$29 não cobre sequer essa infra.
Mesmo no perfil mínimo sobram US$14,50 antes do rateio, gateway, IA e suporte.
O piloto de isolamento forte valida segurança/produto; unit economics e limites
precisam de medição antes de vender ou prometer margem. Não trocar isolamento por
economia sem a revisão de tenancy prevista na Fase 2.

## Checklist de não regressão e próximo passo

- [x] Snapshot fixo, hashes e clone de trabalho independente.
- [x] Original sem edição de código, branch, CI, Render, DNS, secrets ou banco.
- [x] Sem chamadas a provedores, agente, pagamento, planilha ou webhook da loja.
- [x] Testes locais completos com dados artificiais e PostgreSQL descartável.
- [x] Restore sintético documentado; bootstrap vazio bloqueador reproduzido.
- [x] Inventário, riscos, desenho de dados, tenancy e orçamento registrados.
- [ ] Quatro checks do PR aprovados antes de qualquer integração de documentação.
- [ ] Fase 1: repo privado, configuração segura, novo baseline DB e Blueprint inerte.
- [ ] Gate futuro: aprovação de custo/endpoint e projeto independente para staging.

Nenhum merge no repositório original é parte desta execução. O próximo trabalho
seguro é criar a cópia privada e impedir, por código e testes, que qualquer caminho
de configuração aponte à loja. Só então preparar a aprovação concreta do staging.
