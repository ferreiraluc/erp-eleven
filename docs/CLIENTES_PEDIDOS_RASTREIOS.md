# Clientes, pedidos e pacotes

O cliente é um cadastro reutilizável. Um cliente pode ter vários pedidos, e um pedido
pode ter vários pacotes, cada um com seu código e histórico. Um rastreio também pode
pertencer diretamente ao cliente sem exigir um pedido. Isso não cria uma venda no BI,
no módulo de vendas operacionais ou no PDV. Os novos **pedidos com reserva** só
geram uma venda PDV quando o operador confirma sua conclusão; pedidos antigos
continuam como cadastros logísticos, sem reservas presumidas.

## Pedidos separados e conclusão no PDV

**Novo pedido** oferece seleção de cliente e produtos de catálogo, com foto,
tamanho, cor, quantidade e origem **Loja/Depósito**, no estilo do PDV. Cada linha
guarda o ID real do produto; texto, código de barras repetido ou nome semelhante
não vinculam peças automaticamente. A busca inclui o nome e o código interno dos
produtos separados, permitindo localizar o pedido de uma peça reservada.

Ao confirmar a separação, o estoque físico continua igual. Os contadores
`reserved_loja`/`reserved_deposito` descontam apenas o **disponível** de cada local.
Por exemplo: físico 1, reservado 1, disponível 0. O produto continua pertencendo à
loja, mas não pode ser vendido, transferido, excluído ou reduzido por ajuste como
se estivesse disponível. Reservar não gera baixa, receita, fiado ou movimentação
fictícia. A lista mostra a reserva e oferece acesso a Pedidos para identificar a
sacola. Cada local tem seu saldo próprio; reservar na loja não ocupa o depósito.

Pedidos mantêm duas situações independentes: **comercial** (`reserved`,
`completed`, `cancelled`) e **logística** (pendente, processando, enviado,
entregue, cancelado). Uma atualização de rastreamento não libera reservas nem
conclui pagamentos. A reserva não expira automaticamente: permanece até concluir
ou cancelar explicitamente. Pedidos existentes não reservam produtos por análise
de sua descrição; para separar suas peças, crie um pedido com seleção do catálogo.

O cliente é selecionado pela identidade PDV existente; o vínculo ao diretório é
preservado por `cadastro_cliente_id`. Não é criada outra pessoa por comparação de
nome. Vendedor e data/hora são registrados ao separar. Contas com acesso às
próprias vendas também veem somente seus pedidos comerciais; cadastros logísticos
antigos conservam o compartilhamento existente. O backend aplica esse filtro nas
listas, nos históricos de Clientes e nas consultas do assistente.

### Pagamentos parciais

**Receber no PDV** abre o pedido já montado e identificado. Um pagamento parcial
pode ser registrado sem concluir a venda: a sacola permanece reservada, com
**Recebido** e **Saldo pendente**. Cada lançamento conserva moeda original,
câmbio, método, valor aplicado, eventual taxa opcional de cartão, referência,
operador e data. A taxa de cartão segue as regras existentes do PDV. O câmbio de
apresentação do pedido fica congelado na separação; pagamentos conservam suas
próprias taxas acordadas. Não há cobrança automática em banco ou operadora.

Adiantamentos precisam ser positivos, não podem exceder o saldo e não aceitam
fiado. O pedido totalmente pago continua reservado até o operador concluir. A
edição de itens não pode reduzir o total abaixo do recebido; pedidos com
pagamentos não podem trocar de cliente. Para desistência, **Lucas** registra a
devolução conferida fora do ERP, com motivo. O registro original permanece no
histórico. Enquanto houver recebimentos ativos, cancelar é bloqueado. Registrar
a devolução no ERP não executa um reembolso bancário.

Na conclusão, os adiantamentos são aplicados uma única vez, somados aos novos
pagamentos. O servidor valida que cobrem o total; fiado não conclui pedidos
reservados. Excesso somente gera troco quando há dinheiro suficiente, conforme o
PDV. O histórico do pedido inclui também os pagamentos finais e mostra o troco.
Na mesma transação, o sistema libera suas reservas, baixa o estoque físico e
grava **uma única venda PDV**, mantendo cliente, vendedor e o câmbio do pedido.
Os pagamentos antecipados conservam sua data original na venda. O ticket final
usa o fluxo de vendas existente. Cancelar ou corrigir depois da venda usa o
gestor de vendas; não reabre automaticamente a reserva.

### Ticket da sacola

O ticket de separação identifica **ELEVEN**, pedido, cliente, vendedor,
data/hora de separação, peças, cores/tamanhos, local, total, recebido e saldo.
É um comprovante de separação, e não uma venda ou outro recebimento. Pode ser
baixado em PDF ou enviado explicitamente à impressora de tickets de bobina
contínua de 80 mm. Utiliza a mesma fila e agente do caixa, sem mudar etiquetas
Zebra nem a impressão A4. Novas cópias exigem solicitação; pedidos com ticket
pendente não disparam outra impressão. O snapshot de cada trabalho é imutável.

### Concorrência, histórico e contratos

Criação, edição, recebimento, devolução registrada, cancelamento e checkout usam
`request_id` durável, confirmação explícita e revisão `expected_version`.
Uma resposta de rede perdida pode ser repetida com a mesma chave e conteúdo;
isso não duplica reservas, pagamentos ou vendas. Conteúdo diferente com a mesma
chave é recusado. Revisão antiga exige atualizar e conferir. Locks seguem chave
da operação, identidade de clientes, pedido, produtos ordenados, cliente e fila.
O saldo é relido sob lock; dois funcionários não podem reservar/vender a mesma
última peça. Qualquer falha reverte todo o conjunto.

- `POST /api/pedidos/reservas`: criar com cliente PDV, itens, preços e câmbio.
- `GET/PUT /api/pedidos/{id}/reserva`: ficha e edição revisada.
- `POST /api/pedidos/{id}/pagamentos`: registrar um recebimento parcial.
- `POST /api/pedidos/{id}/pagamentos/{payment_id}/estornar`: registrar devolução
  conferida, exclusiva do proprietário, sem contato com provedores.
- `POST /api/pedidos/{id}/cancelar`: liberar reserva sem apagar o histórico.
- `POST /api/pedidos/{id}/checkout`: aplicar adiantamentos e concluir no PDV.
- `GET /api/pedidos/pagina`: `commerce_status=reserved|completed|cancelled|legacy`,
  busca e paginação no servidor. Resumos financeiros são campos da própria
  listagem, sem carregar todas as linhas/pagamentos de cada card.

A migração `z8i9j0k1l2m3` é aditiva: inicia reservas em zero, conserva saldos
físicos e pedidos históricos e cria linhas, pagamentos e recibos de operações.
Não deduz reservas antigas, não junta clientes e não registra vendas no deploy.
As operações guardam antes/depois e o responsável. O endpoint antigo não pode
alterar valores, cliente ou cancelar um pedido comercial, e a exclusão física é
bloqueada. Correções do Lucas na venda final preservam os pagamentos originais do
pedido, mesmo quando o gestor substitui as linhas de pagamento da venda.

Na publicação, disponibilizar primeiro o backend e aguardar a instância anterior
encerrar, antes de liberar as telas de reserva. Depois que houver reservas ativas,
não reverter para uma versão do backend que desconheça os saldos reservados;
uma correção deve preservar essas proteções. Aparelhos com a interface antiga
precisam recarregar para mostrar o disponível, mas o backend atualizado já recusa
saídas que consumiriam peças separadas.

Os testes isolados cobrem alterações por local, pagamentos e estornos registrados,
edição obsoleta, cancelamento, rollback, limites e escopo de acesso. PostgreSQL
valida a migração, concorrência na última peça e repetição simultânea de criação,
pagamento e conclusão; nenhuma validação envia pagamentos ou impressões reais.

### Arquivar a listagem e começar uma lista nova

Lucas pode conferir a prévia e **arquivar os pedidos existentes**. O arquivo
altera somente a visibilidade na listagem: os registros, clientes, rastreios,
anexos, pagamentos e vendas permanecem vinculados e consultáveis. O seletor
**Atuais / Arquivados / Todos** permite acessar o histórico com o mesmo escopo de
permissões; vendedores continuam vendo apenas seus pedidos comerciais.

A operação exige confirmação explícita de toda a prévia. Pedidos legados e
comerciais concluídos, cancelados ou totalmente devolvidos podem ser arquivados.
Qualquer reserva, condicional ou devolução com recebimento ainda pendente bloqueia
o lote inteiro, para não ocultar peças separadas, peças com clientes ou valores a
resolver. O arquivamento nunca libera reservas, devolve peças, estorna pagamentos
ou exclui pedidos. Pedidos arquivados também não podem ser excluídos pela rota
antiga de exclusão.

- `GET /api/pedidos/arquivo/preview`: contagem completa, bloqueios e amostra dos
  primeiros 50 pedidos; exclusivo de Lucas.
- `POST /api/pedidos/arquivo/confirm`: `request_id`, `confirm: true`, `plan_token`
  e `expected_count` da prévia. Mudanças desde a conferência são recusadas sob
  lock; repetir a mesma confirmação devolve o recibo persistido sem duplicar o
  arquivamento. Uma nova inclusão concorrente que não constava da prévia permanece
  atual, e o resultado informa `remaining_count`.
- As listagens `/api/pedidos/pagina` e `/api/pedidos/` aceitam
  `listing=current|archived|all`, com `current` como padrão. Consultas por ID e
  históricos de clientes preservam o acesso aos registros arquivados.

A migração `b0k1l2m3n4o5` apenas adiciona `archived_at`, `archived_by` e o recibo
de operação. Não arquiva nenhum registro durante a publicação. Os testes isolados
verificam escopo, bloqueios, preservação de estoque, repetição e prévia obsoleta;
PostgreSQL verifica migração aditiva e confirmações concorrentes.

## No ERP

### Cards e atividade do cliente

Em **Clientes**, cada cadastro usa um card expansível com o mesmo acabamento dos
cards de rastreamento: contorno, acento lateral, fundo suave e informações compactas.
O cabeçalho mostra nome, contato, compras do PDV, rastreios e solicitações de
impressão, além das datas da última compra e da última solicitação. Pedidos aparecem
separadamente quando existem; seu valor não é somado ao total de compras do PDV.
Clientes inativos mantêm o histórico e têm indicação visual própria.

O seletor **Organizar clientes** permite ordenar por nome, últimas compras ou
últimas impressões. A ordenação ocorre no servidor antes da paginação, respeitando
busca e estado; clientes sem a atividade escolhida aparecem ao final, com desempate
por nome e ID. Os resumos da página são carregados em conjunto, sem consultar o
histórico de cada cliente individualmente nem trazer PDFs ou snapshots de impressão.
O escopo pessoal de vendas é aplicado antes da contagem e da ordenação por compra.

Ao expandir, as abas **Compras PDV**, **Pedidos e pacotes** e **Endereços e impressões**
carregam seus detalhes somente quando acessadas. As listas conservam paginação
própria; datas novas de atividade e compras usam o horário de Brasília. Uma associação
concluída atualiza o resumo sem recolher o card. Falhas de consulta continuam distintas
de um histórico vazio.

O contador de compras exclui vendas canceladas ou retiradas da listagem. A seção de
compras mantém os cancelamentos visíveis no histórico permitido e mostra valor
líquido, devoluções e pagamentos registrados com método, moeda, valor original e
equivalente. Pagamentos originais de uma venda cancelada não são recebimentos novos;
fiado, troco e estornos não são somados novamente como faturamento. As contas de
fiado permanecem separadas, assim como vendas operacionais e resultados do BI.

**Impressões solicitadas** conta os trabalhos persistidos ligados aos endereços do
cliente, incluindo referências antigas consolidadas. Uma tentativa de rede do mesmo
trabalho não cria outra solicitação; uma nova cópia confirmada é outro trabalho.
O card distingue fila pendente e envio incerto; `submitted` continua significando
entrega à conexão/spooler, sem sensor que confirme o papel. Documentos avulsos
temporários do bot e trabalhos sem endereço vinculado não são atribuídos por nome.

### Associação automática e conferência de históricos

Novos pedidos e rastreios aproveitam o endereço compatível ao resolver o cliente,
além dos vínculos explícitos e contatos já reconhecidos. Ao selecionar uma conta PDV
sem vínculo no checkout, uma identidade corroborada por documento ou contato pode
associá-la ao diretório sem unir contas ou modificar saldos e snapshots. Homônimos,
dados conflitantes e cadastros inativos não são escolhidos apenas pela semelhança.

Lucas pode abrir **Associar histórico existente** no card expandido para conferir
registros antigos ainda sem vínculo. A prévia considera nome completo normalizado
com endereço compatível e número, documento ou contato corroborado; rastreios também
podem herdar o cliente de um pedido explicitamente vinculado. Nome igual sozinho
não basta nessa conferência. Registros já vinculados a outra pessoa são preservados.

A consulta é somente leitura. A confirmação associa apenas os registros da prévia,
confere novamente seu estado sob locks e registra o responsável na auditoria.
Mudanças desde a prévia exigem outra conferência; repetir a mesma confirmação não
duplica o efeito. Não ocorre varredura ou associação global ao abrir a lista ou
durante o deploy. Limites da consulta são explícitos: até 200 registros por fonte e
10 mil identidades de clientes. Uma consulta parcial é sinalizada; um conjunto de
identidades incompleto não é usado para provar que não há homônimos.

As rotas dessa ação são exclusivas do proprietário:
`POST /api/clientes/{id}/conciliacao/previa` e
`POST /api/clientes/{id}/conciliacao`, com `expected_token` da prévia e `confirm: true`.
Não imprimem, não criam compras e não fundem pessoas.

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

Novos cadastros em Clientes, contas PDV/fiado e endereços confirmados compartilham a
comparação de identidade: nome completo, sobrenomes compatíveis, documento com tipo e
país, telefone/e-mail ou endereço completo com rua e número. Acentos, pontuação dos
documentos, máscaras de CEP e abreviações reconhecidas de rua são normalizados.
Nome, sobrenome, rua ou CEP isolados não comprovam que duas pessoas são a mesma.
Nomes com alguns nomes intermediários omitidos podem corresponder quando há outra
informação que confirme a identidade.

Uma identidade reconhecida é reaproveitada. Criar novamente o mesmo cliente retorna
o cadastro existente (`200`, em vez de `201`), sem substituir seus contatos atuais.
Se já houver uma pessoa com nome compatível sem confirmação suficiente, ou documento
conflitante, o cadastro manual pede revisão (`409`); não cria outro cliente definitivo.
Nome incompleto também não cria uma pessoa permanente. Um endereço ambíguo continua
salvo e sinalizado para revisão, sem vincular uma pessoa por suposição; isso preserva
a impressão dos dados disponíveis no Paraguai. A prévia sozinha não cria cliente
nem trabalho de impressão. Pedidos e rastreios novos usam a mesma identidade quando
há evidência compatível ou vínculo explícito; um rastreio desconhecido não cria cliente.

O cadastro permite **CPF, CNPJ e RG (Brasil)** e **CI e RUC (Paraguai)**, com vários
documentos por cliente. RG sem emissor pode ser registrado, mas seu número sozinho
não confirma uma associação automática. Números de tipos/países diferentes não são
intercambiáveis. O CPF antigo é preservado; campos genéricos antigos de documento PDV
ou PY não são classificados por adivinhação. CPF ausente não vira zeros. No endereço,
o campo histórico `cpf` conserva o número acompanhado de `documento_tipo` e, para RG,
`documento_emissor`; acrescentar outro documento não troca o tipo do número já salvo.
A emissão SuperFrete continua exigindo CPF/CNPJ, sem substituir por RG/CI/RUC.

Clientes existentes não são fundidos sem confirmação. Nomes e documentos dos aliases
confirmados passam a reconhecer o principal em lançamentos futuros e nas buscas,
sem sobrescrever as identidades originais. Vínculos explícitos têm prioridade; um
conflito de documento no endereço permanece sinalizado. Ao editar, selecionar
expressamente o cliente confirma a revisão (`customer_link_confirmed`); salvar apenas
uma alteração de rua não apaga o aviso. Contas PDV mantêm sua identidade financeira e
`cadastro_cliente_id`; consolidar o diretório move apenas esse vínculo, sem unir
saldos, contas ou snapshots. Havendo mais de uma conta PDV para a pessoa, o operador
escolhe a conta existente. Lançamentos simultâneos de identidade são serializados.
O servidor valida a consistência cliente/pedido/pacote, inclusive fora da interface.

## Compras do PDV no histórico do cliente

O card mostra **WhatsApp** ao lado do telefone. O atalho abre a conversa pelo
número internacional, sem enviar mensagem automaticamente. O cadastro oferece
**País do telefone: Brasil (+55) ou Paraguai (+595)** e uma prévia do número final.
O Brasil exige DDD; no Paraguai, `0981 234567` pode ser informado com o zero nacional.
Ao salvar, o backend valida a escolha e grava o telefone internacional no campo
existente, por exemplo `+595981234567`; não cria outro cliente nem muda sua identidade.
O país do telefone fica no DDI, não representa nacionalidade ou país do endereço.

Números já internacionais são preservados, inclusive ao selecionar outro país por
engano. O zero nacional indevido após `+595` ou `+55` é removido, quando o restante
forma um número válido do país, também ao construir o link
de contatos antigos. Números locais sem DDI mostram **Configurar WhatsApp**, que
abre o cadastro para escolher o país; o botão não fica mais desabilitado. Não se
adivinha o DDI pelo nome, documento, endereço ou idioma e não há alteração em massa
dos telefones históricos. Uma edição de outro campo pode preservar um telefone
antigo ainda sem país. Números incompletos pedem correção; a validação de formato
não confirma que exista uma conta WhatsApp.

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

Ao cotar uma etiqueta SuperFrete, o endereço é reavaliado pelas regras de identidade
e o cliente é capturado no dado interno `_customer_id` do frete, inclusive quando
não foi possível determinar um cliente. Esse campo não é enviado à transportadora.
O vínculo pode vir do diretório ou da conta PDV ligada ao diretório, preservando
a exclusividade desses campos no endereço. Alterações posteriores do endereço
não trocam o destinatário capturado. Rastreios existentes recebem somente um
vínculo ausente e compatível; outros clientes e pedidos não são sobrescritos.

Os contadores e o histórico de impressões incluem endereços vinculados via PDV,
clientes consolidados e IDs antigos de endereços, sem consultas individuais por
endereço. Cada pacote continua com seu próprio rastreio: três envios do mesmo
cliente aparecem na ficha, mesmo originados no bot. Uma venda sem envio não gera
pacote; não se atribui um frete a uma venda PDV específica apenas por nome ou data.

A migração `a7b8c9d0e1f2` cria
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

## Unificar clientes por seleção

O proprietário usa **Clientes → Selecionar**, marca de **2 a 20 clientes** e abre
**Unificar clientes**. A seleção permanece ao pesquisar ou mudar de página. O modal
permite escolher o cadastro principal e conferir documentos, contatos e quantos
pedidos, rastreios, endereços e vínculos PDV serão reunidos. O antigo botão
**Conferir duplicidades** foi removido de Clientes. Em Endereços e envios,
**Conferir endereços** continua tratando apenas duplicidades de endereços.

A confirmação exige declarar que os cadastros são da mesma pessoa. Nomes, contatos
ou documentos preenchidos divergentes aparecem na prévia e exigem uma confirmação
adicional. Isso permite corrigir grafias e cadastros feitos de maneiras diferentes,
sem decidir automaticamente qual pessoa tem razão. Campos já preenchidos no principal
são preservados; documentos das origens continuam registrados nos aliases, inclusive
CPF com unicidade própria. Não se copiam números para sobrescrever documentos atuais.

A união inteira é atômica, com uma única prévia para o grupo: falha em qualquer
vínculo impede alteração parcial. Mudanças nos cadastros ou nos próprios vínculos
invalidam o token; é preciso conferir novamente. Repetir uma confirmação já concluída
não repete seus efeitos. A autorização do proprietário é aplicada no backend, e a
auditoria registra responsável, origens, campos acrescentados e vínculos movidos.

- `POST /api/clientes/maintenance/customers/preview`: `target_id` e `source_ids`
  (1 a 19 origens diferentes do principal).
- `POST /api/clientes/maintenance/customers/confirm`: os mesmos IDs, `plan_token`,
  `confirm: true` e `reviewed_conflicts: true` quando a prévia exigir.

Pedidos, rastreios e endereços passam a apontar para o principal. Contas PDV/fiado
permanecem distintas, com seus saldos e vendas; apenas o vínculo ao diretório muda.
Nomes de destinatários, valores, códigos, PDFs, snapshots de venda/impressão e
etiquetas já emitidas não são reescritos. O histórico do card reúne esses vínculos
sem somar receitas do BI ou das vendas operacionais.

As origens ficam inativas, preservadas para rastreabilidade e fora de todas as listas.
Consultar um ID antigo resolve o principal; editar, reativar ou vincular por uma
seleção antiga retorna `409` para atualizar a lista. A busca por documento tipado ou
identidade de um alias retorna o principal. Registros antigos ainda sem vínculo
podem ser conferidos em **Associar histórico existente**; abrir a lista ou unificar
clientes não executa uma associação global por nome.

A comparação de endereço brasileiro aceita texto livre com campos identificados
(como `N°`, `CEP`, `Cidade` e `Estado Roraima`) e endereço estruturado com UF (`RR`).
Exige rua, número e CEP iguais, nome compatível e complementos consistentes;
fragmentos desconhecidos, documentos conflitantes ou homônimos ambíguos impedem
a associação. Não reescreve o endereço original.

A prévia de **Associar histórico existente** também examina o destinatário
registrado no frete de produção cujo código corresponde exatamente ao rastreio.
Isso permite recuperar vínculos antigos quando o rastreio guarda apenas a cidade.
Mudanças nos dados de prova invalidam a prévia; a confirmação é limitada, auditada
e idempotente. PDFs, valores, nomes históricos e snapshots permanecem preservados.

Para endereços, a comparação conservadora continua exigindo o mesmo destinatário/local.
O duplicado vira uma referência inativa; trabalhos, fretes e snapshots mantêm seus
IDs originais, e o histórico segue as referências. A revisão manual de endereços
permanece limitada a 10 mil cadastros e 25 pares por consulta (até 20 por nome).
Nenhuma lista de contatos é enviada a IA para decidir identidade.

A migração `s1b2c3d4e5f6` acrescenta documentos tipados e os campos de tipo/país nas
contas PDV, sem inferir tipos nos dados antigos nem consolidar pessoas no deploy.
A migração anterior `e1f2a3b4c5d6` conserva as origens por `clientes.merged_into_id`.
As rotas antigas de manutenção em pares e a CLI permanecem disponíveis para as
operações existentes; a interface de Clientes usa a seleção de grupo.

### Manutenção operacional em pares

A CLI anterior continua exigindo uma simulação e o token do par, no diretório
`backend` com o ambiente do destino configurado:

```sh
venv/bin/python -m app.customer_maintenance merge --target UUID_PRINCIPAL --source UUID_DUPLICADO
venv/bin/python -m app.customer_maintenance merge --target UUID_PRINCIPAL --source UUID_DUPLICADO --apply --expected-plan TOKEN_DA_SIMULACAO
```

Divergências de documentos tipados, CPF, telefone ou e-mail exigem a revisão explícita
`--reviewed-conflicts`, preservando os valores de cada origem. Na CLI de pares, se
apenas um cadastro possui CPF legado, ele deve ser o principal por sua unicidade.
A seleção de grupo da interface preserva o CPF no alias e não exige essa escolha.
Não usar a confirmação de diferenças apenas por semelhança de nome. A aplicação
exige Lucas ativo para auditoria; locks PostgreSQL e token protegem a transação.
Downgrades não removem documentos ou aliases existentes.

## Validação e limites

Os testes de seleção, identidade tipada, busca e contas PDV cobrem autorização,
homônimos, documentos conflitantes, aliases, rollback, repetição de confirmações,
históricos e concorrência. As migrações e os locks são validados em PostgreSQL
isolado; SQLite não comprova concorrência PostgreSQL.

Não há associação automática com linhas do Excel ou reconciliação financeira.
Diretório e contas `PdvCliente` continuam entidades distintas. Pacotes arquivados
permanecem no histórico; inativar um cliente não apaga seus pedidos ou rastreios.

## Conciliação dos cadastros existentes

A revisão `d0e1f2a3b4c5` adicionou o estado de revisão dos endereços e a identidade
BI do vendedor, sem executar conciliação de pessoas no deploy. A CLI abaixo gera
uma prévia com rollback; `--apply` confirma uma conciliação previamente autorizada.
Executar no diretório `backend`, com o ambiente do destino configurado:

```sh
venv/bin/python -m app.customer_reconciliation --report /caminho/privado/previa.json
venv/bin/python -m app.customer_reconciliation --apply --report /caminho/privado/aplicado.json
```

A ordem é endereço → cliente → pedido → rastreio. Rastreios antigos não criam
clientes; desconhecidos e ambiguidades permanecem sem vínculo. O comando conserva
snapshots, valores, códigos e auditoria, e pode ser repetido sem recriar operações.
A regra atual exige evidência além do nome para vincular uma identidade existente;
nome único não é identificação infalível. Essa CLI não faz parte do deploy.

## Atualizações por webhook

O monitoramento opcional Wonca usa perfil de 2h e pausa de 21h a 07h (Brasília),
com janela local de 30 dias sem renovação diária. Lucas administra a configuração
no painel de Configurações. Históricos e vínculos com pedidos/clientes permanecem
os mesmos; eventos novos podem avisar o destinatário responsável mesmo sem mudar
Em trânsito para outro status. [Configuração, consumo e limites](RASTREAMENTO_WONCA.md).
