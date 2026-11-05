# Execução incremental e evidência de aceite

Cada linha abaixo é um lote de PR, não autorização de deploy. Todos os PRs de código
pertencem ao repositório privado independente. A branch `codex/issue-70-phase-0`
é a única contribuição proposta ao repositório original: documentação, sem merge
automático. Usar `Refs` na descrição; não fechar a #70 ao entregar uma fase parcial.

## Fases e lotes

| Fase / PR proposto | Mudança | Evidência obrigatória |
| --- | --- | --- |
| 0 discovery | Este inventário, arquitetura, riscos, orçamento e baseline | Hashes, testes, restore sintético, limitação do banco vazio |
| 1a isolamento da fonte | Repo privado independente, proveniência, remoção de configurações ativas da loja, CI próprio | Nenhum env/backup/DB real; remoto distinto; scan de artefatos; source manifest |
| 1b runtime seguro | Ambiente explícito, URL/CORS configuráveis, workers/integrations desligados, guardas de instância | Startup recusa target antigo/desconhecido; zero efeito externo no smoke |
| 1c bootstrap SaaS | Migração inicial própria e seeds artificiais; admin configurável na cópia | PostgreSQL vazio → head → login; constraints, triggers, sequências/índices e upgrade; nenhuma revisão antiga alterada |
| 1d staging | Blueprint próprio com previews off, pipeline sem deploy automático até aprovação, smoke local | Login/estoque/PDV/etiquetas/relatórios/rastreio/agente sem provedores reais; staging externo somente após aprovação |
| 2a fronteiras | Contexto imutável, registry de instâncias e permissões; superadmin separado | Token A em B, headers/host forjados, IDs cruzados, contexto ausente rejeitados |
| 2b segurança | MFA superadmin, segregação de secrets/logs, backup/export e observabilidade | MFA bypass/replay/recovery, credenciais distintas, export/cache/upload/print/IA isolados |
| 3a Control Center | Vue/API: tenants, planos, usuários, suporte, auditoria, edição/branding | RBAC e estados vazio/erro/loading; nenhuma credencial ERP revela superadmin |
| 3b indicadores/ações | MRR, churn, inadimplência, IA, provisionamento; confirmação/reversão | Métricas por moeda/período com fixtures; eventos auditados e confirmação vinculada ao objeto/versão |
| 4a billing | Adapter, inbox/outbox, estados, reconciliação e retry | Assinatura inválida/duplicada, atraso, reordenação, timeout, alteração de plano |
| 4b licenças | Resolver central, guardas FastAPI, frontend Vue, grace/read-only/export, cotas | Default deny; invalidação e concorrência; ausência de deleção na suspensão |
| 5a edições | Registry e templates Moda/Varejo/Logística, overrides/addons, branding/hook versionados | A não altera B; dependência inválida/ciclo negado; release e rollback de config |
| 5b rastreio | Primeiro módulo transversal `shipping.tracking` | Start negado via API/job/bot/URL/inclusões indiretas; Pro/Business respeitam RBAC |
| 6a provider | Adapter Render oficial, operações async, approval plan e ownership, health/logs/rollback | Replay e crash entre etapas; alvo antigo/externo negado; mock sem provisionar |
| 6b piloto | 2–3 empresas sintéticas isoladas, onboarding, recuperação e suporte | Teste ponta a ponta local; piloto Render aprovado; custos medidos e evidências de recuperação |
| 6c go-live proposto | Relatório de capacidade, riscos, margens, incidentes e operação | Aprovação comercial explícita após gates; não considerar plano gratuito como SLA |

Ordem: implementar Fase 1 antes de Fase 2, e assim por diante. Uma pendência externa
de staging não impede trabalho local preparatório das fases seguintes, mas impede
declarar aceite integral da fase dependente. Não agrupar todas as fases em um PR.
Nenhum recurso pago/endpoint público/DNS será criado apenas para fechar uma checkbox.

## Matriz de critérios inegociáveis

| Critério #70 | Prova de aceite e fase responsável |
| --- | --- |
| Original intacto | Todas: diff original, ausência de chamadas/mutações operacionais, nenhuma alteração de workflow/Render/DNS; registrar exceções autorizadas |
| Sem cross-tenant | 2/6: duas ou três bases/chaves, token A em B, IDs cruzados em CRUD, relatórios/export, anexos/OCR, bot/job, print/cache/logs; teste concurrente |
| Start sem rastreio | 4/5: matriz de HTTP/serviço/job/bot/listener; contador de chamadas Wonca igual a zero; nenhum dado via cards/pedidos/clientes |
| Suspensão preserva dados | 4/6: comparar contagens/hashes antes/depois; leitura/export autorizado funciona; escrita e efeito externo negados |
| Billing idempotente | 4: evento duplicado/atrasado/concorrente, assinatura ruim, gateway indisponível, retry e reconciliação produzem uma transição auditada |
| Provisionamento seguro | 1/6: credencial separada, ownership/allowlist, aprovações expiradas/adulteradas/reutilizadas rejeitadas; original nunca é target |
| Módulos/edições configuráveis | 3/5: mudar via Control Center, persistir/reiniciar, invalidar cache; alteração A não afeta B; rollback por versão |
| Relatório por fase | Todas: PR(s), commit, testes, limitações, custo real/estimado, riscos e próxima autorização concreta |

## Threat model e testes negativos mínimos

Atacantes considerados: usuário/administrador de uma empresa tentando outra,
cliente HTTP contornando menu, evento externo forjado/repetido, job com contexto
antigo, fornecedor devolvendo URL hostil, suporte com escopo excessivo e erro
operacional no provisionamento. Ativos: DB, documentos/fotos, prompts, dinheiro,
impressoras, tokens, assinaturas, infraestrutura e logs. Trust boundaries: browser/API,
API/DB, control/data plane, filas/provedores, agente e adapter Render.

Testar também caminhos indiretos: `pedido_anexos`, galeria/miniatura, comprovante,
endereços e seus históricos, resumo de rastreio do dashboard, relações cliente/pedido,
respostas do assistente com contexto anterior, export paginado, downloads e polling
de agente; middleware sozinho não cobre CLIs/threads/listeners.

Limitações conhecidas: o inventário ainda não é auditoria linha a linha de todas as
queries; testes isolados do original não certificam tenancy. Um piloto isolado deve
passar em testes adversariais próprios antes de receber dados reais. Não inventar
suporte a múltiplas lojas ou gateway só porque existe uma feature no catálogo.

## Política de releases e validação

- Branches `codex/issue-70-phase-N-*`, PRs pequenos com origem e escopo definidos.
- Manter backend, frontend, print-agent e python-security; CI sem tokens externos,
  sem acesso ao DB da loja, sem deploy e sem instalar agente real.
- PostgreSQL descartável para DDL/locks, SQLite para regras; Node 22 e Python 3.11
  no CI; tipagem e build além dos testes frontend.
- Review do diff, secrets/artifacts, migrações e configuração antes de integrar.
  No repo novo, proteção de main e checks sujeitos às capacidades do plano GitHub;
  se proteção privada não estiver disponível, registrar e não afirmar proteção ativa.
- Release identifica SHA, schema version, edition schema, feature registry e contrato
  da licença; canário sintético antes de promover. Não usar HEAD mutável para deploy.
- Rollback preserva dados e efeitos externos já realizados; schema incompatível
  interrompe promoção. Exports/backups não saem da fronteira do tenant sem autorização.

## Formato do relatório por fase

1. Entregas implementadas e links dos PRs/commits; itens apenas projetados à parte.
2. Testes executados, ambientes, resultados, skips e limitações reais.
3. Evidência de preservação da loja e de ausência de efeitos externos.
4. Custo criado (zero quando local), projeção mensal e variáveis/exclusões.
5. Riscos remanescentes e condições para concluir o aceite.
6. Próximos trabalhos seguros e ação concreta que requer autorização, se houver.

O país de faturamento, gateway comercial, domínio novo, região/owner Render,
política de retenção e cotas reais de IA serão definidos antes das integrações
externas correspondentes. Até lá, usar contratos configuráveis e fixtures sintéticas;
não escolher um país ou conta existente por inferência.
