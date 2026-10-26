# Auditoria de manutenção — 30/09/2026

Revisão estrutural do repositório após as entregas de bot, impressão, endereços,
SuperFrete, BI e cards do dashboard. O objetivo foi tornar o código e sua documentação
mais fáceis de manter, preservando os fluxos da loja. Esta revisão não é uma certificação
de ausência de bugs nem uma auditoria completa de segurança.

## Método e alcance

Foram confrontados imports estáticos/dinâmicos do frontend, rotas, chamadas HTTP,
routers da API, modelos, serviços, CLIs, testes, migrações e configurações de execução.
Uma função ou arquivo só foi removido quando não havia consumidor identificado.
No backend, efeitos de registro, comandos executáveis e referências por migração
foram considerados antes de classificar código como abandonado.

Não houve alteração de dados, planilhas, permissões da loja, histórico de impressão,
compras, mensagens ou migrações aplicadas. Os SQLs históricos foram movidos, não executados.
As remoções de código permanecem recuperáveis pelo histórico Git.

## Limpeza realizada

| Área | Alteração e motivo |
| --- | --- |
| Templates antigos | Removidos resíduos React, páginas Vue de exemplo, logos e estilos sem importadores. O aplicativo real é Vue. |
| Componentes antigos | Removidos `FolgasCalendar.vue` (a aplicação usa `FolgasCalendarAdvanced`) e `PDVPaymentModal.vue` (o PDV implementa o pagamento na tela ativa). |
| Dashboard | Removido store sem dados usados pela tela, com indicadores fictícios e consultas desnecessárias; cards mantêm suas próprias consultas reais. Contratos exclusivos do store também foram retirados. |
| TypeScript | Consolidada declaração de ambiente; corrigidos contratos, nulabilidade, referências a campos inexistentes, refs de inputs e temporizadores usados nos templates. |
| Backend | Retirados sete helpers sem chamadas: antigo hook de saída por venda e utilitários de CPF, comissão, moeda e data. Preservadas as implementações efetivamente usadas. Importação SQLAlchemy atualizada. |
| Scripts e SQL | SQLs manuais anteriores ao fluxo atual foram para `archive/sql`; removidos deploy que referenciava arquivo inexistente e seed isolado de funcionários fictícios. Alembic intacto. |
| Dependências | Removidos Headless UI, Heroicons, VueUse, Tesseract.js e plugin Tailwind Forms sem uso, além de MSAL não utilizado pelo conector OneDrive. Removido pacote npm duplicado da raiz. |
| Atualizações de segurança | Aplicadas correções compatíveis no lockfile npm, sem `--force` nem migração de framework. Auditoria npm: 18 alertas antes, zero depois. `python-multipart` atualizado de 0.0.26 para 0.0.32 para corrigir cinco alertas identificados pelo Dependabot (dois altos e três baixos). |
| Diagnóstico antigo | Removidos logs de login com credenciais/resposta, script de depuração no HTML e endpoints de diagnóstico do servidor Express opcional. |
| Build e execução | Docker simplificado, exclusões para segredos/artefatos, argumento Vite no build; referência Render corrigida; comandos usam `npm ci`. Docker não foi executado nesta máquina. |
| Repositório | Arquivos locais de máquina deixaram de ser rastreados e continuam no disco. `.gitignore` atualizado. |
| Documentação | README, escopo, arquitetura, desenvolvimento, operação e guias revisados; estudos antigos identificados em `archive/`; instruções de manutenção em `AGENTS.md`. |
| Integração contínua | Workflow GitHub para testes isolados do backend, tipagem e build do frontend, sem credenciais de produção ou ações nos provedores. |

## Recursos preservados deliberadamente

- Vendas operacionais, PDV, fiado, câmbio e transferências têm telas/APIs e não são
  código morto. Foram documentados separadamente do BI usado pela loja.
- Twilio está implementado e pode ser habilitado conforme a conta. Não existe um
  conector direto Meta Cloud API a ser documentado como pronto.
- `assistant_setup`, `superfrete_setup` e o import de `assistant_events` têm função
  operacional mesmo sem consumidores convencionais.
- Migrações Alembic, ferramentas Windows, snapshots e vínculos históricos permanecem.
- Express/compression continuam como alternativa de execução do frontend em container;
  o Render atual publica apenas os arquivos estáticos.

## Evidências de validação

| Verificação | Resultado local |
| --- | --- |
| Testes backend, com `DATABASE_URL=sqlite://` explícito | **161 passaram** |
| Tipagem de todo o frontend | **Sem erros**, ante 56 erros na linha de base |
| Build Vite | **Concluído** |
| `npm audit` | **0 vulnerabilidades reportadas**, ante 18 (incluindo 2 críticas) |
| ESLint | Restam **131** ocorrências de `no-explicit-any`; demais erros encontrados foram corrigidos; regras não foram desabilitadas |
| Grafo de imports do frontend | Sem arquivos de código candidatos a órfãos após a limpeza |
| Registro da API | OpenAPI gera 149 caminhos sem iniciar workers ou conectar ao banco real |
| Migrações | Head `y5z6a7b8c9d0`; arquivos Alembic sem alterações |
| YAML | Sintaxe de Render, Compose e workflow verificada |
| Interface local | Login, dashboard vazio, navegação e campos de busca do modal de pedido conferidos com API simulada, sem novos erros de execução |
| Servidor Express opcional | HTTP 200 em `/health`, raiz e rota SPA após build; execução direta Node, sem Docker |

Os números de dependências refletem a base de advisories no momento da execução;
não substituem acompanhamento posterior. A auditoria npm não abrange os pacotes Python.
SQLite não prova comportamento de locks/enums/migrações PostgreSQL. Não foram feitas
compras SuperFrete, impressões físicas ou testes de mensagens externas nesta limpeza.

## Pendências concretas para próximas manutenções

| Prioridade | Pendência | Próximo passo e critério de conclusão |
| --- | --- | --- |
| Alta | Bootstrap PostgreSQL incompleto: as primeiras migrações pressupõem esquema anterior | Criar instalação vazia reproduzível e validá-la em PostgreSQL isolado, sem reescrever revisões aplicadas nem recomendar `stamp head` como instalação |
| Média | 131 usos antigos de `any` | Tipar fronteiras HTTP/erros e stores por módulo; habilitar lint como gate quando a linha de base estiver resolvida |
| Média | Telas e serviços extensos | Extrair componentes/composables e responsabilidades gradualmente, começando por rastreamento, dashboard e estoque; preservar UX e contratos com validação de regressão |
| Média | Endpoint histórico `/api/dashboard/stats` e totais de vendas operacionais | Revisar mistura de moedas e meta fixa antes de usar esses valores para decisão financeira; o novo card de BI não consome esse endpoint |
| Média | Health check não representa prontidão integral | Separar saúde do processo e disponibilidade do banco/workers; atualmente conferir o corpo de `/health`, não apenas HTTP 200 |
| Média | Cobertura de operação real | Complementar testes com PostgreSQL isolado, integração de provedores em ambiente de teste e rotina de recuperação/backups |
| Baixa | Alternativa Docker sem execução validada | Rodar build e smoke test em máquina com Docker, usando banco de desenvolvimento preparado |

Novas revisões devem atualizar este registro quando resolverem uma pendência. Os comandos
reproduzíveis estão em [Desenvolvimento](DESENVOLVIMENTO.md); a rotina de publicação e
diagnóstico está em [Operação](OPERACAO.md).

## Evolução de usabilidade e consulta — 26/10/2026

Esta revisão separa entregas verificáveis de propostas. Não instala monitoramento
contínuo, não treina modelos com dados de clientes e não modifica registros reais
durante testes. As evidências usam fixtures e PostgreSQL isolado com 50 mil produtos.

| Entregue nesta revisão | Uso e limite |
| --- | --- |
| Menos campos repetidos | Marca/categoria apenas no editor de dados em lote; códigos apenas no editor de barras. Quantidade digitada é reaproveitada ao iniciar a grade. |
| Cores PT/EN/ES | Comparação explícita em consultas e escopos por cor, mantendo tonalidades e cadastros. Não é um tradutor genérico. |
| Continuação após QR | Resultado exato separado dos relacionados; mesma grade/cor primeiro, leitura pequena e cancelável, sem contagem ou IA no caminho crítico. |
| Miniaturas em vendas | Metadados em lote e cache existente; snapshots comerciais preservados. |
| Revisão de duplicados | Tela exclusiva do proprietário, prévia versionada e confirmação; referências e históricos conservados. Nenhuma fusão por IA ou durante publicação. |
| Identidade na confirmação da IA | Entrada sugerida pelo assistente registra nome/SKU/marca/tamanho/cor/código/grade revisados. Mudança exige nova prévia; prévias antigas sem identidade são recusadas. Movimentos continuam auditados e idempotentes. |

### Referências pesquisadas e decisões

O [PostgreSQL documenta índices trigramas GIN/GiST para LIKE/ILIKE e similaridade](https://www.postgresql.org/docs/current/pgtrgm.html).
O ERP já possui esses índices, além do índice único da referência interna.
A decisão foi medir as expressões existentes e reutilizá-las, evitando adicionar
índices redundantes e aumentar o custo de cada cadastro sem evidência.
O [Vue recomenda medir atualizações e virtualizar listas grandes](https://vuejs.org/guide/best-practices/performance.html).
Mantemos paginação no servidor, miniaturas sob demanda e consultas canceláveis;
virtualização com grades expansíveis fica condicionada à medição abaixo.

O [Odoo mantém estoque e registros próprios por variante](https://www.odoo.com/documentation/19.0/applications/sales/sales/products_prices/products/variants.html).
Aplicamos essa referência preservando a identidade de cada tamanho/cor, com a
família como navegação e contexto. A [Shopify documenta a consolidação de perfis de cliente](https://help.shopify.com/en/manual/customers/manage-customers?lang=en-US);
aqui a consolidação também é uma ação explícita revisada, com o histórico preservado.
Estas são referências de produto, não promessa de paridade com essas plataformas.

### Plano de melhoria contínua

| Prioridade | Próxima entrega proposta | Critério para liberar |
| --- | --- | --- |
| P1 | Medição de busca por classe: QR exato, nome/modelo, descrição, cor/tamanho e sem resultado | Instrumentação agregada sem texto de clientes, contagem de queries, p50/p95 e tamanho das respostas. Comparar em 50 mil itens; meta inicial de SQL seletivo abaixo de 100 ms e QR abaixo de 50 ms em ambiente controlado, não SLA de rede/produção. |
| P1 | Sugestões de cadastro com as IAs existentes | Foto/etiqueta propõem tipo, material e palavras-chave; conservar fonte e divergências, comparar com vocabulário existente, operador aplica. Não inferir saldo/preço/identidade. Testar 100 exemplos revisados com erros conhecidos antes de mudar prompts/provedores. |
| P1 | Preferências e atalhos de ações frequentes | Usar inicialmente escolhas locais por usuário: local de estoque, moeda, última grade e filtros favoritos; botão para limpar. Sugerir sem preencher silenciosamente produto, cliente ou quantidade. Medir redução de cliques e abandono antes/depois. Não usar o log de auditoria como rastreador de navegação. |
| P1 | Consolidar cadastros reconhecidos como duplicados | Proprietário confere os pares na nova tela, corrige conflitos e escolhe o principal. Conferir históricos antes/depois, sem excluir fisicamente pessoas ou endereços consolidados. |
| P2 | Memória factual com validade | Guardar somente preferências/dicionários aprovados, com autor, fonte, versão, escopo e opção de remover. Reler estoque, preços, permissões e impressoras antes de qualquer confirmação; contexto antigo não substitui consulta atual. |
| P2 | Assistência contextual de consulta | Quando a busca literal não resolver, oferecer interpretação por IA em ação explícita e com timeout; sugestões estruturadas passam pelos mesmos filtros/permissões. Medir acerto no conjunto revisado, latência e custo; falha do provedor mantém a busca SQL disponível. |
| P2 | Prévias e diagnóstico de impressão mais claros | Exibir destino, papel/layout e estado confirmado/incerto; oferecer consulta do trabalho antes de outra cópia. Testar fila/reconexão com transporte local isolado, preservando confirmação e idempotência de Zebra e 3nStar. |
| P2 | Virtualização de listas/grupos muito grandes | Provar ganho de rolagem e memória em S24/iPad com centenas de cards carregados, sem quebrar seleção, teclado, miniaturas ou grupos expansíveis. Só então substituir a renderização atual. |

As [ferramentas da Anthropic usam contratos de entrada definidos pela aplicação](https://platform.claude.com/docs/claude/docs/tool-use).
O uso das duas integrações deve continuar limitado a contratos validados no backend:
uma extrai/propõe e outra pode revisar casos ambíguos sob solicitação, sem duplicar
chamadas pagas em toda busca. Reaproveitar a resposta revisada pelo hash da imagem,
versão do prompt e escopo antes de considerar outra chamada. Não houve alteração
de modelo, novas chamadas pagas ou envio de clientes aos provedores nesta revisão.

### Evidência desta rodada

Em PostgreSQL 17 local, com 50 mil produtos sintéticos e cores equivalentes,
a primeira página de relacionados levou **36,81 ms** no serviço; a consulta de
IDs da família executou em **0,018 ms**, usando o índice existente. Duas páginas
usaram dez consultas pequenas, incluindo a leitura do vocabulário de cores e dos
metadados, sem COUNT, originais de fotos ou consultas por card.
Consultas seletivas de modelo/descrição levaram **0,043–0,266 ms** de execução SQL;
o termo curto `Y 26` levou **16,047 ms**. Planejamento, rede, API e renderização
são custos adicionais; estes valores não medem produção nem prometem latência
fixa. O teste antes/depois das migrações comprova os índices já existentes, não
um ganho novo de centenas de vezes nesta versão.

Foram exercitados: confirmação de identidade após mudança de tamanho/cor,
respostas antigas, paginação e cancelamento de relacionados, escopos por cor,
metadados de vendas sem fotos, conflitos de identidade e duas confirmações
concorrentes da mesma consolidação em PostgreSQL. Revisão visual no Safari em
largura de desktop e área de 412 px, usando somente dados fictícios, sem checkout,
impressão física, limpeza de produção ou chamadas pagas aos modelos.
