# Ativação do assistente Eleven

## Implementação desta entrega

- WhatsApp **1:1** via Twilio e **grupo Telegram**, com DeepSeek no mesmo backend.
- Consultas de pedidos/rastreios, inclusive envios sem pedido vinculado.
- Memória compartilhada de relatos operacionais confirmados. Histórico de conversa é separado por canal/conversa/tópico; WhatsApp privado não é enviado ao contexto do grupo.
- Rascunhos de atendimento, devolução, pedido, venda e endereço. Isso **não** lança uma venda, altera endereço do pedido, movimenta estoque ou emite reembolso.
- Publicação automática de código novo no grupo Telegram, depois do commit do ERP.
- Painel de administrador em **Dashboard → Assistente IA** (`/assistente`): configuração, acessos, registros e fila.
- Worker persistente, mensagens únicas, limites de processamento, tentativas controladas e tratamento de envio incerto.

Imagens, áudio, impressão HP/Windows e operações financeiras permanecem etapas posteriores. A leitura OCR atual do ERP não foi alterada. Esta entrega não cria contas, compra números, registra bot no BotFather nem publica serviços automaticamente.

## 1. Configuração do servidor

Instale `backend/requirements.txt` no ambiente da API e do worker. Use `backend/assistant.env.example` como referência e configure as variáveis no ambiente seguro de ambos; não envie chaves em mensagens ou salve valores reais em arquivos versionados.

Use o mesmo PostgreSQL e as mesmas variáveis nos dois processos. Antes de habilitar, aplique a migração em ambiente de teste e depois no ambiente de destino:

```sh
cd backend
alembic upgrade head
python -m app.assistant_setup check
```

O assistente vem com `ASSISTANT_ENABLED=false`. Cada canal tem uma chave independente: `ASSISTANT_TELEGRAM_ENABLED=true` e `ASSISTANT_WHATSAPP_ENABLED=false` por padrão. A pausa impede recebimento, processamento e envio pelo canal; filas pendentes são preservadas. O status do painel informa presença de configuração, não comprova que as credenciais ou conexões funcionam.

Para o piloto no serviço Starter existente do Render, configure `ASSISTANT_EMBEDDED_WORKER=true` na API. O processamento inicia em uma thread dedicada depois da migração, usa sessões próprias e não bloqueia o loop HTTP durante chamadas de IA. `/health` informa `assistant_worker=online`; retorna HTTP 503 se essa thread parar. O serviço deve permanecer ativo: o plano Free, que hiberna sem tráfego, não atende operação contínua. Não é necessário um segundo serviço para esse modo.

Para separar a execução futuramente, configure `ASSISTANT_EMBEDDED_WORKER=false` na API e crie um **Background Worker** com:

```text
Build: pip install -r backend/requirements.txt
Start: cd backend && python -m app.assistant_worker
```

O worker separado necessita serviço que permaneça em execução. Configure as variáveis do exemplo também no serviço web. Não execute o worker pelo APScheduler da API. Em desenvolvimento, inicie o mesmo comando em outro terminal. Durante reinícios ou deploys sobrepostos, locks PostgreSQL impedem processamento simultâneo da mesma fila; resultados de envio incerto continuam sem repetição automática.

## 2. Número WhatsApp na Twilio

Cadastre um remetente WhatsApp na conta Twilio e conclua o processo de habilitação. Para piloto, o Sandbox do console legado permite respostas livres na janela de atendimento com funcionários que tenham aderido a ele, quando disponível na conta.

**Atenção ao novo trial (Try out WhatsApp):** ele é diferente do Sandbox legado. A API de envio do trial exige `ContentSid` de um dos modelos fornecidos pela Twilio e não aceita o texto livre produzido pela IA. Enviar `join` ou uma nova mensagem ao número de teste não remove essa restrição. O chatbot desta implementação precisa de uma conta/remetente habilitado para texto livre; não substitua a resposta por um template fictício para contornar a limitação. Referências: [restrições do Try out WhatsApp](https://www.twilio.com/docs/usage/trials/try-out-whatsapp) e [Sandbox legado](https://www.twilio.com/docs/whatsapp/sandbox).

Configure:

- `TWILIO_ACCOUNT_SID`: conta do remetente.
- `TWILIO_AUTH_TOKEN`: usado para validar assinatura e autenticar envio.
- `TWILIO_WHATSAPP_FROM`: endereço completo `whatsapp:+DDINUMERO`.
- `TWILIO_WEBHOOK_URL`: URL pública exata `https://SEU-BACKEND/api/assistant/webhooks/twilio`.

No remetente/Sandbox, selecione essa URL para mensagens recebidas, método **POST**. A assinatura é validada usando a URL pública configurada, sem confiar no host interno do proxy. Use HTTPS; não acrescente barra final ou query string sem atualizar a URL exata.

As respostas desta versão são mensagens de texto dentro da janela de atendimento. O worker expira respostas atrasadas antes de 24 horas; não inicia disparos privados fora dessa janela e não possui templates de envio proativo. Avisos automáticos de rastreio vão ao **Telegram**.

## 3. Bot e grupo Telegram

Uma pessoa cria o bot com **@BotFather** e cria/seleciona o grupo. O bot não cria sozinho esse grupo por meio desta implementação.

1. No BotFather, use `/newbot`, escolha nome e username e guarde o token em `TELEGRAM_BOT_TOKEN`.
2. Defina `TELEGRAM_BOT_USERNAME` sem `@` e adicione o bot ao grupo interno de funcionários. Ele precisa poder enviar mensagens; não são necessários poderes de administrador para a lógica do ERP.
3. Para observar as conversas comuns, desative o modo de privacidade com `/setprivacy` no BotFather. Siga a orientação do Telegram sobre remover/adicionar novamente o bot se necessário. Se mantiver o modo de privacidade, a interação funciona pelas mensagens/comandos que o Telegram entregar ao bot, mas não haverá leitura geral.
4. Antes de configurar o webhook, cada funcionário envia `/start@USERNAME_DO_BOT` no grupo. Execute `python -m app.assistant_setup telegram-discover` para listar somente os IDs de chats e autores recebidos. Essa operação não imprime textos das conversas, não envia mensagens e não remove webhooks existentes.
5. Coloque o ID do grupo em `TELEGRAM_GROUP_ID` (geralmente negativo). Use os IDs de usuários para os vínculos no painel. Nome e username não substituem ID numérico.
6. Gere um segredo aleatório forte e configure `TELEGRAM_WEBHOOK_SECRET` (32–256 caracteres alfanuméricos, `_` ou `-`). Guarde-o no ambiente seguro.
7. Com migrações, vínculos e serviços prontos, habilite o assistente nos dois serviços e registre o webhook:

```sh
cd backend
python -m app.assistant_setup telegram-webhook --url https://SEU-BACKEND/api/assistant/webhooks/telegram
python -m app.assistant_setup telegram-info
```

O comando de webhook mantém atualizações pendentes. O teste inicial deve ser feito com mensagens de teste e antes do uso real. `telegram-discover` requer que não haja webhook existente; ele não interrompe uma integração em funcionamento.

Somente o grupo configurado é aceito. Mudar o grupo exige atualizar a variável nos serviços. Mensagens de outros bots, administradores anônimos, canais, edições e remetentes não vinculados são ignoradas. Tópicos de supergrupos têm contextos separados e recebem resposta no mesmo tópico; avisos automáticos vão ao grupo geral.

## 4. Vínculos e memória

Entre no ERP como ADMIN e abra **Assistente IA**. Para cada funcionário:

- Cadastre `whatsapp:+DDINUMERO` vinculado ao usuário ERP correto.
- Cadastre o ID numérico Telegram vinculado ao **mesmo usuário ERP**.
- Ative “Pode registrar ocorrências” apenas para quem deve criar/confirmar registros. O padrão é consulta.

Confirme os identificadores diretamente com o funcionário. Não é permitido reatribuir uma identidade existente a outro usuário pelo painel. Desative acessos quando alguém sair da equipe. O grupo deve ser restrito a pessoas autorizadas a ver os dados operacionais publicados nele; a autorização de quem pergunta não impede outros membros de lerem a resposta.

Exemplos:

```text
WhatsApp: Tem o rastreio do João?
Telegram: /rastreio João
Telegram: @USERNAME_DO_BOT tem o rastreio do pedido 123?
Qualquer canal: /registrar Chegou a devolução do pedido 123, camiseta M.
Após revisar o rascunho: /confirmar ID_COMPLETO
Para descartar: /cancelar ID_COMPLETO
Para consultar depois em outro canal: /memoria pedido 123
Ajuda: /ajuda
```

A confirmação é feita pelo autor, identificado pelo mesmo usuário ERP, e expira em 24 horas. A ferramenta de IA não consegue aprovar seu próprio rascunho. O texto confirmado fica disponível à equipe nos dois canais. Histórico bruto privado e rascunhos não são usados na busca compartilhada. Administradores podem inspecionar rascunhos no painel.

Em grupo, o bot responde a seus comandos, menções, respostas a ele e consultas diretas de envio, como “Tem o rastreio do João?”. Mensagens comuns recebidas são analisadas em modo de observação; fatos operacionais claros podem gerar um rascunho para confirmação. Conversas sem ocorrência ficam sem resposta. O limite padrão é de 100 mensagens recebidas por usuário em 24 horas, somando canais; excesso é ignorado sem gerar nova chamada ao modelo.

## 5. Teste de aceitação ao ativar

1. Funcionário cadastrado pergunta pelo rastreio em cada canal. Confirme que os dados correspondem ao ERP.
2. Teste dois clientes com o mesmo nome e múltiplos envios; o assistente deve pedir identificação.
3. Registre ocorrência pelo WhatsApp, revise e confirme; consulte `/memoria` no Telegram.
4. Verifique que mensagem privada não confirmada não aparece na memória do grupo.
5. Cadastre um rastreio de teste pelo fluxo normal do ERP; confirme um aviso no Telegram após salvar.
6. Reenvie o mesmo webhook em ambiente de teste; não deve gerar novo registro/resposta.
7. Teste remetente não cadastrado e acesso revogado; nenhum dado deve ser retornado.
8. Confira o painel: mensagens processadas, envios aceitos pelo provedor e eventuais falhas.

## Operação e limites

- Para pausar, configure `ASSISTANT_ENABLED=false` e reinicie API e worker. Filas ficam preservadas; não são apagadas.
- Para deixar apenas o WhatsApp em standby, mantenha `ASSISTANT_WHATSAPP_ENABLED=false`, mesmo com as chaves Twilio cadastradas. Após o upgrade, confirme o remetente e o webhook antes de habilitar esse canal.
- `pending`: aguardando worker; `failed`: falha após limite; mensagens com falha podem ser reprocessadas pelo administrador.
- `accepted`: o provedor aceitou, não comprova entrega/leitura. Recebimento de status de entrega não está implementado nesta versão.
- `uncertain`: houve timeout/interrupção e o provedor pode já ter enviado. Não há retentativa automática nem botão de reenvio indiscriminado. Conferir no canal antes de qualquer intervenção.
- `expired`: resposta WhatsApp perdeu a janela; funcionário deve enviar outra mensagem.
- O processamento usa locks PostgreSQL. Testes unitários usam SQLite apenas em ambiente isolado, sem validar comportamento real de concorrência PostgreSQL.
- Retenção automática, métricas de cobrança/token, alertas externos e painel de reimpressão não estão implementados. O limite diário e o máximo de quatro chamadas ao modelo por mensagem limitam uso, mas não são um teto financeiro em moeda.
- Segredos ficam nas variáveis de ambiente. Conteúdo de mensagens não aparece na fila administrativa; os registros operacionais aparecem para ADMIN. O banco contém textos recebidos e requer política de acesso/retencão da empresa.

## Validação local

```sh
cd backend
pip install -r requirements-dev.txt
python -m pytest tests/test_assistant.py -q
```

As chamadas externas são simuladas. Não chamar endpoints de produção ou aplicar migração no banco real apenas para executar estes testes.

Os testes reais de conectividade e DeepSeek realizados em 20/09/2026 estão registrados em [ASSISTENTE_TESTES_INTEGRACAO.md](ASSISTENTE_TESTES_INTEGRACAO.md). A memória foi validada com dados fictícios em banco temporário; também houve consulta de um pedido real em transação somente leitura. Esses testes não representam ativação contínua em produção.

Fontes: [Twilio: validação de requisições](https://www.twilio.com/docs/usage/security), [Twilio: WhatsApp](https://www.twilio.com/docs/whatsapp/api), [Telegram Bot API](https://core.telegram.org/bots/api), [Telegram: privacidade](https://core.telegram.org/bots/features#privacy-mode), [DeepSeek: API](https://api-docs.deepseek.com/).
