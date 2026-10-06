# Clientes, pedidos e pacotes

O cliente é um cadastro reutilizável. Um cliente pode ter vários pedidos, e um pedido
pode ter vários pacotes, cada um com seu código e histórico. Um rastreio também pode
pertencer diretamente ao cliente sem exigir um pedido. Isso não cria uma venda no BI,
no módulo de vendas operacionais ou no PDV.

## No ERP

- Em **Clientes**, abra o histórico do cliente: o painel reúne pedidos, pacotes,
  entregues e em trânsito. Há paginação independente das duas listas. O mesmo painel
  reúne os endereços, impressões A4 e etiquetas, com data, situação e responsável.
- **Vincular cadastro existente** recebe o número completo de um pedido ou o código
  de um rastreio. Primeiro mostra o cadastro encontrado; **Confirmar vínculo** salva.
- Em **Detalhes do pedido**, a seção de pacotes mostra todos os rastreios associados,
  inclusive os arquivados, e permite vincular outro rastreio já cadastrado.
- Um código que já pertence a outro pedido não pode ser transferido por acidente ao
  salvar um pedido. É necessário desvinculá-lo expressamente no cadastro de rastreio.
- Ao selecionar um cliente em um pedido, o frontend preenche seus dados para revisão.
  A operação de vincular, sozinha, não troca nomes ou endereços históricos.

Novos endereços salvos no gestor, cotados no bot ou usados em uma impressão confirmada
recebem um cliente. A resolução normaliza acentos, espaços e telefones completos; usa
documento compatível com o nome, nome/telefone ou nome completo único sem conflito de
documento/telefone. CPF ausente não vira zeros; RUC/C.I. permanece no endereço PY.
Sem correspondência, cria um cliente com os dados recebidos. Nome incompleto,
homônimos, documento divergente ou cadastro inativo ficam sinalizados para revisão.
Isso não impede a impressão PY dos dados disponíveis. A prévia de impressão sozinha
não cria cliente nem trabalho na fila.

Clientes existentes não são fundidos. Vínculos explícitos têm prioridade; documentos,
contatos e nomes existentes não são substituídos. Ao editar um endereço, selecionar
expressamente o cliente confirma a revisão (`customer_link_confirmed`); salvar apenas
uma alteração de rua não apaga o aviso. Cadastros PDV explícitos continuam separados.
O servidor valida a consistência cliente/pedido/pacote, inclusive fora da interface.

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
- `GET /api/clientes/{id}/historico-enderecos`: utilizações paginadas de todos os
  endereços vinculados, inclusive IDs antigos consolidados, sem contar o mesmo uso duas vezes.
- `POST /api/clientes/{id}/vinculos`: vínculo explícito de pedido ou rastreio.
- `GET /api/pedidos/{id}/rastreamentos`: todos os pacotes do pedido.
- Criação/edição em `/api/rastreamento/`: aceita `cliente_id` e `pedido_id`, herda
  cliente do pedido e rejeita referências conflitantes.

Serviços compartilhados: `services/customer_links.py`, `customer_identity.py` e
`customer_reconciliation.py`. A validação não faz commits,
não chama provedores e não dispensa a confirmação dos fluxos do assistente.

## Validação e limites

`tests/test_customer_links.py` cobre homônimos, herança explícita, snapshots,
idempotência, conflitos, múltiplos pacotes e estados de entrega/cancelamento.
SQLite valida essas regras; a migração e a concorrência dependem de PostgreSQL.

Não há vinculação automática com linhas do Excel, reconciliação financeira ou
fusão de clientes de pedidos com `PdvCliente`. Pacotes arquivados permanecem no
histórico; inativar um cliente também não apaga seus pedidos ou rastreios.

## Conciliação dos cadastros existentes

A revisão `d0e1f2a3b4c5` adiciona o estado de revisão dos endereços e a identidade BI
do vendedor, sem executar conciliação de pessoas no deploy. O comando abaixo gera
uma prévia transacional com rollback; `--apply` confirma a conciliação autorizada.
Executar no diretório `backend`, com o ambiente do destino configurado:

```sh
venv/bin/python -m app.customer_reconciliation --report /caminho/privado/previa.json
venv/bin/python -m app.customer_reconciliation --apply --report /caminho/privado/aplicado.json
```

A ordem é endereço → cliente → pedido → rastreio. Rastreios antigos **não criam
clientes**: somente os clientes existentes, incluindo os criados a partir dos
endereços, podem receber esses vínculos. Nome incompleto, homônimo ou desconhecido
permanece sem vínculo, com motivo no relatório privado. O comando pode ser repetido
sem recriar clientes, pacotes ou utilizações. A conciliação usa locks PostgreSQL,
registra o ator Lucas na auditoria e preserva snapshots, valores e códigos.

Os testes `test_customer_reconciliation.py` e `test_reconciliation_postgres.py`
cobrem identidade, privacidade, histórico, migração e concorrência entre endereços.
Não se deve tratar nome único como identificação infalível: os vínculos continuam
revisáveis no ERP e nenhuma fusão automática de clientes é realizada.
