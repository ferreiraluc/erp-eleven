# Clientes, pedidos e pacotes

O cliente é um cadastro reutilizável. Um cliente pode ter vários pedidos, e um pedido
pode ter vários pacotes, cada um com seu código e histórico. Um rastreio também pode
pertencer diretamente ao cliente sem exigir um pedido. Isso não cria uma venda no BI,
no módulo de vendas operacionais ou no PDV.

## No ERP

- Em **Clientes**, abra o histórico do cliente: o painel reúne pedidos, pacotes,
  entregues e em trânsito. Há paginação independente das duas listas.
- **Vincular cadastro existente** recebe o número completo de um pedido ou o código
  de um rastreio. Primeiro mostra o cadastro encontrado; **Confirmar vínculo** salva.
- Em **Detalhes do pedido**, a seção de pacotes mostra todos os rastreios associados,
  inclusive os arquivados, e permite vincular outro rastreio já cadastrado.
- Um código que já pertence a outro pedido não pode ser transferido por acidente ao
  salvar um pedido. É necessário desvinculá-lo expressamente no cadastro de rastreio.
- Ao selecionar um cliente em um pedido, o frontend preenche seus dados para revisão.
  A operação de vincular, sozinha, não troca nomes ou endereços históricos.

Cadastros de pessoas não são unidos por nome parecido, nome idêntico, CPF parcialmente
informado ou telefone semelhante. Vínculos usam IDs confirmados. Homônimos permanecem
separados. O servidor valida a consistência cliente/pedido/pacote, inclusive quando a
requisição é feita fora da interface.

## Estado dos pedidos

O estado logístico considera todos os pacotes ativos do pedido:

- Todos entregues: pedido entregue.
- Pelo menos um em trânsito ou parcialmente entregue: pedido enviado.
- Falha de consulta ou código ainda não encontrado não cancela um pedido.
- Um pedido cancelado manualmente permanece cancelado. Sem pacotes ativos, a
  sincronização preserva o estado existente em vez de concluir entrega por uma lista vazia.

O campo antigo `Pedido.codigo_rastreio` continua como atalho para um código principal.
A lista completa fica na relação `Rastreamento.pedido_id`; trocar o código principal
não apaga os pacotes anteriores. As atualizações Wonca usam essa mesma regra.

## Bot, etiquetas e migração

As consultas do bot encontram tanto o cliente explicitamente vinculado quanto o
nome do destinatário histórico. Isso não muda a regra de priorizar envios atuais e
responder com cada código isolado, seguido de seus detalhes.

Novos rastreios gerados por etiquetas SuperFrete recebem o cliente explicitamente
vinculado ao endereço usado na emissão. A migração `a7b8c9d0e1f2` cria
`rastreamentos.cliente_id` e preenche apenas vínculos comprovados por
`pedidos.cliente_id`; não compara nomes nem reescreve destinatários.

API relevante (autenticação obrigatória):

- `GET /api/clientes/{id}/logistica`: resumo e listas paginadas.
- `POST /api/clientes/{id}/vinculos`: vínculo explícito de pedido ou rastreio.
- `GET /api/pedidos/{id}/rastreamentos`: todos os pacotes do pedido.
- Criação/edição em `/api/rastreamento/`: aceita `cliente_id` e `pedido_id`, herda
  cliente do pedido e rejeita referências conflitantes.

Serviço compartilhado: `services/customer_links.py`. A validação não faz commits,
não chama provedores e não dispensa a confirmação dos fluxos do assistente.

## Validação e limites

`tests/test_customer_links.py` cobre homônimos, herança explícita, snapshots,
idempotência, conflitos, múltiplos pacotes e estados de entrega/cancelamento.
SQLite valida essas regras; a migração e a concorrência dependem de PostgreSQL.

Não há vinculação automática com linhas do Excel, reconciliação financeira ou
fusão de clientes de pedidos com `PdvCliente`. Pacotes arquivados permanecem no
histórico; inativar um cliente também não apaga seus pedidos ou rastreios.
