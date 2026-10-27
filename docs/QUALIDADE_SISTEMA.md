# Conferência diária do sistema

## Uso e limites

**Auditoria → Conferência do sistema** é exclusiva de Lucas, inclusive na API.
O painel reúne configuração, histórico, cobertura, referências e interpretação
opcional por IA. Uma notificação pessoal abre o relatório correspondente. O painel
só consulta os relatórios ao ser aberto; não inicia trabalho ao visitar o dashboard.

O agendamento inicial é **08h30, Brasília**, diariamente. Instalar depois desse
horário programa a próxima ocorrência; não executa uma varredura histórica no
deploy. Lucas pode pausar, trocar o horário ou desligar a análise por IA. Salvar
essas opções não inicia uma chamada paga. **Conferir agora** enfileira uma análise,
com no máximo três solicitações manuais por dia e uma manual ativa por vez.

A rotina verifica somente dados recentes e filas ativas, com estes tetos:

| Verificação | Cobertura máxima por execução |
| --- | --- |
| Produtos ativos alterados nas últimas 24 horas | 500 registros, sem fotos ou galerias |
| Vendas concluídas nas últimas 24 horas | 100 vendas, sem nomes, valores ou conteúdo dos itens |
| Impressões em estados ativos/problema nos últimos 7 dias | 100 trabalhos, sem PDF ou snapshot |
| Impressoras ativas | 30 dispositivos, sem credenciais |
| Clientes alterados nas últimas 24 horas | 100 cadastros; até 20 consultas indexadas de possíveis correspondências |
| Endereços alterados nas últimas 24 horas | 100 endereços; comparação limitada ao grupo alterado |
| BI e processos | Estado atual, sem consultar planilhas ou iniciar sincronização |
| Referências exibidas no relatório | 100 achados, com paginação |

Os contadores correspondem aos dados analisados, não ao inventário inteiro.
Ultrapassar um teto, limitar comparações ou ocorrer timeout deixa a cobertura
explicitamente incompleta. Um relatório sem pendências não prova que os mais de
50 mil produtos foram conferidos. Não há varredura retroativa completa nem cursor
histórico nesta versão. Itens fora da janela ou além dos limites podem não ser
analisados; a conferência manual operacional continua necessária.

Verificações incluem informações de produto ausentes, saldos divergentes por
local, mínimo superior ao máximo, vendas com itens avulsos sem contexto, envio
incerto/falha/fila parada, dispositivos sem contato, BI sem progresso e processos
sem sinal recente. Dados opcionais ausentes são sugestões de conferência, não
prova de erro. Vendas avulsas são legítimas; uma observação da venda ou resposta
confirmada à sua notificação fornece o contexto sem reescrever o financeiro.

Duplicidades são **candidatas para revisão**, nunca fusões automáticas. Cliente
exige nome completo equivalente e telefone/e-mail armazenado igual; nome isolado
não basta. Endereços usam a equivalência de identidade já existente e apenas o
grupo recente. Limites de comparação aparecem como cobertura incompleta.

## Uso de IA e privacidade

As regras objetivas produzem o relatório mesmo sem IA. Quando habilitada, uma
chamada à DeepSeek interpreta **somente contagens e indicadores de cobertura**.
Se falhar e existir a chave Anthropic, há uma única tentativa com Haiku 5.5.
As configurações e chaves existentes ficam no ambiente do backend. Nenhuma chave
é entregue ao navegador, copiada para o banco de relatórios ou incluída nos logs.

Há um orçamento global de **até duas chamadas por dia de Brasília**, compartilhado
entre execução diária, manuais e retomadas. Cada chamada permite até 600 tokens
de saída; a entrada reconstruída tem no máximo 4 KiB. A reserva é persistida antes
do contato e nunca retrocede ao atravessar a meia-noite. Reiniciar o serviço,
trocar uma configuração ou repetir um pedido não libera outro orçamento.
Depois de uma interrupção pode haver reserva consumida sem resumo; a retomada
usa a conferência objetiva e não tenta cobrar novamente. Esses limites restringem
o consumo, mas não constituem preço fixo ou gratuidade do provedor.

Não são enviados nomes, documentos, endereços, telefones, e-mails, IDs, valores,
imagens, PDFs, motivos de funcionários ou texto livre. O adaptador não carrega
as ferramentas do assistente operacional. A resposta recebe validação de formato
e tamanho, é exibida como **sugestão de IA** e nunca é executada como instrução.
Falha, ausência de chave ou orçamento esgotado preservam o resumo determinístico.

Esta rotina não altera produtos, estoque, vendas, clientes, endereços, pagamentos
ou impressões. Não repete jobs incertos, não compra frete, não chama o bot nem
dispara sincronização do BI. Grava apenas seu histórico, auditoria e notificação
para Lucas. Correções operacionais seguem os fluxos e confirmações existentes.

## Implementação e manutenção

`quality_worker` roda em uma thread da API, separada do envio de notificações.
Seu estado aparece como `quality_worker` em `/health`, sem derrubar a API caso a
conferência pare. O PostgreSQL mantém configuração, pedidos, lease e idempotência.
Uma execução recupera leases vencidos até três tentativas; ao esgotar, encerra
com falha e registra um aviso único. Não abandona eternamente um relatório como
“executando”. Relatórios e referências históricas não são removidos automaticamente.

Cada verificação abre uma transação **READ ONLY** no PostgreSQL, com timeout de
1 segundo por consulta e 250 ms para locks. Há orçamento externo de 15 segundos
para iniciar verificações; uma consulta em andamento ainda pode usar seu timeout.
Falha em uma verificação não oculta as demais. Não há sessão de banco aberta
durante a chamada de IA; timeouts e limites de resposta restringem os provedores.

As migrações são aditivas. Tabelas transacionais e índices concorrentes ficam em
revisões separadas. Os índices de dados recentes e estado/data de impressão não
bloqueiam normalmente as escritas durante a construção; um índice incompleto
desta migração é reparado ao repetir o deploy. Validar PostgreSQL isolado antes
de publicar, preservando os cadastros e históricos anteriores.

`quality_checks.FUNCTIONS` é o ponto de extensão para novas verificações modulares.
Ao acrescentar uma, definir limites, cobertura e gravidade; incluir a chave nas
listas permitidas do resumo/API e nas traduções. Selecionar projeções pequenas,
medir o plano de consulta e testar a transação somente leitura, truncamento,
privacidade e falhas. Não registrar SQL ou ações arbitrárias vindas da IA.

A validação usa dados sintéticos, concorrência real em PostgreSQL, falhas simuladas
dos provedores e um catálogo isolado de 50 mil registros para comprovar uso do
índice da janela recente. A medição local desse caso não é uma garantia de latência
de todo o catálogo em produção. Nenhum provedor pago, venda ou impressão real é
necessário para executar os testes.
