# Verificação de integração — 20/09/2026

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
