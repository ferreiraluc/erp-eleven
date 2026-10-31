# Clientes, pedidos e pacotes

O cliente é um cadastro reutilizável. Um cliente pode ter vários pedidos, e um pedido
pode ter vários pacotes, cada um com seu código e histórico. Um rastreio também pode
pertencer diretamente ao cliente sem exigir um pedido. Isso não cria uma venda no BI,
no módulo de vendas operacionais ou no PDV.

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
número internacional, sem enviar mensagem automaticamente. Números incompletos
ou sem país inequívoco pedem correção do cadastro; não se adivinha o DDI pelo nome,
endereço ou idioma. A validação de formato não confirma que exista uma conta WhatsApp.

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
