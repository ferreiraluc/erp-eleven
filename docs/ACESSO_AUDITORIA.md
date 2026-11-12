# Acesso individual e auditoria

## Contas e vendas pessoais

Lucas (`lucas@eleven.com`) é o único administrador. Wissam tem acesso às vendas
da loja. Denis, Sol e Junior têm acesso operacional aos módulos, mas consultam
somente suas próprias vendas. A tela de usuários, disponível para Lucas, permite
cadastrar contas, ativar/desativar, alterar vínculos e redefinir senha temporária.

O perfil **Revendedor — somente consulta** (`access_profile=reseller`) mantém
catálogo, quantidades da loja e depósito, detalhes/fotos, fornecedores e câmbio
disponíveis para consulta. Formulários de produto e movimentação podem ser vistos,
mas não salvam alterações. Cadastro, baixa, transferência, agrupamento, impressão,
histórico do produto e demais módulos são negados também pelo servidor.
Esse perfil não precisa de vínculo com vendedor ou planilha; usa `VENDEDOR` e
escopo pessoal internamente, sem conceder acesso ao PDV. Notificações de vendas
não equivalem a permissão para abrir os detalhes da venda.

Lucas escolhe o perfil no cadastro de usuários. Alterações revogam as sessões
anteriores; uma versão antiga do painel que omita o campo não transforma uma
conta restrita em operacional. O administrador principal permanece no perfil
padrão. Contas existentes recebem `standard` pela migração aditiva, preservando
IDs, senhas, vínculos e permissões anteriores. O bot não aceita identidades
associadas a revendedores, inclusive trabalhos pendentes de impressão originados
no bot. A política da API usa uma lista explícita de métodos e rotas permitidos;
novos endpoints não ficam automaticamente acessíveis ao perfil restrito.

No dashboard, Minha conta, Usuários, Auditoria e Sair ficam no cabeçalho original,
com o título “ERP Eleven, NOME” do usuário conectado. Moeda, idioma com bandeira
e cotações ocupam uma linha compacta, tanto no celular quanto no desktop.
Até 600px, os quatro acessos da conta permanecem em uma única linha, sem os
ícones decorativos, para evitar que Sair crie uma linha extra. O cabeçalho usa
espaçamentos menores no celular; os nomes e permissões dos acessos são preservados.
As demais telas mantêm a barra de navegação no desktop. Em telas de até 768px,
a barra global fica apenas no dashboard, liberando espaço para as ferramentas
dos módulos; o botão de voltar de cada módulo leva ao dashboard.
Usuários e Auditoria aparecem somente para Lucas. O comportamento da sessão e as
permissões continuam iguais em ambos os lugares.

O vínculo de uma conta tem dois identificadores financeiros: `vendedor_id` para
vendas operacionais e `sales_seller` para o nome canônico do vendedor no Excel.
O PDV usa o próprio ID do usuário como vendedor. Sem vínculo suficiente, consultas
pessoais são negadas ou vazias; nunca retornam o total da loja como alternativa.

O backend aplica os filtros **antes** de somar, paginar, comparar ou formar rankings.
Isso vale para o BI, seus lançamentos individuais, vendas operacionais, dashboard,
PDV e consultas financeiras do bot. Funcionários não acessam fontes/configurações
do BI, importação geral ou valores de fiado de outros vendedores. Lucas e Wissam
continuam podendo consultar as vendas gerais; administração permanece exclusiva
de Lucas.

## Sessão e senha

O login não contém links externos de rastreamento. E-mail/senha têm limites no
cliente e no servidor; a senha nunca é truncada nem incluída nas respostas de
validação. A consulta usa parâmetros SQLAlchemy e o bcrypt também é executado
quando a conta não existe, reduzindo diferenças de tempo que revelam cadastros.
Erros de credenciais são genéricos. Tentativas são limitadas por par conta/IP,
conta e IP durante dez minutos, com resposta 429 e `Retry-After`.
Os contadores ficam no PostgreSQL e sobrevivem aos deploys: 12 tentativas por par
conta/IP, 30 por conta e 60 por IP em dez minutos. Chaves HMAC ocultam os identificadores;
contadores vencidos há mais de um dia são removidos no próximo login. A cota é
consumida antes do bcrypt, inclusive em logins bem-sucedidos, e não é reiniciada
por sucesso. Isso evita que outra instância ou um deploy zere a proteção.
Um bloqueio afeta temporariamente usuários da mesma rede; não é um bloqueio permanente.

O frontend publica CSP (`frame-ancestors`, `form-action`, `base-uri`, `object-src`,
`script-src` e `worker-src`) e HSTS por um ano, além de
`X-Frame-Options: DENY`, `nosniff` e `Referrer-Policy: no-referrer`, configurados no
Render e em `render.yaml`. O servidor Node opcional aplica as mesmas regras.
Isso impede enquadrar o ERP em sites terceiros e limita formulários/navegação base,
mas não impede que alguém crie uma cópia visual em outro domínio. Não há passkeys
nem MFA nesta versão; a sessão continua usando o mecanismo de tokens existente.
Referências: [autenticação OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html),
[SQL parametrizado](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
e [defesa contra clickjacking](https://cheatsheetseries.owasp.org/cheatsheets/Clickjacking_Defense_Cheat_Sheet.html).

O frontend não confia no usuário salvo no navegador. Verifica `/api/auth/me` antes
de abrir telas privadas e novamente ao retomar a janela. Token antigo, expirado,
revogado ou de conta desativada leva ao login; falha de rede permite tentar de novo.
Respostas privadas usam `Cache-Control: no-store, private`.

O JWT usa PyJWT com HS256 fixo e exige `exp`, `iat`, `sub`, `sid` e `ver`.
Identifica usuário, sessão e versão de autenticação. `auth_sessions` permite
revogar sessões sem esperar a expiração do token. Logout revoga a sessão atual;
troca/redefinição de senha e alteração de acesso revogam as sessões anteriores.

**Todas as contas encerram a sessão diariamente às 21h de Brasília**
(`America/Sao_Paulo`). Um login feito às 21h ou depois vence às 21h do dia
seguinte. Marcar para lembrar o login não prolonga esse prazo. O servidor aplica
a expiração em cada requisição e informa o limite efetivo em
`/api/auth/me.session_expires_at`; o aplicativo aberto agenda a saída e confere
novamente ao retomar a janela, inclusive quando o celular suspendeu os timers.
Não é necessário um processo agendado para invalidar o token.

A migração aditiva `r0a1b2c3d4e5` conserva usuários, tokens assinados, datas
originais de expiração e revogações. Sessões antigas recebem
`auth_sessions.daily_expires_at` com a primeira ocorrência de 21h após a
ativação, evitando encerrar o expediente no meio do deploy. Novas sessões e
tokens já usam esse limite diário. `effective_session_expiry` considera sempre
o menor prazo; a mesma regra limita entregas de push vinculadas à sessão.
O frontend guarda o prazo verificado junto à identidade exata do token, sem
aceitar respostas atrasadas de outra conta para prolongar ou encerrar a sessão.

Ao entrar com outra conta, o frontend reinicia para descartar estados em memória.
O PDV também limpa carrinho, cliente e resultados ao mudar usuário, sessão ou
escopo; respostas pendentes da identidade anterior são descartadas. Retomar a
mesma sessão verificada preserva o carrinho em uso.

Requisições de autenticação pertencem à sessão que as iniciou. Respostas atrasadas
de login, troca de senha, logout ou verificação não podem restaurar uma conta
encerrada, substituir uma conta nova nem alterar seu erro ou navegação. O logout
encerra a sessão local imediatamente e solicita a revogação do token original.
Erros de autenticação de uma sessão antiga também não redirecionam a nova conta.
Se a validação falhar por conexão em uma tela privada, o estado recuperável permite
validar novamente ou sair. Após uma troca de senha já confirmada pelo servidor,
essa nova tentativa consulta a sessão; não repete a alteração de senha.

Senhas temporárias exigem troca na tela **Minha conta** antes de usar os módulos.
A troca pede a senha atual e confirmação da nova: mínimo de 6 caracteres e máximo
de 72 bytes UTF-8, recusando repetições triviais e alguns padrões óbvios. Senhas
antigas continuam funcionando até a troca; a atualização não redefine contas.
O sistema não armazena senhas em texto; usa bcrypt. Não há envio de recuperação
por e-mail: Lucas fornece outra senha temporária pelo painel.

Para migrar as cinco contas da loja sem perder IDs/vínculos do bot, existe a CLI:

```sh
cd backend
python -m app.user_access_setup          # simula, sem gravar
python -m app.user_access_setup --apply  # solicita a senha inicial sem exibi-la
```

Execute somente após a migração de acesso e na base intencionalmente escolhida.
A CLI reconhece as identidades legadas conhecidas, exige vendedor inequívoco e
preserva senhas individuais nas reexecuções. Não contém senha padrão no código.

## Eventos de auditoria

Lucas também administra **Notificações** dentro da Auditoria. Mensagens pessoais,
respostas, regras e modelos têm validação de acesso no servidor. A ativação no
celular exige consentimento por aparelho; o sino abre a caixa pessoal para todas
as contas. Leituras e tentativas de push ficam fora do log genérico; alterações
administrativas geram eventos explícitos, sem copiar o corpo da mensagem.
Detalhes: [Notificações](NOTIFICACOES.md).

Somente Lucas acessa `/auditoria`, `/api/access/audit` e seus detalhes de operação. O painel combina:

- Login, falhas, logout, mudanças de senha e permissões.
- Operações confirmadas de criação/alteração/exclusão, vinculadas ao usuário e ao canal.
- Filtros por período, usuário, módulo e ação, resumo de operações por usuário e exportação da página.
- Exclusão definitiva de produtos sem vínculo, exclusiva do Lucas, com identificação
  da peça e quantidade de movimentações removidas.

O histórico abre como **cards de operações**. Cada venda do PDV reúne seus registros
de criação, edição, itens, pagamentos, devoluções e estoque associado. O botão
**Abrir venda** leva à venda correspondente; os registros ficam expansíveis no
próprio card. Vendas operacionais e BI não são tratados como vendas do PDV.
Outras alterações são agrupadas pelo identificador exato da requisição confirmada,
por exemplo uma transferência em lote. Eventos sem esse identificador ficam
individuais. Horário próximo, nome do usuário ou semelhança entre valores nunca
são usados para adivinhar uma associação.

As movimentações identificam o produto, quem confirmou, entrada, saída ou
transferência, quantidade e locais conhecidos. Mostram os saldos anteriores e
posteriores da loja e do depósito quando esses fatos foram registrados. Históricos
antigos sem saldo por local mostram somente o saldo total conhecido. Exclusão de
um registro histórico é identificada como exclusão, não como uma nova saída física.
Datas e horas usam o horário de Brasília (`America/Sao_Paulo`).

Os títulos descrevem o acontecimento: **Alteração de nome do cliente**,
**Cadastro de produto**, **Cadastro de cliente**, **Entrada de estoque**,
**Saída de estoque**, **Transferência de estoque** e **Login**.
Campos técnicos, como `updated_at`, não transformam uma alteração de nome em
um título genérico. O responsável e o horário ficam logo abaixo; referências,
IDs e alterações individuais permanecem nos detalhes expansíveis. O card não
repete a mesma descrição em uma prévia quando há somente um registro.

Novos registros de vendas do PDV guardam o vendedor da venda, total em guaranis,
câmbio congelado e situação em `_context.sale`. O título usa esse vendedor e
o valor em dólares calculado com o câmbio da própria venda; o responsável pela
ação continua separado. Um operador editando a venda de outra pessoa não se
torna seu vendedor. Sem câmbio registrado, o histórico exibe G$, sem converter
pela cotação atual. Cancelamentos, devoluções e alterações preservam suas ações;
o total original da venda não é apresentado como valor de reembolso.
Vendas operacionais usam `_context.operational_sale`, com vendedor, valor bruto
e moeda próprios. Reservas, condicionais e pagamentos de pedidos continuam
distintos de vendas concluídas.

As descrições também aproveitam registros antigos, sem regravá-los. Se o log
antigo guardou apenas que `nome` mudou, é possível mostrar **Alteração de nome do
cliente**, mas não recuperar os nomes anterior e posterior. O sistema não busca
valores atuais do cadastro para apresentá-los como fatos históricos.

O servidor aplica os filtros **antes de agrupar e paginar**; os detalhes usam os
mesmos filtros. Por isso um filtro por usuário ou estoque mostra somente os
registros correspondentes dentro da venda, e o total do card reflete esse recorte.
A lista carrega até três exemplos por operação. Os demais registros são buscados
apenas ao abrir o card, com paginação independente; uma venda grande não desaparece
nem se divide artificialmente entre páginas de operações. O resumo de cada usuário
conta operações distintas, com logins em coluna separada. A exportação contém os
grupos da página atual.

Cada grupo inclui ainda um `summary_event` representativo, limitado a um registro,
independente dos três exemplos. Assim, uma venda com muitos movimentos não perde
seu valor/vendedor e o estoque inicial de um produto não esconde seu cadastro.
`entity_count`, `action_count`, `module_count` e `movement_kind` consideram todos
os eventos abrangidos pelos filtros. Um lote misto não é descrito como transferência
só porque seus três exemplos são transferências. Não há uma consulta por card;
os registros retornados continuam limitados por página.

`/api/access/audit?grouped=true` habilita a leitura agrupada e
`/api/access/audit/group` pagina os registros de um grupo. Sem `grouped`, a API
mantém o contrato anterior de eventos individuais. Não há migração nem alteração
dos registros antigos. Novos eventos guardam referências estruturais seguras da
venda e do produto; eventos antigos só são associados quando há uma venda única
explicitamente identificada na mesma requisição. Essas referências sobrevivem à
exclusão das linhas operacionais e não copiam documentos, endereços, fotos ou textos
privados. Um histórico legado sem vínculo suficiente continua separado.

Mutações ORM são registradas na mesma transação; rollback não vira alteração
concluída. Atualizações em lote registram quantidade afetada. Valores sensíveis,
senha, conteúdo de mensagens, CPF, endereços e PDFs não são copiados ao log de
auditoria; campos privados aparecem somente como alterados. Consultas HTTP e eventos
genéricos de requisição (`read`/`request`) não são mais gravados na auditoria.

O acompanhamento de navegação e tempo por módulo foi desligado. O frontend não
envia intervalos de atividade; `/api/access/activity` aceita chamadas de clientes
antigos com `tracking_enabled=false`, sem gravar intervalos ou alterar sessões.
Os eventos de consulta e tempos antigos são preservados no banco, mas não entram
na listagem, totais ou exportação da auditoria. A última atividade mostrada é a
data do último evento relevante, não uma estimativa de presença. Não há coleta de
telas ou teclas digitadas. Logs técnicos do servidor seguem separados do painel.

A auditoria começa a partir da ativação desta versão. Não reconstrói ações antigas
sem evidência nem atribui rotinas automáticas a um funcionário. SQL administrativo
externo ao aplicativo e alterações feitas diretamente nas planilhas não entram
como ações individuais do ERP.

## Contexto do assistente

Conversas continuam limitadas ao autor, canal e conversa. Quando o acesso financeiro
é restringido, o bot não reutiliza respostas anteriores à mudança de permissão.
A memória livre de contas com acesso pessoal fica limitada a relatos confirmados
do próprio autor posteriores à restrição. Dados atuais sempre vêm das ferramentas
que aplicam a mesma autorização do site.

## Validação

`test_access.py`, `test_assistant_access.py` e `test_access_postgres.py` verificam
sessões, permissões, dados financeiros, provisionamento, auditoria transacional,
migrações e concorrência entre abas. Testes frontend verificam sessão expirada,
respostas atrasadas de outra conta e troca de senha durante validação em segundo plano.
`authConcurrency.test.ts` e `authRequests.test.ts` exercitam respostas fora de ordem
e a associação da requisição ao token original, sem consultar contas reais.
`test_audit_groups.py`, `test_audit_groups_postgres.py`, `AuditOperationCard.test.ts`
e `auditPresentation.test.ts` verificam agrupamento e paginação, filtros, isolamento
de permissão, referências históricas, rollback, saldos, detalhes sob demanda e
recuperação após falha de rede. A consulta de agrupamento é validada também em
PostgreSQL isolado, incluindo extração JSON e identificadores UUID.
`test_audit_sale_context.py` e `test_audit_sale_context_postgres.py` verificam
vendedor diferente do operador, valores zerados, captura em lotes, campos privados,
câmbio histórico e rollback, sem depender de vendas reais.
`test_daily_sessions.py`, `test_daily_sessions_postgres.py`,
`authDailyExpiry.test.ts` e `sessionStorage.test.ts` cobrem a virada das 21h,
logins após o fechamento, atualização de sessões legadas em PostgreSQL isolado,
aplicativo aberto, retomada após suspensão e isolamento de respostas antigas.

## Domínio próprio

O frontend atende `https://elevenparispy.com`; `www.elevenparispy.com` redireciona
para o domínio principal no Render. Ambos constam na lista exata de origens CORS
permitidas em `app/main.py`. `VITE_API_BASE_URL` continua apontando para a API do Render.
Adicionar um domínio ao frontend não altera automaticamente a lista do backend.
Não é necessário mudar usuários, senhas ou banco de dados. O armazenamento da sessão
é separado por origem; no primeiro acesso ao domínio novo é necessário entrar novamente.
Não usar `*` ou permitir subdomínios arbitrários para contornar CORS.

## Gestão das vendas do PDV

Somente Lucas edita, exclui, registra devoluções parciais ou estornos integrais
das vendas. A restrição também protege a API antiga de cancelamento. Wissam
pode consultar o geral; Denis, Sol e Junior veem seu próprio escopo e todos
continuam lançando novas vendas. As revisões completas antes/depois e seus
motivos ficam disponíveis exclusivamente para Lucas. Veja [Vendas](VENDAS_PDV.md).
