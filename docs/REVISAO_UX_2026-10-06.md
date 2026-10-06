# Revisão de UI/UX — madrugada de 06/10/2026

## Escopo e orçamento

Revisão autorizada pelo responsável da loja, com agentes usando o ERP local para
encontrar problemas reais de responsividade, navegação e controles. Preservar o
estilo atual, permissões, confirmações, dados e fluxos operacionais.

- Referência às 23h56 de 05/10: 29% do limite semanal consumido, 71% restante.
- Orçamento solicitado: aproximadamente 14,2 pontos percentuais nesta madrugada.
- Margem: parar de iniciar trabalho ao chegar a 39% usado (61% restante), ou se
  outra janela tiver menos de 25% restante. O consumo é compartilhado pela conta;
  percentuais não são um teto rígido configurável por tarefa.
- Heartbeat `melhorar-ui-do-erp-nesta-madrugada`: 1h, 2h, 3h, 4h, 5h e 6h locais;
  encerrar até 7h de 06/10. Não renovar automaticamente para outras noites.
- Rodadas de até 15 minutos; no máximo um subagente por rodada agendada, sem
  delegação recursiva. Conferir uso antes/depois de cada conjunto de alterações.
- Não usar créditos de reset, comprar créditos ou fazer chamadas pagas de IA.

O computador precisa permanecer ligado e o aplicativo aberto. A configuração da
automação é local ao Codex, não um serviço instalado no ERP/Render.

## Ambiente de QA disponível neste computador

Nunca usar o banco de produção para estes testes. O ambiente descartável existente
usa PostgreSQL local em `127.0.0.1:55439`, banco `postgres`, schema `eleven_ui_qa`.
O script local ignorado `.tmp/access-audit/qa_server.py` substitui a conexão,
desabilita assistente/integrações e fornece usuários/dados fictícios.
Leia o script antes de reiniciar; não execute scripts de conciliação de produção.

```sh
backend/venv/bin/uvicorn qa_server:app --app-dir .tmp/access-audit --lifespan off --host 127.0.0.1 --port 8000
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev -- --mode test --host 127.0.0.1
```

Acesse `http://localhost:3000` pelo navegador, não pelo IP (CORS).
As credenciais fictícias estão no script local; não são as senhas de produção.
Use abas temporárias, confira `innerWidth` após mudar a viewport e restaure a
viewport ao terminar. Não enviar impressão, comprar etiqueta nem sincronizar BI.
Cancelar formulários após inspecionar. Para erros/requisições concorrentes, preferir
testes de componente com mocks. Não interromper servidores sem verificar quem os usa.

## Rodada inicial — validada localmente

- Reproduzido em 384px: cabeçalho de 193px, com Sair isolado na linha seguinte.
  A navegação móvel agora preserva os quatro textos na mesma linha e omite ícones
  decorativos. Altura medida caiu para 125px; desktop conserva os ícones.
- Novo produto: regra global de botões anulava a compactação local. Corrigida a
  especificidade somente no card; largura móvel de 122px para 103px, altura 32px.
  Até 360px, rótulo visual Novo; nome acessível completo Novo produto.
- Medições de dashboard em 320/360/384/412/768/1024/1440px sem overflow horizontal.
  Em 320px, botão Novo e título do card ficaram na mesma linha. Dropdowns de moeda
  e idioma abriram dentro da tela, e o atalho abriu Novo Item (cancelado sem salvar).
  PT/ES/EN mantiveram as ações da conta na mesma linha; espanhol exigiu menor
  padding horizontal para preservar também as bordas dos botões dentro da tela.
- Agente de fluxos corrigiu feedback de erro/retry e concorrência por vendedor.
  QA local: busca sem correspondência mostrou Limpar Filtros e restaurou os cinco
  vendedores ao limpar. Testes com mocks cobrem falhas, traduções e concorrência.
- Agente de navegador inspecionou Estoque e Endereços em 384/768px: sem overflow
  horizontal; formulários abertos/cancelados. Os dois problemas confirmados abaixo
  ficam para a próxima rodada. Erro inicial transitório sumiu após recarregar e não
  foi classificado como defeito persistente.
- Validação: 168 testes em 28 arquivos passaram, type-check/build e diff-check.
  Build conserva aviso anterior de importação estática/dinâmica de `api.ts`.
- Publicação: commit `8686d8e`, frontend Render confirmado Live às 00h06;
  deploy `dep-db26atk9v7es7385ruvg`. CI de código: execução `37407324766`.
- Consumo ao concluir o código: 33% usado, 67% restante; incremento de quatro
  pontos desde o início, incluindo os dois agentes da revisão inicial.
- Servidores locais de QA encerrados após validar; reiniciar conforme os comandos
  acima na próxima rodada. Abas temporárias fechadas e viewport restaurada.

## Próximas correções candidatas

Confirmar o problema no navegador e limitar o trabalho antes de implementar:

1. Atalhos de pedido para rastreio: `PedidosView.vue` e `PedidoDetailsModal.vue`
   usam a rota inexistente `rastreamento-detalhes`. A alternativa passa `pedido_id`
   e `codigo_rastreio`, mas `RastreamentoView.vue` só lê `query.search`. Usar a busca
   existente para consulta; qualquer criação deve abrir uma prévia e exigir salvar.
2. **Resolvido na rodada 3.** Clientes: botão Todos alterava `showInactive`, mas o store não enviava esse filtro;
   API assume `ativo=true`. Tornar a seleção efetiva sem mudar o padrão da API.
3. Pedidos: `filteredPedidos` é renderizado inteiro e Próxima só muda `currentPage`;
   consulta inicial limitada a 100 pela API. Resolver paginação/filtros de forma
   coerente para o conjunto todo, sem simplesmente paginar os primeiros 100.
4. **Resolvido na rodada 2.** Estoque: busca sem resultados oferecia Criar primeiro item mesmo com sete
   produtos existentes. `InventoryListView.vue`, vazio próximo à linha 241.
   Diferenciar filtros sem correspondências de catálogo vazio; oferecer limpar busca.
5. **Resolvido na rodada 2.** Endereços: busca sem resultados oferecia Nenhum endereço aqui ainda/Cadastrar
   endereço e paginação 1–0 de 0. `AddressesView.vue`, início do template.
   Mostrar ausência de correspondência e intervalo correto para zero resultados.

Preservar o arquivo preexistente não rastreado
`backend/tests/test_assistant_inventory_identity.py`, pertencente a outro trabalho.
Registrar abaixo cada rodada: evidência, arquivos, testes, commit/deploy, consumo
e pendências. Não declarar UI perfeita nem dispositivo físico testado com base
somente em viewport emulada.

## Rodada 2 — buscas vazias (00h09–00h15)

- Consumo inicial 33%; medição após implementação 35% usado (65% restante).
- Estoque: busca/filtros sem correspondências permitem Limpar Filtros; lista vazia
  sem filtros oferece Novo item. Reset limpa os filtros, conserva visualização/
  agrupamento e não abre formulário. Debounce não repete a consulta ao limpar e é
  cancelado ao desmontar a tela.
- Endereços: diferencia busca aplicada de primeiro cadastro; limpa os filtros
  explicitamente e retorna aos ativos. Paginação vazia é 0–0 de 0, e a faixa não
  ultrapassa a quantidade real de itens retornados. Textos em PT/ES/EN.
- QA local: estoque com sete produtos → busca vazia → limpar → sete produtos;
  agenda com um endereço → busca vazia → limpar → um endereço e faixa 1–1 de 1.
  Sem cadastro, impressão, compra, sync ou alteração de dados da loja.
- Estoque validado em 384px; agenda em 320/384/768/1280px sem overflow horizontal,
  com botão de recuperação dentro da largura disponível.
- 173 testes passaram em 29 arquivos; type-check, build e diff-check passaram.
  Casos novos cobrem filtros combinados, preservação de agrupamento, consulta
  única ao limpar, catálogo realmente vazio, traduções e parâmetros da agenda.
- Próxima prioridade: itens 1–3 acima (navegação de rastreio, filtro de clientes,
  paginação real de pedidos). Não repetir os itens 4–5 resolvidos.
- Publicado: commit `e10212d`, Render Live no deploy `dep-db26f1jncjis73c9sspg`.
  CI de código `37408022884`. Servidores QA encerrados, aba temporária fechada e
  viewport restaurada. Consumo após publicação: 36% usado (64% restante).

## Rodada 3 — filtros de clientes (01h00)

- Consumo inicial: 36%; após implementação: 37% usado, 63% restante. Escolhido o
  filtro de clientes como correção pequena, compatível com a margem disponível.
- Seleção explícita Ativos/Inativos/Todos. API mantém ativos como padrão, aceita
  `ativo=false` para inativos e `include_inactive=true` para ambos, sem mudar
  autenticação, busca ou paginação. Nenhuma migração necessária.
- Respostas antigas não sobrescrevem o filtro atual; erros mostram Tentar novamente.
  Busca sem resultado oferece Limpar Filtros. Salvar/inativar recarrega a seleção.
- QA somente local: dois ativos e um inativo fictícios, resultados 2/1/3; busca de
  inativo em Todos, resultado vazio em Ativos e recuperação ao limpar. Larguras
  320/384/768/1280 sem overflow; nenhum cadastro real alterado.
- 24 testes direcionados do backend e 176 testes frontend passaram; type-check e
  build passaram após completar tradução de retry e ajustar NodeList no teste.
- Limitação anterior mantida: Clientes ainda carrega até 200 itens na interface;
  o escopo desta rodada foi situação/busca, não paginação de grandes cadastros.
  A API continua aceitando skip/limit. Registrar essa paginação para rodada futura.
- Pendências principais: atalhos de rastreio do pedido e paginação de pedidos.
- Publicado: commit `dfc4b92`, frontend e backend confirmados Live no Render
  (`dep-db277d6q1p3s73ebot60` / `dep-db277d6q1p3s73ebosp0`). CI `37412104934`.
  QA local encerrado, abas temporárias fechadas e viewport restaurada.
  Consumo após publicação: 38% usado (62% restante). Antes da próxima ação,
  consultar novamente o limite; ao atingir 39%, pausar a automação.

## Encerramento preventivo — 02h00

- Nova consulta de uso retornou 39% semanal consumido (61% restante), atingindo
  o limiar preventivo. Nenhuma nova implementação foi iniciada nesta rodada.
- Automação `melhorar-ui-do-erp-nesta-madrugada` confirmada como PAUSED; os dois
  agentes já estavam concluídos, sem trabalho em execução.
- Variação observada desde o início: aproximadamente dez pontos percentuais da
  cota compartilhada da conta. Esse indicador inclui outras tarefas da conta e
  não permite atribuir todo o consumo exclusivamente a esta revisão.
- Três rodadas publicadas e validadas. Pendências para futura retomada: atalhos
  de pedido para rastreio, paginação real de pedidos e paginação de clientes
  acima de 200 registros. Não há promessa de conclusão de toda a revisão.
- Nenhuma compra de créditos ou uso de reset. Arquivo de teste preexistente não
  rastreado preservado; encerramento altera somente este diário.
