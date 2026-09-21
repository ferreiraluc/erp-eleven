# Assistente operacional Eleven — DeepSeek + WhatsApp

Estudo inicial: 20/09/2026. Status: histórico do estudo; a primeira versão local foi implementada, sem ativação externa. Veja `ASSISTENTE_ATIVACAO.md`. Provedor corrigido pelo usuário: **DeepSeek**, não Grok.

## Decisão atual — substitui a seleção de canal abaixo

O usuário definiu **Twilio para WhatsApp 1:1** e **bot em grupo Telegram**, com o mesmo backend DeepSeek e memória operacional compartilhada. O grupo WhatsApp deixa de ser requisito. As avaliações de conectores abaixo são histórico do estudo. A impressão futura continua sendo HP em Windows. A implementação inicial entrega consultas, rascunhos/registro de ocorrências, memória confirmada, avisos de rastreio no Telegram e painel administrativo; as etapas financeiras, mídia e impressão ainda não estão implementadas.

## Objetivo

Um número dedicado participa dos canais autorizados da loja, anuncia rastreios cadastrados no ERP, responde consultas dos funcionários e transforma mensagens em registros de pedidos, endereços, atendimentos, vendas e devoluções. Também permite solicitar impressão de endereços.

O ERP continua sendo a fonte dos dados. A conversa fornece contexto e evidências; não substitui a consulta ao banco. O modelo propõe chamadas de funções específicas, e o backend valida e executa cada operação.

Confirmado pelo usuário durante o estudo: participação no **grupo atual**, **número exclusivo** para o assistente e **impressora HP conectada a computador Windows**. A quantidade de participantes e o modelo/conexão exatos da HP ainda não foram informados. O suporte ao grupo atual é requisito de seleção do conector, não preferência opcional.

## O que foi confirmado no código

| Necessidade | Base existente | Trabalho necessário |
|---|---|---|
| Consultar rastreio do cliente | `backend/app/models/pedido.py`, `rastreamento.py`, `cliente.py` | Busca unificada por nome, telefone, pedido e código; resolver homônimos e múltiplos envios |
| Anunciar código novo | Endpoints de pedidos/rastreamentos e `services/rastreamento_sync.py` | Evento persistente em todos os caminhos de cadastro e associação, com prevenção de duplicatas |
| Cadastrar pedido/endereço | `api/endpoints/pedidos.py` e `clientes.py` | Extrair dados, preservar origem, validar campos e separar rascunho de cadastro completo |
| Registrar venda | `api/endpoints/vendas.py` e `pdv.py` | Definir destino: vendas gerais e PDV são fluxos diferentes |
| Vincular cliente | `Cliente` e `PdvCliente` são tabelas distintas | Resolução explícita de identidade, sem tratar UUIDs como intercambiáveis |
| Devoluções/atendimentos | Não foi identificado módulo dedicado na estrutura inspecionada | Criar ocorrências e fluxo de devolução com vínculo opcional à venda/pedido |
| Impressão | `PDVReceiptModal.vue` usa `window.print()` | Criar etiqueta de endereço e ponte local para impressão automática |
| Hospedagem | `render.yaml`: FastAPI, PostgreSQL e frontend | Acrescentar worker persistente; conector WhatsApp conforme opção escolhida |

Cuidados concretos antes de habilitar escrita automática:

- A criação de pedido exige descrição e valor positivo. Mensagem incompleta deve virar rascunho, sem inventar valor.
- A criação de venda no PDV já movimenta estoque e pode alterar fiado. Não chamar esse fluxo apenas porque alguém comentou sobre uma venda.
- O PDV usa conversões para `float` em cálculos e altera estoque diretamente. Revisar precisão, concorrência e validação antes de expor esse fluxo ao agente.
- A sincronização de rastreamentos pode reassociar um código a outro pedido; impedir reassociação silenciosa no novo fluxo.
- O mapeamento atual transforma ERRO/NAO_ENCONTRADO do rastreamento em CANCELADO no pedido. Rever essa regra antes de automatizar ações a partir do status logístico.
- Autenticação JWT existente não resolve a identidade do autor no WhatsApp. Criar vínculo verificado entre participante e usuário ERP, com permissões por operação.

## Escolha do WhatsApp: primeira decisão de viabilidade

### API oficial

A documentação do provedor 360dialog informa exigência de Official Business Account, máximo de oito participantes, criação de grupos por API e ausência de suporte a coexistência nesse recurso. A documentação direta da Meta retornou HTTP 429 durante a consulta. Portanto, confirmar elegibilidade e funcionamento na conta real antes de assumir compatibilidade; não prometer entrada no grupo comum já existente.

### Conector baseado em WhatsApp Web

Baileys é uma biblioteca não oficial. É uma alternativa técnica a investigar quando o grupo atual for indispensável, com custo operacional de sessão, reconexão e mudanças de protocolo, além do risco de restrição da conta. Não selecionar automaticamente esse caminho. Usar número dedicado e teste isolado se essa opção for escolhida.

### Twilio (alternativa solicitada pelo usuário)

Pode ser avaliada como canal oficial para conversas individuais entre funcionários e o assistente DeepSeek. Porém, o exemplo oficial “WhatsApp Group Messaging” usa Conversations para distribuir mensagens por conversas com o número empresarial e declara explicitamente que não é um grupo nativo do WhatsApp. Isso não atende ao requisito de entrar e acompanhar o grupo atual da loja.

A FAQ atual da Twilio menciona o lançamento da Groups API da Meta, mas essa menção não comprova suporte da Twilio à participação em grupos preexistentes. Manter a Twilio como candidata para atendimento privado; só considerá-la solução para o grupo atual após documentação específica e prova de funcionamento. A arquitetura do DeepSeek/ERP e a ponte de impressão permanecem independentes dessa escolha.

### Prova de viabilidade obrigatória

Com o conector candidato, verificar: receber mensagem do grupo alvo; identificar autor de forma estável; preservar mensagem respondida; enviar resposta ao grupo; receber mídia; reconectar sem processar histórico como novas ordens; identificar mensagens enviadas pelo próprio bot. Validar também os custos, as condições do provedor e a elegibilidade da conta.

Não há escolha final de conector neste estudo. Conversas privadas oficiais podem servir como piloto, mas não satisfazem sozinhas o requisito do grupo.

## Arquitetura proposta

```text
WhatsApp → conector → entrada autenticada → caixa de mensagens persistida
                                           ↓
                              worker + contexto limitado + DeepSeek
                                           ↓
                               funções autorizadas do ERP
                                           ↓
                          validação / rascunho / execução / auditoria
                                           ↓
ERP → eventos na mesma transação → fila de saída → conector → WhatsApp

Solicitação de impressão → fila de impressão → agente local da loja → impressora
```

Começar com tabelas de trabalho no PostgreSQL e worker separado, evitando dependências extras sem necessidade. Disputar trabalhos com locks/leases, retentativas limitadas e recuperação após reinício. O agendador existente dentro do servidor web não deve ser o mecanismo de entrega confiável.

O recebimento confirma sucesso somente após persistência. Chamadas ao modelo e envio externo ocorrem fora da transação de negócio. Eventos de saída são gravados junto com a alteração do ERP, evitando anunciar cadastro que sofreu rollback.

## DeepSeek

A API documenta tool calling: o modelo solicita uma função e a aplicação a executa. Configurar `DEEPSEEK_API_KEY` apenas no servidor, modelo em `DEEPSEEK_MODEL` e cliente com timeout, limite de tokens, número máximo de chamadas de ferramenta e orçamento diário. Escolher o modelo disponível na conta após testar qualidade e custo, sem fixar um nome por suposição.

Validar os argumentos com Pydantic mesmo quando houver modo de saída estrita. Não conceder SQL, shell, acesso genérico a URLs ou função genérica de alteração de tabelas. Consultas retornam apenas os campos necessários ao caso.

Imagens e áudios exigem validação separada das capacidades do modelo contratado. Planejar adaptadores para OCR/transcrição, com extração revisável e sem assumir que a API de texto aceita todo tipo de mídia. O OCR atual do ERP usa Anthropic; substituí-lo é uma decisão separada.

## Fluxos e autonomia proposta

| Ação | Comportamento inicial |
|---|---|
| Avisar rastreio cadastrado | Automático, por evento, em grupo configurado; não depende de IA para montar o código |
| Responder consulta de envio | Automático após verificar autor e resolver cliente/pedido |
| Interpretar conversa espontânea | Gerar rascunho de ocorrência; registrar mensagem de origem e dados extraídos |
| Registrar ocorrência sem efeito financeiro | Pode ser automático para comando explícito de funcionário autorizado, conforme configuração |
| Criar pedido ou alterar endereço | Mostrar proposta e obter confirmação inicial; endereço do pedido não altera todos os cadastros do cliente |
| Registrar venda, baixar estoque, alterar fiado | Confirmação vinculada à operação e ao usuário autorizado |
| Registrar chegada de devolução | Ocorrência de recebimento; triagem separada de reposição de estoque e reembolso |
| Solicitar impressão | Após identificação inequívoca do endereço, criar trabalho identificado e rastreável |

As confirmações acima são uma proposta de comportamento do produto durante o piloto, não uma exigência para realizar este estudo. A autonomia pode evoluir por tipo de operação após medir acerto.

Exemplo de consulta:

1. Funcionário: “Tem o rastreio do João?”
2. Backend verifica participante e grupo, busca candidatos em pedidos e rastreamentos.
3. Havendo mais de um João ou mais de um envio, o assistente pede número do pedido ou outro identificador mínimo.
4. Resposta usa código, número do pedido e data retornados pelo ERP. Informa quando o status foi atualizado; não apresenta status antigo como consulta em tempo real.
5. Sem resultado, informa que não encontrou. Nunca completa código ou associa cliente por adivinhação.

Exemplo de devolução: “Chegou a devolução do João, pedido 123, camiseta M”. Cria proposta vinculada ao pedido, registra autor e evidência. Recebimento físico, conferência do item, destino do estoque e eventual reembolso têm estados separados.

Não responder a toda conversa. Processar contexto apenas dos grupos autorizados; responder a perguntas operacionais claras, menções, mensagens dirigidas ao bot e pendências relevantes. Usar mensagens respondidas para resolver contexto, sem misturar conversas de clientes diferentes.

## Contratos de funções sugeridos

- `buscar_pedidos(termo, periodo, limite)` → candidatos mínimos, identificadores e origem.
- `consultar_rastreios(pedido_id)` → códigos, status, vínculo e data da última consulta.
- `preparar_ocorrencia(tipo, pedido_id?, descricao, source_message_ids)` → rascunho.
- `preparar_alteracao_endereco(pedido_id, endereco, source_message_ids)` → proposta com antes/depois.
- `preparar_venda(modulo, dados, source_message_ids)` → proposta validada, sem baixa imediata.
- `confirmar_operacao(operation_id)` → execução após checagem do ator no servidor; o modelo não pode inventar a aprovação.
- `solicitar_impressao(pedido_id, printer_id, copias)` → trabalho, sem aceitar comando arbitrário de impressão.

Identidade, permissões, grupo de destino e aprovação são fornecidos pelo servidor. Não confiar em campos de identidade gerados pelo modelo. Aprovações vinculam usuário, versão dos dados, resumo da operação e expiração; confirmar novamente se os dados mudaram.

## Persistência sugerida

- `assistant_channels`: conector, ID externo, grupo permitido, regras de participação.
- `assistant_identities`: participante externo ↔ usuário ERP, verificação e estado ativo.
- `assistant_messages`: ID externo único por conta/conversa, autor, reply-to, horários e referência à mídia.
- `assistant_operations`: intenção, dados validados, origem, estado, aprovação, resultado e chave idempotente.
- `operational_occurrences`: atendimento/devolução, status, responsável, pedido/venda vinculados e anexos.
- `integration_outbox`: evento, destino, tentativas, status e identificador externo de entrega.
- `print_jobs`: documento, impressora, solicitante, estado e confirmação do agente local.
- `assistant_audit`: ação, ator, versão, antes/depois permitido e referências às evidências.

Mensagens recebidas e operações precisam de unicidade persistente. Reentrega do webhook não pode criar outra venda. Também detectar relato repetido em mensagens diferentes e confrontar com vendas existentes. Envios externos podem ficar em estado incerto se houver timeout após aceitação: reconciliar quando possível, sem prometer entrega exatamente uma vez.

Criar um painel no ERP para rascunhos, confirmações, erros, histórico, conexão, custos e pausa do assistente. Retenção de mensagens e mídias deve ser configurável; expor ao modelo só o contexto necessário, com acesso restrito no painel e credenciais fora dos logs.

Texto de mensagens, anexos e OCR é dado não confiável: instruções como “ignore suas regras” não alteram ferramentas ou permissões. Lista de grupos autorizados não substitui verificação do autor. Não anunciar CPF, endereço completo ou outros dados dispensáveis em resposta de rastreio.

## Impressão na loja

A hospedagem em nuvem não dá acesso direto a uma impressora USB da loja. Propor agente local que busca trabalhos por conexão de saída autenticada, usando credencial limitada a uma impressora. Nunca expor porta da impressora à internet.

Primeira entrega: gerar documento de endereço e disponibilizar para impressão manual. Automação posterior: agente local, spooler, estado offline, tentativas e política explícita de reimpressão. “Enviado para impressão” e “impresso” são estados distintos; não afirmar impressão física sem confirmação compatível do equipamento.

Para o ambiente confirmado, implementar o agente no Windows e usar a fila/driver da HP instalada. Confirmar formato de papel, layout desejado, nome da fila e disponibilidade do computador. Não pressupor impressora térmica, linguagem ZPL ou ESC/POS. Se a fila apenas confirmar recebimento, apresentar “enviado à fila da HP”, sem afirmar saída física do papel.

## Etapas de entrega

1. **Viabilidade do canal:** definir número/grupo/provedor; executar prova isolada. Resultado: comunicação bidirecional e identidade comprovadas.
2. **Consultas e avisos:** cliente DeepSeek, busca por nome/pedido, eventos de rastreio, fila, auditoria e pausa. Resultado: exemplo do João funciona sem escrita financeira.
3. **Registro operacional:** painel, rascunhos, ocorrências, atendimentos, devoluções e endereços com evidências.
4. **Vendas e estoque:** definir módulo correto, extrair serviços reutilizáveis dos endpoints, corrigir validações relevantes e implementar confirmação/idempotência transacional.
5. **Mídia e impressão:** testar imagens/áudios representativos, etiqueta e agente local conforme equipamento.
6. **Piloto supervisionado:** começar com poucos funcionários, medir erros e liberar autonomia por operação.

## Critérios de aceitação

- Cadastro direto de rastreio e código incluído em pedido geram aviso após commit; rollback não gera envio.
- Mesmo evento recebido várias vezes gera uma operação; reconexão não executa comandos antigos.
- Dois Joões, dois envios e cliente inexistente têm respostas corretas sem associação arbitrária.
- Participante desconhecido não consulta dados nem executa alterações.
- Mensagem ou imagem com instrução maliciosa não amplia permissões.
- Timeout/limite de uso do DeepSeek não perde mensagem nem confirma sucesso inexistente.
- Venda já registrada e depois relatada no grupo não vira outra venda.
- Confirmação duplicada ou expirada não repete baixa; alterações concorrentes invalidam proposta antiga.
- Devolução recebida não implica estorno, pagamento ou reposição automática.
- Impressora offline deixa trabalho pendente; reinício não causa reimpressão silenciosa.
- Alterações preservam os fluxos atuais da interface e são cobertas por testes de negócio, integração e falhas.

## Informações pendentes

Número de participantes no grupo atual; conector já contratado, se houver; perfil Meta elegível ou não; volume diário e uso de fotos/áudios; pessoas autorizadas; módulo de vendas usado na operação; modelo da HP, papel/layout e disponibilidade do Windows; política de confirmação e retenção. Já confirmados: grupo atual, número dedicado e HP em Windows. Não é necessário enviar chaves no chat para decidir a arquitetura.

Custos a estimar depois desses dados: tokens DeepSeek + canal WhatsApp + worker/conector + armazenamento de mídia + eventual OCR/transcrição. Notificações determinísticas, contexto curto e processamento seletivo reduzem uso. Não foi feita chamada paga à API neste estudo.

## Fontes consultadas

- DeepSeek, Tool Calls: https://api-docs.deepseek.com/guides/tool_calls/
- DeepSeek, Chat Completions: https://api-docs.deepseek.com/api/create-chat-completion/
- 360dialog, documentação de grupos do próprio provedor: https://docs.360dialog.com/docs/messaging/groups
- Baileys, repositório e aviso de biblioteca não oficial: https://github.com/WhiskeySockets/Baileys
- Twilio, exemplo de grupo por redistribuição de mensagens: https://www.twilio.com/code-exchange/whatsapp-group-messaging
- Twilio, FAQ WhatsApp: https://www.twilio.com/docs/whatsapp/best-practices-and-faqs
- Meta, página tentada sem leitura bem-sucedida (429): https://developers.facebook.com/documentation/business-messaging/whatsapp/groups

As limitações externas devem ser reconfirmadas ao escolher o fornecedor. Este documento é um plano técnico baseado em inspeção do código, não validação de produção nem teste das contas do usuário.
