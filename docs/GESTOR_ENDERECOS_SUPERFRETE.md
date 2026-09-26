# Gestor de endereços e SuperFrete

Acesso: Dashboard → **Endereços e envios** (`/enderecos`), para ADMIN e GERENTE.

- **Endereços:** cadastros Brasil/Paraguai, com vínculo opcional a clientes de pedidos ou PDV, sem sobrescrever o cadastro original do cliente.
- **Impressões:** histórico do bot e do ERP, PDF, edição como nova cópia e cancelamento de trabalhos ainda não retirados pelo agente.
- **Remetentes:** endereço compartilhado entre impressão e frete. Blocos antigos são lidos automaticamente quando os campos são reconhecíveis. Confira os campos recuperados e complete apenas os ausentes; o bot também aceita complementos na conversa.
- **Padrões:** fonte, margens, título, campos e ordem dos modelos A4. Alterações afetam apenas novas solicitações; o histórico preserva os dados originais.
- **SuperFrete:** cotação, confirmação do pagamento, PDF recuperado automaticamente e impressão automática opcional no frontend (ativada no bot). Rastreios recebidos são registrados no ERP durante a consulta da etiqueta.

A edição é de dados e padrões dos PDFs gerados pelo ERP, não de Word ou PDFs externos. Arquivos avulsos antigos podem deixar de estar disponíveis após a limpeza da fila. PDFs SuperFrete são validados e guardados no banco assim que o provedor os disponibiliza.

## Frontend

1. Cadastre endereço brasileiro completo e remetente com dados estruturados.
2. No endereço, clique em **Frete**. Informe peso em kg, medidas em cm e conteúdo real. Informe a chave da nota fiscal ou selecione declaração de conteúdo quando o envio for não comercial.
3. Faça a cotação e selecione um dos serviços disponíveis: PAC, SEDEX ou Mini Envios.
4. Confira o preço final e clique em **Confirmar pagamento e emitir**. Essa etapa consome saldo SuperFrete.
5. A opção **Imprimir automaticamente quando o PDF estiver pronto** vem marcada. Desmarque antes do pagamento se quiser imprimir manualmente. O PDF aparece na tela automaticamente e pode ser baixado.

A impressão simples continua aceitando CPF ausente e dados parciais do Paraguai. A emissão de frete tem validações próprias da transportadora, incluindo CPF/CNPJ do destinatário.

## Bot

Exemplo: “Quero cotar uma etiqueta para este endereço: [dados]. Remetente [nome], pacote [peso e medidas], conteúdo [descrição, quantidade e valor], [nota fiscal ou envio não comercial].”

O bot aceita destinatário e remetente informados na conversa, sem exigir cadastro prévio do remetente. Pode também extrair os dados do bloco de impressão dos remetentes existentes; pede somente campos faltantes. Os dados ficam preservados na cotação sem sobrescrever o cadastro-base. Descrição, quantidade e valor unitário dos itens são usados na declaração informada pelo usuário. O bot apresenta serviços/valores. Após a escolha do serviço, pede confirmação do pagamento. Depois da confirmação do pagamento, busca o PDF, envia ao Telegram e coloca uma única cópia A4 na fila automaticamente. Não exige comandos com barra.

Confirmações pertencem ao usuário autorizado e à conversa de origem. Cotar não paga. Cancelar a impressão de uma etiqueta paga não cancela nem reembolsa a compra.

## Configuração

```dotenv
SUPERFRETE_TOKEN=seu_token
SUPERFRETE_CONTACT_EMAIL=contato_tecnico
SUPERFRETE_SANDBOX=false
```

Tokens de produção e Sandbox são diferentes. O padrão é Sandbox. No Render, o backend também carrega `/etc/secrets/superfrete.env`, preservando variáveis já definidas no ambiente. Nunca versionar tokens.

Migrações: `r8s9t0u1v2w3` e `s9t0u1v2w3x4`. Cria cadastros, padrões e fretes; adiciona anexos à entrega do bot e recupera conteúdo de impressões antigas vinculadas a ações do assistente.

## Operação

O agente Windows existente e o Sumatra continuam sendo usados. A máquina da loja precisa estar ligada com o agente aberto. “Enviado à impressora” indica aceitação pelo agente/Sumatra, não confirmação física do papel.

Impressões usam chaves de idempotência. Pagamentos são marcados antes da chamada externa. Uma resposta incerta bloqueia novo pagamento automático e permite consultar o estado. Se não houver identificador de frete, confira o painel SuperFrete antes de criar nova emissão.

Documentação oficial: https://superfrete.readme.io/reference/primeiros-passos

O histórico consultável pelo bot inclui endereços impressos. Pedidos de frete consultam novamente os cadastros antes de responder; recusas antigas sobre remetentes não configurados não são reaproveitadas. Mensagens do usuário cujo processamento falhou permanecem disponíveis no contexto, para não perder complementos de endereço.

## Botões, nomes e memória

Prévias do Telegram têm botões de confirmação/cancelamento. Havendo várias, o bot mostra uma lista paginada pelo nome e dados da solicitação. `confirmar impressão "Juan"` executa apenas se houver uma prévia inequívoca desse autor nessa conversa; homônimos abrem opções. Botões antigos continuam sujeitos a validade de 24 horas, permissões e execução única.

`consultar_equipe` lê os vendedores ativos e resolve nomes sem diferenciar acentos. `Lembre que Juninho é o Junior` prepara um apelido; confirmar salva em `assistant_knowledge`. O catálogo de ferramentas também é persistido e sincronizado a cada versão. Saldos, rastreios e agenda são consultados de novo; a memória não congela fatos operacionais.

## Recuperação automática dos PDFs

O worker de etiquetas roda em uma thread separada, inclusive quando o assistente está pausado. Consulta a SuperFrete com intervalo progressivo até cinco minutos, persiste o PDF validado e usa uma chave única por frete para a impressão automática. Não repete pagamento. Depois de 400 tentativas sem conclusão, sinaliza falha; **Consultar** no gestor reinicia a recuperação. Problemas temporários da impressora não impedem salvar/enviar o PDF.

Para ativar notificações, execute **no servidor**, após o deploy:

```sh
python -m app.assistant_setup telegram-webhook --url https://SEU-BACKEND/api/assistant/webhooks/telegram
python -m app.superfrete_setup --url https://SEU-BACKEND/api/freight/webhooks/superfrete
```

Telegram precisa de `allowed_updates` com `message` e `callback_query`. A SuperFrete usa `order.generated`; o webhook valida HMAC-SHA256 sobre o corpo original, agenda uma consulta autenticada e nunca paga nem confia em URLs do evento. A assinatura fica cifrada em `freight_webhooks` com a chave do servidor; opcionalmente pode ser fornecida por `SUPERFRETE_WEBHOOK_SECRET`. A consulta periódica continua mesmo sem webhook.

Etiquetas antigas pagas são recuperadas sem imprimir de novo. Para as antigas cujo PDF faltava, o canal original recebe o documento ao ficar pronto. Mantenha o agente Windows da loja aberto; não é necessário reinstalá-lo.

Referências: [botões Telegram](https://core.telegram.org/bots/api#inlinekeyboardmarkup), [eventos e assinatura SuperFrete](https://superfrete.readme.io/reference/webhook).

## Endereço único e histórico de utilização

A agenda mantém um cadastro por destinatário e local de entrega. Acentos, maiúsculas, espaços, pontuação e a máscara do CEP são normalizados para reconhecer repetições. Apartamentos numerados também aceitam as formas “Apartamento”, “apto”, “apt” e “ap” como equivalentes. Nome, número, complemento, cidade ou outro local diferente continuam sendo cadastros distintos. Em endereços mínimos do Paraguai, o telefone ajuda na identificação. Blocos vazios ou somente com nome não são consolidados automaticamente.

O bot, o cadastro manual e as impressões usam a mesma rotina de reutilização. Solicitações concorrentes são serializadas e um índice único protege o cadastro. Diferenças de CPF/CNPJ ou vínculos com clientes distintos exigem conferência, para não misturar pessoas.

No cartão de cada endereço, **Histórico** mostra cotações, etiquetas e impressões, com data, responsável, estado, rastreio e dados do endereço usado na ocasião. Permite filtrar por tipo, paginar, abrir o frete e consultar o PDF da impressão. Uma cotação não comprova um pacote enviado. Repetir uma mesma requisição técnica não cria outra utilização; solicitar outro pacote cria outro frete, reutilizando o endereço.

As migrações `t0u1v2w3x4y5` e `u1v2w3x4y5z6` consolidam duplicatas já existentes, incluindo abreviações de apartamentos. Os IDs antigos ficam preservados como referências ao cadastro principal; fretes, impressões e snapshots não são excluídos nem reescritos. Históricos de cópias antigas aparecem no endereço consolidado. Referências antigas continuam resolvendo para o endereço principal; editores abertos antes da consolidação precisam atualizar a agenda.

### Impressões de endereços A4 no histórico

Os modelos simples enviados pelo bot ou pelo ERP aparecem no mesmo **Histórico** das etiquetas. O resumo mostra endereços A4 impressos, etiquetas emitidas e total enviado à impressora. A contagem de impressão usa somente trabalhos `submitted`; fila, cancelamento, expiração, falha ou resultado incerto permanecem na lista, mas não aumentam o total. A data de conclusão do agente aparece em destaque, com a data da solicitação abaixo. Isso registra o envio à impressora, não um sensor de saída do papel.

A migração `w3x4y5z6a7b8` recupera impressões antigas com endereço no snapshot que estavam sem vínculo com a agenda. Reutiliza o endereço existente ou cria um único cadastro a partir dos dados originais, preservando datas, responsável, resultado e documento histórico. Não cria trabalhos nem reimprime. Blocos brasileiros sem bairro podem usar um cadastro mais completo quando nome, cidade, UF, CEP e rua/número/complemento identificam um único endereço. Conflitos de documento ou candidatos ambíguos não são associados automaticamente. PDFs avulsos da ponte temporária continuam fora da agenda.
