# Clientes, pedidos e pacotes

O cliente é um cadastro reutilizável. Um cliente pode ter vários pedidos, e um pedido
pode ter vários pacotes, cada um com seu código e histórico. Um rastreio também pode
pertencer diretamente ao cliente sem exigir um pedido. Isso não cria uma venda no BI,
no módulo de vendas operacionais ou no PDV.

## No ERP

Os cards de rastreamento no dashboard e na página de encomendas compartilham
fundo opaco levemente tonalizado, contorno completo, acento lateral por status e
sombra curta, definidos em `frontend/src/assets/trackingCards.css`. Amarelo indica
pendente, azul trânsito, verde entregue e vermelho falha/não encontrado; o texto
do status continua presente. A borda permanece no celular, sem depender de hover.
Descrições e previsões usam texto mais escuro. A alteração é visual: preserva
filtros, expansão, ações e as listas distintas de mobile e desktop.

Na página de encomendas, telas abaixo de 1200px e tablets de toque até 1366px
usam apenas o card expansível; a linha e o painel de desktop ficam ocultos juntos,
sem barras vazias ou detalhes repetidos. Busca e status ficam lado a lado no tablet;
no celular, empilhados. Copiar/expandir e as três ações têm áreas de toque uniformes.
O histórico expandido acompanha o conteúdo, sem limite de altura que corte eventos.

- Em **Clientes**, Ativos é a seleção inicial; Inativos mostra apenas os cadastros
  desativados e Todos inclui os dois estados. A busca respeita a seleção. A API
  mantém ativos como padrão e aceita `include_inactive=true` para consultar ambos.
  A tela consulta páginas de 20 clientes, com busca e filtro aplicados antes da
  contagem no servidor. O total cobre o diretório completo, inclusive cadastros
  além dos primeiros 200; cadastros consolidados continuam fora de todas as listas.
  Mudar a busca ou o estado retorna à primeira página. Respostas atrasadas não
  substituem a seleção atual, inclusive durante a espera curta da busca.
  Falha oferece tentar novamente na página solicitada, sem exibir total antigo
  ou tratar a falha como lista vazia. Se a última página ficar vazia após uma
  inativação, a tela retorna à última página existente.
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

Clientes existentes não são fundidos automaticamente. Vínculos explícitos têm prioridade; documentos,
contatos e nomes existentes não são substituídos. Ao editar um endereço, selecionar
expressamente o cliente confirma a revisão (`customer_link_confirmed`); salvar apenas
uma alteração de rua não apaga o aviso. Cadastros PDV conservam sua identidade
financeira, mas podem ser associados ao diretório por `cadastro_cliente_id` ao
selecionar um cliente na nova venda (ver [Vendas PDV](VENDAS_PDV.md)). A consolidação
move esse vínculo sem unir saldos ou alterar snapshots de vendas anteriores.
O servidor valida a consistência cliente/pedido/pacote, inclusive fora da interface.

## Compras do PDV no histórico do cliente

O histórico em **Clientes** inclui **Compras no PDV**, com paginação própria,
situação, vendedor, data em Brasília, itens e quantidades devolvidas. Cada venda
mostra a conta PDV de origem e o nome registrado na venda. A associação considera
exclusivamente `PdvCliente.cadastro_cliente_id`; nomes iguais ou vendas avulsas
sem conta selecionada não criam vínculos. Contas PDV inativas mantêm suas compras
visíveis. Consultar um cliente consolidado resolve o cadastro principal.

O resumo considera todas as vendas visíveis desse cliente, inclusive quando a
lista está paginada. Valor líquido desconta estornos e considera canceladas como
zero, inclusive cancelamentos antigos sem valor de estorno registrado. Vendas
excluídas ficam no histórico reservado do gestor de vendas. O filtro de vendas
pessoais é aplicado no backend antes da contagem, dos totais e da paginação.

Essa consulta não cria vendas, clientes ou vínculos, não reúne saldos de fiado e
não soma receitas do BI ou das vendas operacionais. Os snapshots da venda e as
contas PDV permanecem separados. A API é
`GET /api/clientes/{id}/compras-pdv?page=1&page_size=20` (limite de 100 por página).
Os testes `test_customer_purchases.py` cobrem homônimos, escopo financeiro,
paginação, estornos, aliases, contas inativas e ausência de escritas na consulta.

## Estado dos pedidos

A lista de Pedidos consulta a página solicitada no servidor (20 por vez), com
busca por número, cliente, endereço ou código, status e tag antes de contar e
paginar. Pedidos antigos continuam pesquisáveis, mesmo além dos primeiros cem.
A rota `GET /api/pedidos/pagina` fornece `items`, `total`, `page` e `page_size`;
a rota de listagem anterior conserva seu contrato para outros consumidores.
Consultas atrasadas não substituem filtros mais recentes e falhas oferecem
Tentar novamente. Links com `pedido_id` abrem o cadastro mesmo fora da página.

O atalho Rastreamento da lista e dos detalhes abre a tela existente filtrada pelo
código (ou destinatário quando não há código). Esse atalho apenas consulta;
criar um novo rastreio continua exigindo o formulário e sua confirmação.

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

- `GET /api/clientes/pagina`: `items`, `total`, `page`, `page_size`; aceita busca
  literal por nome, telefone, documento, e-mail e endereço, além dos filtros de
  estado. A rota `/api/clientes/` mantém seu contrato anterior em lista.
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

## Consolidação de clientes duplicados

O proprietário pode usar **Clientes → Conferir duplicidades** ou o mesmo botão em
**Endereços e envios**. A ferramenta apresenta pares candidatos, permite escolher
o principal, exige uma prévia e uma confirmação da identidade antes de unir.
Nomes normalizados iguais são apenas candidatos; CPF/contatos ou vínculos
divergentes bloqueiam a união. O usuário deve conferir os dados, inclusive em
homônimos. Clientes PDV/fiado permanecem contas distintas, com os vínculos
explícitos já implementados, sem soma automática de saldos.

Para endereços, a comparação conservadora já usada no cadastro deve reconhecer o
mesmo destinatário/local. O duplicado vira uma referência inativa ao principal;
jobs, fretes, PDFs e snapshots permanecem nos IDs originais e o histórico segue
as referências. Dados divergentes de documentos/clientes não são mesclados.
Uma alteração após a prévia invalida o token; a confirmação pode ser repetida
após falha de rede sem repetir a consolidação. Nenhuma união roda no deploy.

A revisão é solicitada manualmente e limitada a 10 mil cadastros e 25 pares por
consulta (até 20 registros por nome); o aviso de revisão parcial pede refinar a
busca. Nomes incompletos, grafias diferentes não reconhecidas ou nomes únicos não
são detectados como duplicados por esta tela. Ausência de candidatos não comprova
unicidade. A API aplica a autorização do proprietário em consulta, prévia e
confirmação; nenhuma lista de contatos é enviada a IA.

A revisão `e1f2a3b4c5d6` permite conservar um cliente antigo como referência ao
principal (`clientes.merged_into_id`). Não consolida pessoas durante o deploy.
Uma manutenção explícita pode reunir pedidos, rastreios e endereços de um par
revisado. Não altera nomes de destinatários, endereços das compras, valores, códigos,
PDFs, snapshots de impressão, etiquetas nem os cadastros PDV. Cada operação registra
o responsável e os vínculos movidos na auditoria.

O cadastro de origem fica inativo, preservado para rastreabilidade, e não aparece
nem na lista Todos. Consultar seu ID nas rotas de cliente e histórico resolve o
principal; editar, reativar ou vincular por uma seleção antiga retorna `409` para
atualizar a lista. O bot reconhece os nomes dos aliases explicitamente unidos,
sem usar documentos antigos para sobrescrever os dados do principal. Divergências
de identidade continuam exigindo revisão; nomes parecidos não provocam fusão.
A criação manual também retorna `409` se a identidade já for reconhecida pela
mesma regra usada nos endereços, indicando reutilizar o cadastro existente.

No diretório `backend`, com o ambiente correto, simular um par autorizado:

```sh
venv/bin/python -m app.customer_maintenance merge --target UUID_PRINCIPAL --source UUID_DUPLICADO
venv/bin/python -m app.customer_maintenance merge --target UUID_PRINCIPAL --source UUID_DUPLICADO --apply --expected-plan TOKEN_DA_SIMULACAO
```

O token vincula a confirmação ao conteúdo e aos vínculos revisados. Mudanças entre
simulação e aplicação exigem nova simulação; reaplicar o mesmo par já consolidado
não duplica efeitos. CPF, telefone ou e-mail divergentes impedem a aplicação até
o proprietário confirmar a identidade e o cadastro correto. Somente então se usa
`--reviewed-conflicts`, conservando os dados preenchidos do destino e os originais
na origem. Se apenas um cadastro possui CPF, ele deve ser o principal para respeitar
a unicidade do documento. Nunca aplicar o sinalizador apenas por semelhança de nome.

Usar em uma janela sem edição dos cadastros envolvidos. A transação possui locks
PostgreSQL e limite de espera; em falha, revisar o estado antes de repetir. A
confirmação exige o administrador Lucas ativo para auditoria. O downgrade recusa
remover aliases existentes. `test_customer_maintenance.py` e
`test_customer_maintenance_postgres.py` cobrem histórico, conflitos, rollback,
migração e concorrência entre aplicações da mesma consolidação.

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
