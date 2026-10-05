# Deploy e operação

## Serviços de produção

- Frontend: site estático Render, `https://erp-eleven-frontend.onrender.com`.
- Backend: web service Python, `https://erp-eleven-backend.onrender.com`.
- Banco: PostgreSQL compartilhado entre API e workers.
- Impressora: agente PowerShell na máquina Windows da loja, fora do Render.

O repositório é publicado pela branch `main` com auto-deploy configurado nos serviços.
`render.yaml` é a referência versionada; confira diferenças com os serviços existentes
antes de reaplicar um Blueprint. Não use essa operação para substituir banco, segredos,
plano ou configuração já ativa inadvertidamente.

| Serviço | Build | Execução/publicação |
| --- | --- | --- |
| Backend | `pip install -r backend/requirements.txt` | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Frontend | `cd frontend && npm ci --include=dev && npm run build` | `frontend/dist` |
| Assistente separado, opcional | Mesmo build do backend | `cd backend && python -m app.assistant_worker` |

A sintaxe do Blueprint usa `type: web` e `runtime: static` para o frontend,
conforme a [referência oficial do Render](https://render.com/docs/blueprint-spec).
O servidor Express/Docker é uma alternativa local, não participa do site estático.

## Configuração

A lista de referência fica em `backend/.env.example`; nenhum valor real pertence ao Git.
O exemplo adicional `assistant.env.example` serve para habilitar integrações em uma base
que já tenha a configuração principal. O backend também lê o Secret File
`/etc/secrets/superfrete.env`, sem sobrescrever variáveis existentes no processo.

| Grupo | Variáveis | Uso |
| --- | --- | --- |
| Banco/autenticação | `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `TIMEZONE`, `LOG_LEVEL` | API, sessões, logs e fuso |
| Rastreio | `WONCA_API_KEY` | Atualização dos envios |
| Visão de imagens | `VISION_PROVIDER`, `DEEPSEEK_VISION_MODEL`, `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY` | OCR de estoque e comprovantes; `auto` prefere DeepSeek, com Anthropic opcional |
| Assistente | `ASSISTANT_ENABLED`, `ASSISTANT_EMBEDDED_WORKER`, `ASSISTANT_DAILY_MESSAGES`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` | Worker, limite e modelo |
| Telegram | `ASSISTANT_TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_GROUP_ID` | Grupo e webhook autenticado |
| WhatsApp | `ASSISTANT_WHATSAPP_ENABLED`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_WEBHOOK_URL` | Adaptador individual Twilio, opcional |
| SuperFrete | `SUPERFRETE_TOKEN`, `SUPERFRETE_CONTACT_EMAIL`, `SUPERFRETE_SANDBOX`, `SUPERFRETE_WEBHOOK_SECRET` | Etiquetas e assinatura opcional definida no ambiente |
| Frontend | `VITE_API_BASE_URL` | URL pública da API, incorporada no build |

`ACCESS_TOKEN_EXPIRE_MINUTES` era uma configuração antiga sem uso na criação do token.
O login aplica a regra implementada em `user_sessions`: meia-noite local sete dias à
frente, convertida para UTC. Alterar um valor antigo do ambiente não muda essa regra.

A configuração OneDrive fica em `sales_bi_config`, pelo painel **Fontes**, somente ADMIN.
Não há `MSAL_CLIENT_ID` ou OAuth Microsoft implementado nesse conector. Ele usa os links
compartilhados configurados para leitura. Dados de remetentes ficam no banco, não no código.

## Processos contínuos

No modo atual, `ASSISTANT_EMBEDDED_WORKER=true` inicia o bot em thread da API.
A recuperação de etiquetas e o agendador BI iniciam independentemente dessa flag.
Use um serviço que permaneça em execução e uma instância Uvicorn; não inicie outra
cópia local conectada à produção para testes. Veja [Arquitetura](ARQUITETURA.md).

- BI: 18h `America/Sao_Paulo` ou botão manual; recarregar dashboard consulta snapshots, não sincroniza OneDrive.
- Rastreios: atualização diária às 19h no mesmo fuso.
- Etiquetas: consultas progressivas após emissão até o PDF ficar disponível, sem novo pagamento. Cotações interrompidas e criações incertas também têm recuperação persistida; consulte as regras e os limites no [gestor](GESTOR_ENDERECOS_SUPERFRETE.md#recuperação-de-solicitações-e-diagnóstico).
- Bot: recebimento por webhook, execução/entrega por fila.
- Impressão: o Windows deve estar conectado, com sessão e agente abertos.

## Publicação de uma mudança

1. Revise o diff e confirme que não há segredos/artefatos privados.
2. Execute testes relevantes, tipagem e build; para esquema/locks, inclua homologação PostgreSQL.
3. Mantenha backup antes de alterações de banco. A API tenta `alembic upgrade head` ao iniciar.
4. Publique a revisão na branch configurada e acompanhe **Live** no Render para o commit correto.
5. Confira `/health`, logs de migração, carregamento do frontend e os fluxos afetados.

Falha de migração agora interrompe o startup; não há fallback silencioso de criação
de tabelas. Em falha de migração, investigar e corrigir por nova revisão;
não carimbar `head` em um esquema desconhecido para ocultar o problema.

A migração de acesso invalida tokens legados sem identificação de sessão. Planeje um
novo login e execute o provisionamento das cinco contas conforme
[Acesso e auditoria](ACESSO_AUDITORIA.md), preservando os IDs das identidades do bot.
Não redefina as senhas pessoais em uma atualização posterior.

Retornar o código a uma revisão anterior não reverte banco, pagamentos ou impressões.
Não executar downgrade destrutivo como reação automática a uma falha.

## Diagnóstico

| Sintoma | Conferir |
| --- | --- |
| Bot não responde | Flags, vínculo ativo do autor, grupo, segredo do webhook, filas no painel e worker |
| WhatsApp sem resposta | Habilitação externa do remetente, URL/assinatura Twilio e flag; ter token não comprova entrega |
| Emissão temporariamente indisponível | `error_category`, `recovery_kind` e próxima consulta; documento inválido pede correção, nunca zeros. Criação antiga sem ID/tag exige conferência no provedor |
| Etiqueta paga sem PDF | Estado do frete e worker de etiquetas; usar Consultar para recuperar, não pagar outra vez |
| Impressão parada | Agente Windows, driver, Sumatra, `last_seen_at`, estados pending/claimed/uncertain |
| BI não atualizou | Fontes, última leitura, próximo horário, erro por arquivo e salvamento do Excel |
| “—” nas vendas | Ausência de resultado/detalhamento; não substituir por zero nem redistribuir diferença |
| Endereço repetido | Número/complemento/documento/vínculo e normalização; não apagar usos históricos |

`/health` informa API, banco, assistente embutido e worker de etiquetas. Não atesta impressão
física, entrega de mensagens, saldo de provedor nem sucesso de sincronização BI. Banco offline
pode aparecer no JSON mesmo com HTTP 200; monitorar o conteúdo também. O estado de leitura
BI está em `/api/sales-bi/sources`, autenticado.

O agente tem credencial própria, limitada à impressora. Para substituir/revogar, use o fluxo
administrativo e reinstale a credencial no Windows; não copie token para URLs ou documentação.
Consulte os guias específicos antes de registrar novamente webhooks ativos.

## Verificação de publicação — 04/10/2026

- Cabeçalho unificado: `170ef02` / `0a89d49`; saudação e navegação de conta no mesmo cabeçalho do dashboard, com conferência visual desktop e 390px. Outras rotas mantêm a navegação de conta.
- Logística e recuperação: `26d0cb9`; RUC/C.I em PY, reconhecimento conservador de variantes de endereço, diagnóstico SuperFrete e recuperação sem repetir pagamento incerto.
- [CI 37257127551](https://github.com/ferreiraluc/erp-eleven/actions/runs/37257127551): **685 testes backend e 164 frontend passaram**, com PostgreSQL isolado, tipagem e build.
- Backup privado verificado antes da manutenção. Migração `c9d0e1f2a3b4` e as quatro colunas de recuperação conferidas no banco publicado; API, banco, worker do bot e worker de etiquetas online.
- Os arquivos servidos pelo frontend já contêm o cabeçalho integrado, as mensagens de recuperação e o campo RUC/C.I. A consulta autenticada somente leitura à SuperFrete retornou disponível.
- Uma consolidação dirigida preservou os dois IDs e seis usos históricos (duas impressões e quatro cotações). Solicitações antigas com documento inválido receberam diagnóstico, preservando o estado incerto e a mensagem anterior; nenhuma foi cobrada, recriada ou impressa.

A validação automatizada usa provedores simulados. A manutenção não emitiu etiquetas
nem enviou impressões ou mensagens de teste à operação. A aprovação do CI não atesta
saldo, documentos reais válidos nem disponibilidade contínua da transportadora.
