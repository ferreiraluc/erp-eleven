# Verificação de integração — 20 e 21/09/2026

## Estado atual — 21/09/2026, ativação do WhatsApp

- Twilio: conta `Full`, status `active`; remetente `+595 992 036654` confirmado `ONLINE` pela API v2. O remetente antigo de teste não é mais usado pelo ERP.
- Webhook do remetente salvo como POST para `https://erp-eleven-backend.onrender.com/api/assistant/webhooks/twilio` e relido pela API para confirmar a configuração.
- Render: `ASSISTANT_WHATSAPP_ENABLED=true`, `TWILIO_WHATSAPP_FROM` atualizado e `TWILIO_WEBHOOK_URL` canônico. Outras credenciais e a ativação do Telegram foram preservadas. O worker local permanece desabilitado.
- O WhatsApp previamente verificado do proprietário foi vinculado ao mesmo usuário ADMIN do Telegram, com as mesmas permissões. A memória de ocorrências confirmadas continua compartilhada; histórico e confirmação de prévias permanecem na conversa de origem.
- Publicação `2eb3093`: [deploy concluído](https://dashboard.render.com/web/srv-d29uhc6r433s739t1b30/deploys/dep-daoss20473hc739nqh30). API, banco e worker online. Webhook WhatsApp sem assinatura retornou 403; payload de verificação assinado, sem mensagem, retornou 200 sem gerar resposta.
- Telegram: conversa normal sem comandos comprovada. Após a correção, “Qual o rastreio do Vandilson?” gerou duas mensagens distintas aceitas em ordem (55 e 56), com código sozinho e dados atuais do ERP.
- Teste completo WhatsApp ainda aguardando a primeira mensagem do proprietário ao número aprovado. Não houve mensagem recebida pelo ERP até esta verificação; portanto, a entrega de uma resposta WhatsApp ainda não está comprovada.
- Correção adicional: a IA não pode apresentar uma prévia textual sem persistir a solicitação correspondente. Teste reproduziu o caso e confirmou cadastro somente após “confirmo”, em banco isolado; nenhum cadastro fictício foi criado em produção. Um teste com data já ocupada foi corretamente recusado sem duplicação.
- Versão final `997ac27`: [deploy concluído às 21h46](https://dashboard.render.com/web/srv-d29uhc6r433s739t1b30/deploys/dep-daosve0473hc739nt130), incluindo a correção das prévias.
- Validação atual: 54 testes automatizados passaram. Chamadas reais à DeepSeek validaram recuperação de rastreio antigo e preparação/confirmação de folga com permissões preservadas.

Os registros abaixo são históricos e descrevem os estados anteriores do piloto.

## Atualização: piloto Telegram publicado às 23h10 (Brasília)

- Código em produção: `7c09d7697026417f9aac4167b97386e8189c8598`, branch `main`.
- Backend: [deploy concluído no Render](https://dashboard.render.com/web/srv-d29uhc6r433s739t1b30/deploys/dep-dao924ks728c73bf89f0), usando o serviço Starter existente. Nenhum serviço pago adicional foi criado.
- Frontend: [deploy concluído](https://dashboard.render.com/static/srv-d2a0imogjchc73e4250g/deploys/dep-dao924ks728c73bf89cg). Painel em [Assistente IA](https://erp-eleven-frontend.onrender.com/assistente), com login ADMIN.
- As variáveis DeepSeek, Telegram e Twilio foram copiadas para o ambiente do backend. A conexão de banco e os demais segredos já existentes no Render foram preservados.
- No Render: `ASSISTANT_ENABLED=true`, `ASSISTANT_TELEGRAM_ENABLED=true`, `ASSISTANT_EMBEDDED_WORKER=true` e `ASSISTANT_WHATSAPP_ENABLED=false`.
- Migração `n4o5p6q7r8s9` aplicada pelo deploy. Antes, a criação das quatro tabelas e suas referências foi validada em esquema temporário do PostgreSQL, revertido integralmente após o teste.
- `/health` respondeu HTTP 200 com API, banco e worker `online`. O Render foi configurado para monitorar esse endpoint.
- Webhook Telegram registrado no backend público com segredo. Mensagens sem o segredo retornam HTTP 403. O webhook WhatsApp retorna HTTP 503 porque o canal está em standby.
- O proprietário do grupo Telegram foi vinculado ao usuário administrador existente, com permissão de consulta. Outros funcionários precisam ser vinculados no painel.
- Uma consulta real enviada pelo Telegram foi recebida pelo webhook, processada no servidor e respondida no grupo. A fila registrou `done` e `accepted`, e o código da resposta foi comparado ao cadastrado no ERP. Nenhum pedido foi alterado; nenhuma mensagem WhatsApp foi processada.
- 28 testes automatizados passaram e o frontend compilou.

Uso no piloto: envie `/rastreio Nome do cliente` em uma única mensagem, `/rastreio NUMERO-DO-PEDIDO`, ou mencione `@ElevenParis11_Bot` na pergunta. Em caso de vários bots no grupo, use `/rastreio@ElevenParis11_Bot Nome`. A privacidade do Telegram permanece ativa; ainda não há leitura geral da conversa. O bot funciona no servidor independentemente do computador local, onde a ativação continua desabilitada.

Os registros abaixo descrevem a etapa anterior à publicação.

## Resultado

| Componente | Verificação | Resultado |
| --- | --- | --- |
| DeepSeek | Autenticação e listagem de modelos | HTTP 200; modelo configurado `deepseek-flash` |
| Consulta pela IA | Pergunta por João Exemplo em banco temporário | A IA chamou `buscar_rastreios` e devolveu `TESTE-SEM-POSTAGEM`, o código fictício cadastrado |
| Memória entre canais | Rascunho criado no fluxo WhatsApp e confirmado no fluxo Telegram pelo mesmo usuário fictício | Registro compartilhado; a IA usou `buscar_memoria` e encontrou a ocorrência |
| Telegram | Comando real no grupo → recepção pela Bot API → autorização no banco temporário → DeepSeek → envio ao grupo | Resposta aceita pelo Telegram, identificada como teste com dados fictícios |
| ERP real | Conexão PostgreSQL com `SET TRANSACTION READ ONLY` | Conexão bem-sucedida; `transaction_read_only=on` confirmado |
| Rastreio real | DeepSeek → `buscar_rastreios` → pedido existente → resposta ao Telegram | Código retornado conferido contra o banco; mensagem visível no grupo como teste somente leitura |
| Twilio | Recepção do comando de adesão e de “Olá Eleven” | Ambas encontradas na API de mensagens; resposta automática padrão da Twilio observada |
| Twilio | Envio de resposta livre pelo adaptador do ERP | Recusado com `21654 / ContentSid Required`, inclusive após a nova mensagem recebida |

Os testes de consulta e memória fizeram quatro chamadas reais à DeepSeek. O teste Telegram fez a consulta adicional com a mesma implementação do agente e um banco isolado em memória. A memória entre canais foi validada no backend; não foi possível comprovar esse fluxo completo pelo transporte WhatsApp, devido à restrição abaixo.

Depois que a conexão do banco foi fornecida, uma consulta adicional usou as funções reais de busca e conclusão da DeepSeek contra o PostgreSQL existente, em transação somente leitura encerrada com rollback. Somente o pedido selecionado foi fornecido à IA; o código da resposta foi comparado ao cadastrado antes de enviá-la ao Telegram. Essa consulta pontual não passou pelo worker nem por um webhook de produção, pois as tabelas do assistente ainda não foram migradas.

## Diagnóstico da Twilio

A conta foi identificada como Trial e a mensagem automática recebida menciona o Tryout. A documentação atual do **Try out WhatsApp** exige `ContentSid` de um modelo fornecido pela Twilio para envio via API. Ela não permite personalizar livremente a mensagem. Isso explica a rejeição do parâmetro `Body` utilizado pelo chatbot. O código enviado pelo adaptador contém somente `From`, `To` e `Body`; não inclui `ContentVariables`.

Fonte: [Twilio — Try out WhatsApp, parâmetros permitidos na API](https://www.twilio.com/docs/usage/trials/try-out-whatsapp#send-a-whatsapp-message). A documentação distingue esse trial do [Sandbox do console legado](https://www.twilio.com/docs/whatsapp/sandbox).

Para testar respostas dinâmicas no WhatsApp, é necessário disponibilizar uma conta/remetente que aceite texto livre na janela de atendimento. O upgrade financeiro da conta e a aprovação do remetente não foram realizados nesta verificação.

## Estado de ativação

- Bot `@ElevenParis11_Bot` e grupo **Eleven | Operações** configurados; comandos e descrição cadastrados.
- Telegram com privacidade de grupo ainda ativa: teste por comando direcionado ao bot, sem leitura geral da conversa.
- Credenciais locais presentes em `backend/.env`, ignorado pelo Git e com permissão de arquivo restrita. Nenhum segredo consta neste relatório.
- `ASSISTANT_ENABLED=false`; não há worker contínuo ou webhook Telegram configurado.
- `DATABASE_URL` salva pelo usuário e validada. Foi executada uma consulta de rastreio em transação somente leitura; nenhuma migração ou escrita foi executada no banco de produção.
- Ainda faltam implantação da API/worker, migração no ambiente de destino, vínculo dos usuários reais e configuração dos webhooks.

As mensagens iniciais são demonstrações com dados fictícios. A mensagem posterior identificada como **TESTE SOMENTE LEITURA — DADOS REAIS DO ERP** contém o resultado da consulta real. Ambas informam que o atendimento contínuo ainda não está ativo.

## Ampliação do coordenador — 21/09/2026

- Consultas sem termo obrigatório: últimos envios, períodos relativos no fuso America/Sao_Paulo, status, contagens e paginação (até 20 registros por página).
- Busca individual prioriza um único envio em aberto do cliente; histórico entregue não gera pergunta desnecessária. Homônimos distintos continuam exigindo identificação. Pedido e rastreio com o mesmo código são contados uma vez, e o status do rastreamento prevalece na consulta de entrega.
- Rastreio individual: mensagem apenas com o código, seguida de cliente/status/data/última consulta salva. A segunda mensagem depende da aceitação da primeira pelo provedor. Sem atualização online aos Correios durante a conversa.
- Consultas adicionais: pedidos, clientes, estoque por produto/SKU/categoria/tamanho/cor e local, vendas tradicionais/PDV e calendário de folgas. Vendas exigem ADMIN/GERENTE; módulos e moedas ficam separados.
- Folgas: ADMIN/GERENTE com `can_register=true` pode pedir um cadastro; uma prévia é armazenada em `assistant_actions`. `confirmo` (única prévia pendente) ou `/confirmar ID` executa na mesma conversa, pelo mesmo autor, em até 24h. A nova folga fica pendente de aprovação, como no cadastro padrão. Sem alteração/exclusão/aprovação automática. Cancelamento de prévia: `/cancelar ID`.
- A página `/assistente` mostra a auditoria das solicitações de folgas. Motivos pessoais não aparecem nas consultas do calendário do grupo.
- Migração `o5p6q7r8s9t0` cria a auditoria de ações e acrescenta a dependência entre mensagens de saída.
- No primeiro deploy da ampliação, a privacidade de grupo ainda exigia menção/resposta/comando. A ativação posterior de mensagens normais está registrada abaixo.
- WhatsApp permanece em standby; usa o mesmo agente quando o canal for habilitado.

Validação antes da publicação:

- Regressões automatizadas cobrem períodos/dias no fuso local, contagens e paginação, histórico versus envio aberto, homônimos fora da primeira página, deduplicação/status, filtros de estoque, Decimal/moedas/PDV cancelado, permissões/expiração/duplicidade/rollback de folgas e ordem das mensagens.
- Consultas SQL executadas contra PostgreSQL real em transação somente leitura: envios recentes, ontem, em aberto, cliente Vandilson, estoque, pedidos, clientes, vendas e folgas.
- Migração validada com upgrade/downgrade/upgrade em schema isolado e rollback completo; nenhum cadastro de teste deixado em produção.
- Oito cenários com DeepSeek real e banco isolado: últimos 5 envios, ontem, pendências, rastreio individual, camiseta M na loja, folgas de amanhã, cadastro completo e pedido de folga sem data. Todos escolheram as ferramentas/filtros corretos; o pedido sem data solicitou a informação faltante.
- 44 testes automatizados passaram; build do frontend concluído. Migração testada no PostgreSQL.
- Dois diálogos adicionais com DeepSeek real passaram: consulta de últimos envios seguida de “e ontem?”; pedido de folga sem data, complementação da data e “confirmo”. O cadastro de folga ocorreu apenas no banco isolado do teste.

### Conversa sem comandos

A pedido do usuário, o recebimento do Telegram passou a tratar mensagens comuns dos funcionários autorizados como solicitações ao coordenador, incluindo continuações (“e ontem?”), “confirmo” e “cancela”. Os comandos existentes continuam compatíveis, mas não são necessários. Confirmações em linguagem natural também atendem aos rascunhos de ocorrências, mantendo autoria, conversa e validade de 24 horas.

O recebimento sem comandos/menções usa Group Privacy desativado no BotFather e a readição do bot ao grupo existente, conforme https://core.telegram.org/bots/features#privacy-mode. O ERP continua aceitando apenas o grupo configurado e funcionários autorizados. A conclusão da ativação e os testes estão registrados abaixo.

O resumo de estoque agora devolve explicitamente os totais de loja e depósito para todos os produtos filtrados, evitando que a IA use apenas os itens da página ou peça um produto desnecessariamente. Validação: 46 testes automatizados passaram.

Primeiro deploy da ampliação: commit `c222f13`, Render `dep-daos47e8bjmc73aho0vg`, migração `o5p6q7r8s9t0`, backend/worker/banco online. Testes reais no grupo confirmaram últimos 5 envios e rastreio do Vandilson em duas mensagens (IDs 36 e 37 aceitos, na ordem). Cadastro real de folga foi testado em banco isolado, sem criar folgas fictícias na operação. Permissão de registro ativada apenas para o administrador Telegram já verificado.

Ativação sem comandos concluída em 21/09/2026 após autorização explícita: BotFather confirmou `DISABLED`; `getMe` retornou `can_read_all_group_messages=true`. O bot foi removido e readicionado ao grupo como membro comum, sem compartilhar as últimas 100 mensagens. A pergunta normal “Quantas unidades temos na loja e no depósito?” chegou ao webhook, terminou como `done` e recebeu resposta no grupo (envio 43 aceito), com os totais corretos. Nenhum privilégio de administrador do Telegram foi necessário.

O teste repetido de rastreio revelou que a IA podia copiar uma resposta antiga em texto único e ignorar a ferramenta de formatação. A correção verifica códigos contra consultas feitas na solicitação atual, força nova busca quando necessário e aplica a resposta em duas mensagens no servidor. Listagens continuam em formato normal. Validação: 52 testes passaram; teste com DeepSeek real e PostgreSQL somente leitura forçou a recuperação após resposta antiga e retornou código mais status atual em duas partes. Nenhum pedido foi alterado.

A aplicação aceita mensagens normais apenas do grupo configurado e de identidades autorizadas; eventos de entrada/saída de membros são ignorados. Textos de ajuda e confirmação passaram a orientar “confirmo”/“cancela”, mantendo comandos antigos opcionais. Resumo por local conferido diretamente: loja 248 unidades, depósito 480, total 728 (fotografia do teste de 21/09/2026, não dado permanente).
