# Evolução noturna — 30/09/2026

Registro de continuidade do trabalho autorizado pelo responsável. Atualizado às
01h22 de Brasília de 01/10/2026. **Última publicação concluída** no commit
`eab8b677a0e9970e756573c3726982e89915ce4f` (rodada de saldos ausentes abaixo).
A primeira rodada foi publicada em `78a9ea98918ddbe3220d53354c90498f9a96be79`.
Frontend e backend confirmados Live no Render; CI GitHub concluída com sucesso.

## Implementação desta rodada

- Sessões verificadas, troca de senha, cinco contas com provisionamento idempotente,
  vendas pessoais no backend e auditoria exclusiva de Lucas.
- Comprovante postal por foto no Telegram, prévia confirmada e código validado.
- Vínculos explícitos entre clientes, pedidos e múltiplos pacotes; entrega parcial.
- Lançamentos individuais do Excel, visão diária e horários quando existirem na origem.
- Consulta do BI Excel pelo bot, com as mesmas permissões pessoais, sem iniciar sync.
- Geração/importação de pessoa do 4Devs com edição e aprovação exclusiva de Lucas.
- Traduções PT/ES/EN nos módulos e formulários, preservando dados e enums da API.
- OCR revisável de etiquetas e proteção de saldos contra saídas concorrentes.
- Visão DeepSeek com a chave existente; Anthropic permanece como opção configurável.

## Evidências de validação

- **341 testes Python passaram**, incluindo PostgreSQL isolado: migrações, concorrência
  de estoque/rastreios, atualizações externas antigas e crédito de atividade entre abas.
- **52 testes frontend passaram**; tipagem TypeScript e build de produção concluídos.
- Revisão visual local: login, sessão revogada, conta temporária, BI pessoal, auditoria,
  usuários, idiomas e gerador de remetentes. Build com navegação hash também conferido.
- Formulário real 4Devs retornou pessoa completa, sem salvar cadastro.
- DeepSeek real reconheceu rastreio/destinatário de imagem sintética, sem gravação
  no banco ou envio ao Telegram. A revisão humana das fotos continua necessária.
- Backup privado local anterior ao deploy concluído; catálogo conferido com pg_restore.

Nenhuma compra, impressão física ou mensagem real foi usada para testar a interface.
As migrações `z6a7b8c9d0e1` e `a7b8c9d0e1f2` foram aplicadas pelo Render.
API, banco, assistente e recuperação de etiquetas reportam online em `/health`.

As contas Lucas/Wissam/Denis/Sol/Junior foram provisionadas preservando os IDs.
Login, escopo, exigência de troca de senha, logout e revogação foram conferidos nas
cinco contas. A segunda simulação de provisionamento não propôs alterações ou
redefinições. **Não executar novamente para redefinir senhas pessoais.** Usuários
inativos anteriores permaneceram inativos. Auditoria passa a registrar a partir
desta versão, sem atribuir retroativamente operações antigas.

O novo detalhamento das planilhas será preenchido na próxima sincronização manual
ou diária às 18h. Não foi iniciada sincronização extra; correções nas células seguem
sendo consumidas pelos resultados salvos. Ausência de hora real não vira intraday
artificial. A geração de pessoa usa o formulário público 4Devs e mantém importação
JSON como alternativa; somente Lucas pode aprovar o cadastro.

## Continuidade

Os três agentes concluíram suas frentes; integração e publicação verificadas.
Não repetir o trabalho concluído nem provisionar senhas novamente. Na continuidade,
priorizar melhorias pequenas fundamentadas em evidências: diagnóstico de saldos e
códigos duplicados no estoque, clareza de erros recuperáveis e revisão de fluxos de
bot com testes isolados. Não corrigir automaticamente saldos reais nem inventar
registros, horários ou vínculos. Cada nova mudança deve ter escopo delimitado,
testes pertinentes e sua própria verificação de publicação.
A continuação agendada desta tarefa está ativa até 8h de Brasília de 01/10/2026;
depende do laptop ligado e do aplicativo disponível. Preservar dados e segredos,
notificar somente entregas, falhas ou questões que precisem do responsável.

## Rodada iniciada às 00h04 — estoque

Implementação, validação e publicação concluídas:

- **Estoque → Conferir estoque** mostra divergências entre total/locais, saldos
  ausentes/negativos e códigos compartilhados, com busca, filtros e paginação.
  A consulta só ocorre ao abrir o painel; não altera saldos nem funde cadastros.
- Contagens exigem local explícito e revisão. Aplicação única, locks ordenados,
  referência atualizada na recontagem e bloqueio quando houve movimentação no
  local após a leitura impedem duplicação e sobrescrita de estoque.
- Códigos repetidos no mesmo lote de novos produtos do bot são rejeitados.
- Falhas da listagem exibem aviso com nova tentativa, sem indicar estoque vazio.
- Migração aditiva `b8c9d0e1f2a3`: preserva sessões antigas sem inferir o local.

**383 testes Python e 66 testes frontend passaram**, com TypeScript e build de
produção concluídos. PostgreSQL isolado comprovou migração, concorrência de
leitura/aplicação, cancelamento durante espera e preservação de saídas concorrentes.
Revisão visual local confirmou painel, idiomas, filtros, valores ausentes e falha
recuperável. Nenhum saldo de produção foi consultado ou corrigido para esses testes.

Limitação conhecida: a listagem/editor geral ainda não suporta todos os saldos
nulos legados. O diagnóstico mostra os valores ausentes e o erro de abertura é
recuperável; reparar esse contrato exige uma mudança específica, sem converter
silenciosamente ausência em zero. Não existe tela de sessões de contagem; esta
rodada corrige os endpoints existentes e seu wrapper.

Publicação confirmada às 00h24: frontend e backend no commit
`b546b7563d50e684ca0e88e4bd2805be30e97acf`, com
[CI concluída](https://github.com/ferreiraluc/erp-eleven/actions/runs/36810147323).
O Render executou a migração, e a consulta técnica de `alembic_version` confirmou
`b8c9d0e1f2a3`. API, banco, assistente e worker de etiquetas reportam online.
Backup privado anterior à migração: 7.105.884 bytes, permissões 0600 e catálogo
validado. Servidores locais de QA encerrados após a revisão; nenhum print, compra,
mensagem, sincronização de BI ou redefinição de senha foi feito nesta rodada.

Na próxima continuação, não refazer estas entregas. Investigar o contrato de saldos
nulos usando somente fixtures isoladas, antes de propor correção explícita; manter
a distinção entre zero conhecido e valor ausente. Demais melhorias devem partir
de falhas reproduzíveis, mantendo confirmações do produto e histórico operacional.

## Rodada iniciada às 01h04 — saldos ausentes

Implementação, validação e publicação concluídas. Reprodução isolada confirmou falha de
listagem/edição ao retornar NULL, soma parcial apresentada como total no bot e
baixa/devolução do PDV tratando local ausente como zero. Divisão: receipt_tracking
cuida da API/serviço de estoque; customer_links do frontend e consumidores dos
tipos; sales_intraday do bloqueio transacional no PDV; root da consulta do bot,
documentação, integração e validação visual.

Escopo: permitir leitura e edição de metadados com saldos desconhecidos, exibir
ausência explicitamente, preservar totais incompletos e bloquear movimentações que
pressupõem quantidade conhecida. Sem reparo automático, migração, compra, impressão
ou consulta de estoque de produção. Os 29 testes de consultas do bot passaram.

A suíte completa passou com **429 testes backend e 82 testes frontend**, incluindo
os novos cenários de PostgreSQL isolado. TypeScript e build de produção aprovados.
Lista e editor abriram no QA local com total/loja ausentes, depósito zero e um
produto com saldo zero conhecido; filtro e bloqueios da lista confirmados.
A edição de descrição pela interface foi conferida na base isolada: saldos
permaneceram NULL, NULL e zero. PT/ES e busca do PDV revisados visualmente; a busca
mostra saldo ausente e impede inclusão no carrinho, sem concluir venda/pagamento.

Sem mudança de esquema: a revisão Alembic permanece `b8c9d0e1f2a3`. A restauração
de quantidades ausentes continua exigindo procedimento explícito e auditado; esta
rodada não infere valores. Os bloqueios de NULL não substituem uma revisão das
demais regras legadas do PDV (baixa direta, quantidade fracionária/insuficiente e
fluxo financeiro); isso permanece como próximo escopo a reproduzir em testes.

Publicação confirmada às 01h22: frontend e backend no commit
`eab8b677a0e9970e756573c3726982e89915ce4f`, ambos com deploy concluído no Render,
[CI aprovada](https://github.com/ferreiraluc/erp-eleven/actions/runs/36814577531)
e `/health` com API, banco, assistente e worker de etiquetas online. Servidores
locais de QA encerrados e abas temporárias removidas. Nenhuma impressão, mensagem,
compra, sincronização de planilhas, senha ou saldo real foi usado para validar.

Esta rodada resolveu a compatibilidade de leitura de NULL registrada às 00h24;
não repetir esse trabalho na próxima execução. Permanece pendente somente um fluxo
específico para restaurar quantidades ausentes, caso necessário. Não provisionar
senhas novamente; continuar preservando as confirmações e o histórico.
