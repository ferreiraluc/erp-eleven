# Acesso individual e auditoria

## Contas e vendas pessoais

Lucas (`lucas@eleven.com`) é o único administrador. Wissam tem acesso às vendas
da loja. Denis, Sol e Junior têm acesso operacional aos módulos, mas consultam
somente suas próprias vendas. A tela de usuários, disponível para Lucas, permite
cadastrar contas, ativar/desativar, alterar vínculos e redefinir senha temporária.

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

Somente Lucas acessa `/auditoria` e `/api/access/audit`. O painel combina:

- Login, falhas, logout, mudanças de senha e permissões.
- Operações confirmadas de criação/alteração/exclusão, vinculadas ao usuário e ao canal.
- Filtros por período, usuário, módulo e ação, resumo de eventos por usuário e exportação da página.
- Exclusão definitiva de produtos sem vínculo, exclusiva do Lucas, com identificação
  da peça e quantidade de movimentações removidas.

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
