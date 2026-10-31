# Eleven SaaS Platform

Plano de execução da [Issue #70](https://github.com/ferreiraluc/erp-eleven/issues/70),
iniciado em 18/10/2026. **Este diretório é documentação: não habilita SaaS no ERP da loja.**

- [Fase 0: discovery, segurança e baseline](FASE_0.md).
- [Arquitetura e desenho de dados propostos](ARQUITETURA_PROPOSTA.md).
- [Fases, PRs e critérios de aceite](PLANO_EXECUCAO.md).
- Evidências: [commit e hashes](phase-0/baseline.json),
  [operações HTTP](phase-0/routes.csv), [esquema ORM](phase-0/schema.csv),
  [restore sintético](phase-0/restore-result.json),
  [limitação do bootstrap Alembic](phase-0/empty-migration-result.json).

O ERP original permanece em `ferreiraluc/erp-eleven`. A implementação será publicada
em repositório **privado independente**, sem integração Render até autorização.
O snapshot de origem é `a2f7178a56560924b39e91fa16ed744999a326bd`; novas correções da
loja serão avaliadas individualmente, nunca incorporadas automaticamente.

## Limites da autorização

Autorizados: leitura do código e issues, cópias locais independentes, dados sintéticos,
testes isolados, novo repositório privado, branches `codex/`, PRs e documentação.
Não executar: merge para `main` original, acesso ao banco real para testes,
configuração da infraestrutura original, reuso de segredos, deploys pagos,
exposição de endpoints públicos, migrações de produção ou DNS sem aprovação explícita.
Não registrar webhooks nem instalar agentes nas máquinas da loja.

Cada aprovação futura deve identificar o workspace/projeto independente, recursos,
release SHA, custo recorrente e variável, domínio/endpoint a expor, plano de retorno
e prazo. Aprovar um plano não autoriza qualquer recurso adicional ou ação destrutiva.

## Estado

| Fase | Estado nesta documentação | Limite |
| --- | --- | --- |
| 0 | Discovery e ensaios locais concluídos; PR sujeito aos quatro checks | Não certifica produção, bootstrap completo ou isolamento multi-tenant |
| 1 | Preparação especificada; implementação no repositório independente | Staging Render depende de aprovação e bootstrap válido |
| 2–5 | Projetadas, não implementadas | Aceite exige evidências de código/testes, não apenas estas propostas |
| 6 | Projetada, não executada | Piloto local antes de propor provisionamento pago e go-live |

Nenhuma fase dependente de staging público será marcada como concluída por testes
com mocks. O trabalho local seguro pode continuar enquanto a autorização externa
estiver pendente, com essa pendência registrada no relatório da fase.
