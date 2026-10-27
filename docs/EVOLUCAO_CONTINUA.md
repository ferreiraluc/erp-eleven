# Plano de evolução contínua

## Base entregue em 26/10/2026

- Caixa de notificações por usuário, mensagens e regras editáveis por Lucas,
  respostas, histórico e convite de ativação por aparelho.
- Conferência diária com verificações modulares e somente leitura, relatório de
  cobertura e resumo opcional por IA com orçamento global.
- Índices para janelas de atualização e estado/data de impressão, validados em
  PostgreSQL isolado com catálogo sintético de 50 mil produtos.
- Proteção contra alertas de vendas revertidas, modelos vazios que impediriam o
  checkout, repetição de chamadas pagas, relatórios presos e cobertura truncada
  apresentada como completa.

As mudanças de dados sugeridas nos relatórios continuam sujeitas à conferência
de Lucas nos módulos existentes. Identidades consolidadas, snapshots e histórico
operacional não são apagados como forma de “limpeza”.

## Próximas etapas propostas

| Prioridade | Trabalho | Evidência necessária antes de ativar |
| --- | --- | --- |
| 1 | Revisar recorrências dos relatórios: avulsos sem contexto, impressão incerta, cadastro incompleto e possíveis duplicidades | Exemplos confirmados pela operação; nenhuma fusão por nome isolado |
| 2 | Ampliar cobertura por lotes incrementais, com cursor persistido, sem varrer todo o catálogo em uma abertura | Testes de retomada, limites, índices e cobertura de itens fora das 24 horas |
| 3 | Medir consultas mais usadas e remover gargalos reais | p50/p95 e planos de consulta em dados isolados; sem gravar termos de busca ou dados pessoais |
| 4 | Reduzir passos nos cadastros/grades e sugerir padrões frequentes | Fluxos reais revisados, prévia editável e comparação de tempo de execução |
| 5 | Melhorar classificação visual e aliases multilíngues com exemplos conferidos | Conjunto de exemplos representativos; medir falsos positivos e preservar decisão manual |

Essas etapas são planejamento, não funções já ativadas. A conferência atual não
aprende automaticamente a alterar a operação nem programa correções sozinha.
Conhecimento novo deve virar uma regra ou uma proposta revisável, com origem,
teste, limite de custo e possibilidade de desativação.

## Critérios de publicação

Trabalhar em branch `codex/`, documentar o módulo, validar caminhos autorizados e
negados, testar banco isolado e UI responsiva. Toda publicação passa por PR e pelos
checks protegidos antes do deploy automático. Depois, conferir revisão publicada,
assets, saúde e erros de inicialização. Som/push e impressão física precisam de
validação no aparelho real; testes não disparam vendas, pagamentos ou impressões
operacionais para fingir essa comprovação.

Referências da implementação: [Notificações](NOTIFICACOES.md),
[Conferência diária](QUALIDADE_SISTEMA.md), [Arquitetura](ARQUITETURA.md) e
[Operação](OPERACAO.md).
