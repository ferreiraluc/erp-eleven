# Acesso individual e auditoria

## Contas e vendas pessoais

Lucas (`lucas@eleven.com`) é o único administrador. Wissam tem acesso às vendas
da loja. Denis, Sol e Junior têm acesso operacional aos módulos, mas consultam
somente suas próprias vendas. A tela de usuários, disponível para Lucas, permite
cadastrar contas, ativar/desativar, alterar vínculos e redefinir senha temporária.

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

O frontend não confia no usuário salvo no navegador. Verifica `/api/auth/me` antes
de abrir telas privadas e novamente ao retomar a janela. Token antigo, expirado,
revogado ou de conta desativada leva ao login; falha de rede permite tentar de novo.
Respostas privadas usam `Cache-Control: no-store, private`.

O JWT identifica usuário, sessão e versão de autenticação. `auth_sessions` permite
revogar sessões sem esperar a expiração do token. Logout revoga a sessão atual;
troca/redefinição de senha e alteração de acesso revogam as sessões anteriores.
Ao entrar com outra conta, o frontend reinicia para descartar estados em memória.
O PDV também limpa carrinho, cliente e resultados ao mudar usuário, sessão ou
escopo; respostas pendentes da identidade anterior são descartadas. Retomar a
mesma sessão verificada preserva o carrinho em uso.

Senhas temporárias exigem troca na tela **Minha conta** antes de usar os módulos.
A troca pede a senha atual, confirmação da nova e aplica limite de 6–72 bytes.
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

## Eventos e tempo de atividade

Somente Lucas acessa `/auditoria` e `/api/access/audit`. O painel combina:

- Login, falhas, logout, mudanças de senha e permissões.
- Operações confirmadas de criação/alteração/exclusão, vinculadas ao usuário e ao canal.
- Acessos HTTP autenticados com rota, resultado e referência da requisição.
- Tempo ativo estimado por usuário e módulo, filtros de período e exportação da página.

Mutações ORM são registradas na mesma transação; rollback não vira alteração
concluída. Atualizações em lote registram quantidade afetada. Valores sensíveis,
senha, conteúdo de mensagens, CPF, endereços e PDFs não são copiados ao log de
auditoria; campos privados aparecem somente como alterados. Eventos de requisição
podem aparecer ao lado de sua mutação: são evidências diferentes, não duas edições.

O tempo usa pequenos intervalos enquanto a página está visível, com foco e interação
recente. Intervalos longos sem conexão não geram crédito. Abas simultâneas compartilham
um limite por sessão. É uma estimativa de uso, não comprovação de jornada de trabalho;
navegadores/dispositivos com sessões diferentes podem se sobrepor. Não há captura de
tela, teclas digitadas nem conteúdo do campo para esse cálculo.

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
