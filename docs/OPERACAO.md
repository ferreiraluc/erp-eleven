# Deploy e operação

## Serviços de produção

- Frontend: site estático Render, `https://erp-eleven-frontend.onrender.com`.
- Backend: web service Python, `https://erp-eleven-backend.onrender.com`.
- Banco: PostgreSQL compartilhado entre API e workers.
- Impressora: agente PowerShell na máquina Windows da loja, fora do Render.

O repositório é publicado pela branch `main`, com auto-deploy **After CI Checks Pass**
configurado no frontend e backend. Falhas de testes ou auditoria de dependências de
execução bloqueiam novas publicações automáticas. Deploy manual continua sendo um bypass
operacional: use apenas para uma revisão previamente validada.
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

`/live` informa apenas que a API responde. `/health` verifica o banco e o progresso
dos workers de assistente embutido, etiquetas e BI; devolve **503** se o banco está
indisponível, uma thread parou ou ficou dez minutos sem progresso. A consulta ao banco
é feita fora do event loop e fecha a sessão mesmo em erro. O Render usa `/health`
para admissão de deploy e recuperação de instâncias. Não atesta impressão física,
entrega de mensagens, saldo de provedor nem resultado correto da sincronização BI.
O estado de leitura BI está em `/api/sales-bi/sources`, autenticado.

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

## Confiabilidade e segurança — manutenção de 07/10/2026

### Proteções de aplicação

- Pool PostgreSQL: cinco conexões persistentes e até cinco extras por processo,
  pre-ping, reciclagem após 900 s e espera limitada. `DB_*` no `.env.example`
  permite ajustar os limites. Queries têm 30 s e espera por locks 10 s;
  tarefas excepcionais precisam de limite próprio, não desabilitar globalmente.
- O timeout de transações ociosas permanece opt-in: alguns fluxos de provedores
  ainda mantêm transações durante chamadas HTTP. Separá-los exige preservar
  idempotência, confirmação e locks específicos de cada operação.
- Limitação de login persistida, validação estrita de JWT e mínimo de 12 caracteres
  nas novas senhas. Senhas existentes não são redefinidas pelo deploy.
- Produção recusa segredo padrão/curto, algoritmo inesperado, banco não PostgreSQL
  e Telegram ativo sem segredo de webhook. **Não trocar `SECRET_KEY` às cegas**:
  dados de configuração cifrados também dependem dela; rotação exige migração.
- Logs técnicos registram método, rota-modelo, status, duração e ID gerado por
  requisição. Não registram query strings nem corpos. Há redação de segredos
  configurados, URLs, JWT, e-mail e CPF formatado e supressão de valores de exceções.
  A redação é defesa adicional, não garantia para texto livre arbitrário.
- A auditoria do produto continua registrando login e alterações; consultas e
  contadores operacionais não voltam a gerar eventos no painel de auditoria.
- FastAPI/Starlette/PyJWT e dependências Node afetadas receberam correções dirigidas.
  CI verifica `pip-audit` e dependências Node de execução, além dos testes existentes.
- A política de scripts permite apenas a própria origem e WebAssembly necessário
  ao OCR; bloqueia scripts inline e eval JavaScript. O vue-i18n 9 usa o modo JIT
  compatível com CSP, preservando traduções. A mensagem de carregamento foi movida
  para um arquivo estático.
- O Docker opcional usa usuário sem root. Produção permanece no runtime Python
  gerenciado pelo Render: não há Kubernetes, VPC AWS ou Redis para configurar aqui.

### Rede e recuperação no Render

Verificação no painel: backend Starter e banco Basic-256mb em Oregon, PostgreSQL 16,
sem réplica. A conexão do backend usa o hostname **interno** do Render. A regra
externa do banco foi reduzida de `0.0.0.0/0` ao IPv4 administrativo atual `/32`;
a rede interna continua permitida. O validador do Render rejeitou uma origem fora
da lista. O IP exato fica no painel, não no repositório público.

**Se mudar a conexão de internet do administrador**, atualize a regra `/32` em
PostgreSQL → Info → Networking antes de usar ferramentas externas. Site, Telegram
e agente Windows continuam usando HTTPS da API, sem conexão direta ao PostgreSQL.
Não restaurar `0.0.0.0/0` para contornar um IP administrativo desatualizado.

Recovery informa PITR dos últimos **três dias** no plano atual. Uma janela maior,
réplica/HA e capacidade adicional dependem de plano e orçamento. Nenhum plano foi
comprado ou aumentado nesta manutenção.

### Backup cifrado e teste de restauração

Ferramenta: `tools/operations/recovery.py`, executada pelo Python do backend.
Requisitos locais: `pg_dump`/`pg_restore` de versão compatível e `age`/`age-keygen`.
A ferramenta não importa a aplicação nem inicia workers. O backup passa diretamente
para a cifra age, sem dump em texto claro no disco. A conexão remota exige TLS
com validação do certificado e hostname. A restauração autentica o arquivo inteiro
antes de criar uma base local descartável, valida tabelas/constraints e remove
essa base ao terminar. Não aceita destino remoto nem sobrescreve banco existente.

```sh
# Preparação única; guardar a identidade privada em cofre separado também.
umask 077
mkdir -p "$HOME/.config/erp-eleven/recovery" "$HOME/.local/share/erp-eleven/recovery"
age-keygen -o "$HOME/.config/erp-eleven/recovery/identity.agekey"

# A chave privada nunca vai para o Render, Git ou argumentos de comandos.
backup_recipient=$(age-keygen -y "$HOME/.config/erp-eleven/recovery/identity.agekey")
backend/venv/bin/python tools/operations/recovery.py backup \
  --env-file backend/.env --recipient "$backup_recipient" \
  --output-dir "$HOME/.local/share/erp-eleven/recovery"

# Usar PostgreSQL local vazio para o exercício, nunca a URL de produção.
# Substituir USUARIO_LOCAL, porta e ARQUIVO pelos valores deste computador.
SRE_LOCAL_DATABASE_URL=postgresql://USUARIO_LOCAL@127.0.0.1:55439/postgres \
  backend/venv/bin/python tools/operations/recovery.py verify-restore \
  --archive "$HOME/.local/share/erp-eleven/recovery/ARQUIVO.dump.age" \
  --identity "$HOME/.config/erp-eleven/recovery/identity.agekey"
```

O manifesto `.dump.json` tem checksum, duração, versão Alembic, contagens e resultado;
não contém nomes de clientes ou credenciais. Mantê-lo junto do backup. Dumps podem
conter credenciais cifradas da aplicação: a identidade age **e** a chave original
`SECRET_KEY` precisam de custódia para uma recuperação completa. Não registrar
seus valores em tickets, relatórios ou logs.

Exercício de 07/10: backup de aproximadamente 10 MB criado em 50 s, restaurado em
PostgreSQL local em menos de 1 s, **50 tabelas**, revisão `a3b4c5d6e7f8`, nenhuma
constraint pendente de validação. Estes tempos medem somente exportação e restore
local, **não** o RTO do serviço completo. Um ensaio com dados artificiais comprovou
também a preservação de linhas e a exclusão apenas do banco temporário criado.

O arquivo cifrado está na pasta privada acima; a chave está na pasta de configuração.
Isto complementa o PITR, mas ambos os arquivos no mesmo laptop não constituem cópia
independente contra perda do equipamento. Pendente: cofre externo para a chave,
cópia off-site aprovada, retenção definida e automação dessa cópia. Não há rotina
nova apagando backups antigos. Meta sugerida a validar com a loja: RPO até 24 h da
cópia externa e RTO até 2 h, com ensaio mensal completo e sem disparar integrações.

### Pendências e critérios de acompanhamento

| Área | Evidência / limite atual | Próxima ação e sinal de alerta |
| --- | --- | --- |
| Rede/TLS | Banco acessível pela rede interna; acesso público restrito; HTTPS válido | Monitorar expiração com 30 dias de antecedência e testar conectividade após mudança de rede |
| CPU/RAM/IOPS | Banco 256 MB, uso de disco 0,81% de 15 GB no painel; amostra SQL sem locks, deadlocks ou transação ociosa | Observar pelo menos um ciclo de pico; atenção a memória >85%, OOM, CPU >80% por 15 min ou disco >80%. A amostra não comprova ausência de gargalos |
| Banco | 6 conexões na amostra incluindo auditoria, limite 103; TLS ativo nas conexões observadas; `pg_stat_statements` ausente | Medir p95 e queries lentas antes de índices; não habilitar extensões/reinícios ou rodar `EXPLAIN ANALYZE` de escrita indiscriminadamente |
| Alta disponibilidade | Uma API, um banco e um computador/impressora; sem réplica | Dimensionar plano/HA, backup de internet e nobreak; não há failover físico implementado |
| Acesso | Sessões revogáveis, escopo por vendedor e limite compartilhado | Trocar senhas iniciais, habilitar MFA nas contas de infraestrutura; MFA/passkeys no ERP e sessão HttpOnly ainda pendentes |
| Segredos | Scan do histórico Git sem achados; não certifica ausência de vazamentos fora do Git | Revogar/rotacionar tokens já compartilhados em conversa, coordenando Telegram/Twilio/Render e agente. Preservar capacidade de decifrar configurações |
| Dependências | Auditoria de execução integrada ao CI | Restam 4 avisos altos de desenvolvimento (`braces`/`micromatch`/`fast-glob` e configuração ESLint); acompanhar correção upstream sem `npm audit fix --force` ou downgrade incidental |
| Alertas/APM | Health real e notificações de falha do Render; logs técnicos sanitizados | Falta monitor independente, destino de alertas, APM/SIEM e retenção central. Definir responsáveis antes de configurar integrações externas |
| Conformidade | Dados de clientes, endereços, documentos e funcionários; histórico preservado | Definir finalidade, retenção, contratos e localização internacional dos dados com responsáveis. Esta manutenção não certifica conformidade legal |

Referências operacionais: [health checks](https://render.com/docs/health-checks),
[deploy após CI](https://render.com/docs/deploys#integrating-with-ci),
[rede do PostgreSQL](https://render.com/docs/postgresql-creating-connecting#restricting-external-access)
e [recuperação](https://render.com/docs/postgresql-backups).
