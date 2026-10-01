# Evolução noturna — 30/09/2026

Registro de continuidade do trabalho autorizado pelo responsável. Atualizado às
00h02 de Brasília de 01/10/2026. **Publicação concluída** no commit
`78a9ea98918ddbe3220d53354c90498f9a96be79`. Frontend e backend confirmados Live
no Render; CI GitHub concluída com sucesso.

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

Implementação e validação concluídas; publicação em preparação:

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
