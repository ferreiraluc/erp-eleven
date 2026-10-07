# Gestor de Vendas do PDV

A página **Vendas** (`/vendas-pdv`) fica nas ações rápidas do dashboard, ao lado de
Nova Venda. Consulta exclusivamente `PdvSale`. `/vendas` conserva os lançamentos
operacionais antigos; `/bi-vendas` conserva as planilhas. Nenhuma destas operações
altera Excel, cria conciliações automáticas ou soma receitas entre fontes.

## Consulta e acesso

Filtros por período inclusivo em Brasília, vendedor, pagamento, situação e busca
por cliente, produto, SKU ou UUID. Paginação no servidor, totais do filtro completo
e exportação CSV da página visível. As datas originais de criação são preservadas.
Lucas e Wissam consultam o geral; os usuários com escopo pessoal consultam apenas
suas próprias vendas. O filtro financeiro precede paginação e agregação.

**Somente Lucas** (`is_owner`) pode editar, devolver, estornar ou excluir, inclusive
pela API antiga de cancelamento. Os demais usuários continuam criando vendas.
Esconder botões no frontend não é a autorização efetiva: preview e commit exigem
`require_owner`, e o serviço também confere a identidade.

## Correção

Lucas pode trocar/adicionar/remover itens, quantidades, local, preço, desconto,
cliente, vendedor, observações e pagamentos. O vínculo de catálogo usa ID; o nome,
SKU, cor e tamanho vêm do produto selecionado. Código de barras repetido não
resolve identidade. Itens avulsos não movimentam estoque.

Os pagamentos corrigidos representam o valor aplicado à venda, **sem troco**,
e devem somar exatamente seu total. Moeda original, conversão para guaranis,
valor convertido e referências ficam registrados. A prévia valida limites,
valores finitos, descontos, produtos ativos e saldos suficientes.

A correção aplica apenas a diferença de estoque por produto/local e a diferença
de fiado por cliente. Preserva uma revisão completa antes/depois em
`pdv_sale_events`, antes de substituir as linhas/pagamentos da representação atual.
Não apaga movimentos anteriores nem recebimentos de fiado.
Vendas que já tiveram devolução/cancelamento não são reescritas: a revisão anterior
continua disponível, e outra operação comercial deve ser uma nova venda.

## Devolução e estorno

- **Devolução parcial:** selecionar linha e quantidade restante, com ou sem
  reposição ao local original. Aceita quantidades fracionárias apenas em avulsos.
- **Estorno integral:** estorna todas as quantidades ainda não devolvidas, com
  escolha explícita de repor ou não o estoque.
- Desconto geral distribuído proporcionalmente, com arredondamento cumulativo
  determinístico. Devolver tudo em etapas chega exatamente ao total da venda.
- Fiado é abatido primeiro, limitado ao valor estornado e ao débito efetivamente
  lançado para a venda. A diferença é mostrada como valor a devolver fora do ERP.
  Se o cliente já pagou o fiado, a reversão pode gerar saldo negativo, identificado
  como crédito a favor dele; pagamentos recebidos não são apagados.
- **Nenhum reembolso bancário, Pix ou cartão é executado pela API.** O gestor
  registra o estorno administrativo. O operador realiza e confere a devolução
  financeira no meio original, evitando pagar novamente um crédito já concedido.
- Pagamentos antigos insuficientes, fiado divergente ou totais inconsistentes
  exigem conferência/correção; o sistema não presume dinheiro recebido.
- Produtos retirados do catálogo não são reativados. Uma devolução sem reposição
  pode ser registrada; reposição exige produto válido e saldo consistente.

Situações: `completed`, `partially_refunded`, `refunded`, `cancelled`. Quantidades
acumuladas ficam nas linhas; valores acumulados na venda. Consultas do bot usam o
valor líquido e desconsideram canceladas/excluídas. O histórico de pagamentos da
venda mostra os registros originais; estornos são eventos separados.

## Exclusão preservando auditoria

Excluir uma venda ativa estorna o restante conforme a prévia e marca `deleted_at`.
Uma venda já cancelada/estornada apenas sai da listagem. Nunca remove fisicamente
venda, movimentos, pagamentos, revisões ou recebimentos. Lucas pode consultar
**Histórico de excluídas** no filtro Listagem; não há reativação nesta versão.
Registros cancelados antes deste módulo são preservados sem tentar reconstruir
estornos financeiros que não foram gravados.

## Confirmação, concorrência e histórico

Todas as novas ações passam por motivo → prévia do efeito → checkbox → confirmação.
O plano inclui estado da venda, estoque e fiado. Se algo mudar, retorna 409 e exige
nova revisão. Locks seguem venda, produtos ordenados e clientes ordenados. Falhas
revertem estoque, fiado, venda e auditoria juntos.

`request_id` único e fingerprint vinculam a confirmação à operação exata. Repetir a
mesma requisição retorna o evento existente; outra operação com a mesma chave é
rejeitada. Falha de rede no frontend conserva a chave e permite repetir a mesma
confirmação. Não há integração com provedores de pagamento neste processo.

Lucas vê até as 100 revisões mais recentes na ficha, incluindo itens antes/depois;
as revisões anteriores permanecem no banco. Eventos da auditoria geral:
`pdv_edit`, `pdv_return`, `pdv_cancel`, `pdv_delete`. Consultas não geram auditoria.
A conciliação com o caderno/BI continua planejada em `CONCILIACAO_VENDAS.md`.

## Implementação e validação

- Serviço: `app/services/pdv_management.py`.
- Contratos: `app/schemas/pdv_management.py`.
- API: `GET /api/pdv/management`, `/options`, `/{sale_id}`;
  `POST /{sale_id}/preview` e `/{sale_id}/commit`.
- Frontend: `SalesManagementView.vue`, componentes `pdv/management/`.
- Migração `a3b4c5d6e7f8`: valores iniciais neutros para vendas antigas, devoluções
  por linha e tabela de revisões. Downgrade destrutivo não é automático.
- Testes isolados de cálculo, permissões, devoluções consecutivas, idempotência,
  troca de produto/cliente, fiado, rollback e revisão obsoleta. PostgreSQL valida
  migração e concorrência real; UI validada com dados sintéticos, sem emitir
  pagamentos, estornos externos ou impressões reais.
