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
- Última medição intermediária: 30% usado, 70% restante.

## Próximas correções candidatas

Confirmar o problema no navegador e limitar o trabalho antes de implementar:

1. Atalhos de pedido para rastreio: `PedidosView.vue` e `PedidoDetailsModal.vue`
   usam a rota inexistente `rastreamento-detalhes`. A alternativa passa `pedido_id`
   e `codigo_rastreio`, mas `RastreamentoView.vue` só lê `query.search`. Usar a busca
   existente para consulta; qualquer criação deve abrir uma prévia e exigir salvar.
2. Clientes: botão Todos altera `showInactive`, mas o store não envia esse filtro;
   API assume `ativo=true`. Tornar a seleção efetiva sem mudar o padrão da API.
3. Pedidos: `filteredPedidos` é renderizado inteiro e Próxima só muda `currentPage`;
   consulta inicial limitada a 100 pela API. Resolver paginação/filtros de forma
   coerente para o conjunto todo, sem simplesmente paginar os primeiros 100.
4. Estoque: busca sem resultados oferece Criar primeiro item mesmo com sete
   produtos existentes. `InventoryListView.vue`, vazio próximo à linha 241.
   Diferenciar filtros sem correspondências de catálogo vazio; oferecer limpar busca.
5. Endereços: busca sem resultados oferece Nenhum endereço aqui ainda/Cadastrar
   endereço e paginação 1–0 de 0. `AddressesView.vue`, início do template.
   Mostrar ausência de correspondência e intervalo correto para zero resultados.

Preservar o arquivo preexistente não rastreado
`backend/tests/test_assistant_inventory_identity.py`, pertencente a outro trabalho.
Registrar abaixo cada rodada: evidência, arquivos, testes, commit/deploy, consumo
e pendências. Não declarar UI perfeita nem dispositivo físico testado com base
somente em viewport emulada.
