# Gestor de endereços e SuperFrete

Acesso: Dashboard → **Endereços e envios** (`/enderecos`), para ADMIN e GERENTE.

- **Endereços:** cadastros Brasil/Paraguai, com vínculo opcional a clientes de pedidos ou PDV, sem sobrescrever o cadastro original do cliente.
- **Impressões:** histórico do bot e do ERP, PDF, edição como nova cópia e cancelamento de trabalhos ainda não retirados pelo agente.
- **Remetentes:** bloco de texto para impressão simples e campos estruturados para frete. Complete os campos estruturados antes da primeira cotação. Remetentes antigos continuam funcionando na impressão simples.
- **Padrões:** fonte, margens, título, campos e ordem dos modelos A4. Alterações afetam apenas novas solicitações; o histórico preserva os dados originais.
- **SuperFrete:** cotação, confirmação do pagamento, PDF e confirmação separada da impressão. Rastreios recebidos são registrados no ERP durante a consulta da etiqueta.

A edição é de dados e padrões dos PDFs gerados pelo ERP, não de Word ou PDFs externos. Arquivos avulsos antigos podem deixar de estar disponíveis após a limpeza da fila. PDFs SuperFrete também dependem da disponibilidade do provedor.

## Frontend

1. Cadastre endereço brasileiro completo e remetente com dados estruturados.
2. No endereço, clique em **Frete**. Informe peso em kg, medidas em cm e conteúdo real. Informe a chave da nota fiscal ou selecione declaração de conteúdo quando o envio for não comercial.
3. Faça a cotação e selecione um dos serviços disponíveis: PAC, SEDEX ou Mini Envios.
4. Confira o preço final e clique em **Confirmar pagamento e emitir**. Essa etapa consome saldo SuperFrete.
5. Abra o PDF para conferir. Só depois use **Enviar etiqueta à impressora**.

A impressão simples continua aceitando CPF ausente e dados parciais do Paraguai. A emissão de frete tem validações próprias da transportadora, incluindo CPF/CNPJ do destinatário.

## Bot

Exemplo: “Quero cotar uma etiqueta para este endereço: [dados]. Remetente [nome], pacote [peso e medidas], conteúdo [descrição, quantidade e valor], [nota fiscal ou envio não comercial].”

O bot aceita destinatário e remetente informados na conversa, sem exigir cadastro prévio do remetente. Pode também extrair os dados do bloco de impressão dos remetentes existentes; pede somente campos faltantes. Os dados ficam preservados na cotação sem sobrescrever o cadastro-base. Descrição, quantidade e valor unitário dos itens são usados na declaração informada pelo usuário. O bot apresenta serviços/valores. Após a escolha do serviço, pede confirmação do pagamento. Depois da emissão, envia o PDF no Telegram e pede uma segunda confirmação para imprimir. Não exige comandos com barra.

Confirmações pertencem ao usuário autorizado e à conversa de origem. Cotar não paga. Cancelar a impressão de uma etiqueta paga não cancela nem reembolsa a compra.

## Configuração

```dotenv
SUPERFRETE_TOKEN=seu_token
SUPERFRETE_CONTACT_EMAIL=contato_tecnico
SUPERFRETE_SANDBOX=false
```

Tokens de produção e Sandbox são diferentes. O padrão é Sandbox. No Render, o backend também carrega `/etc/secrets/superfrete.env`, preservando variáveis já definidas no ambiente. Nunca versionar tokens.

Migração: `r8s9t0u1v2w3`. Cria cadastros, padrões e fretes; adiciona anexos à entrega do bot e recupera conteúdo de impressões antigas vinculadas a ações do assistente.

## Operação

O agente Windows existente e o Sumatra continuam sendo usados. A máquina da loja precisa estar ligada com o agente aberto. “Enviado à impressora” indica aceitação pelo agente/Sumatra, não confirmação física do papel.

Impressões usam chaves de idempotência. Pagamentos são marcados antes da chamada externa. Uma resposta incerta bloqueia novo pagamento automático e permite consultar o estado. Se não houver identificador de frete, confira o painel SuperFrete antes de criar nova emissão.

Documentação oficial: https://superfrete.readme.io/reference/primeiros-passos
