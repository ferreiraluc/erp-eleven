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
