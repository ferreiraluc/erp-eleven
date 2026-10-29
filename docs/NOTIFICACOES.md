# Notificações da Eleven

## Uso por aparelho

O sino fica somente no menu inicial/dashboard, à direita do cabeçalho. Abre um
balão com mensagens pessoais, pendências, confirmação de leitura e respostas,
sem sair da tela. No celular ocupa cerca de 70% da largura, ancorado no canto
direito; no desktop tem limite de 440 px. A lista tem rolagem e carrega mais
mensagens quando solicitado. O balão também dá acesso ao histórico.
**Notificações** (`/notificacoes`) continua sendo a central completa e o destino
de abertura do push externo. Ler e responder no ERP funciona mesmo quando o
aparelho não permite notificações externas.

Na próxima abertura autenticada de cada aparelho, aparece o convite **Ativar
notificações**, quando ainda não existe autorização. O usuário precisa tocar
nesse botão e aceitar a permissão do navegador. Fechar o aviso oculta apenas o
convite da sessão atual; não desliga notificações nem grava uma preferência no aparelho. O ERP não
pode aceitar a permissão por ninguém nem desfazer uma recusa nas configurações
do navegador. Contas com senha temporária precisam primeiro concluir a troca.

As categorias, o envio externo e o som são habilitados por padrão para todas as
contas pela política da empresa. Não existe mais o painel de preferências por
aparelho, seleção de categorias ou botão de desativação no ERP. Preferências
antigas são preservadas no histórico, mas não desabilitam os avisos da política
atual. Isso não concede uma permissão que o sistema operacional recusou.

Com permissão já concedida, abrir, entrar novamente ou retomar a conexão tenta
revalidar a inscrição automaticamente, com limite de tentativas por intervalo.
Sair remove o vínculo ativo e fecha avisos desse login; uma indicação local de
propriedade permite reutilizar a inscrição nativa no próximo login da mesma
conta. Outra conta exige novo vínculo. Quando o navegador perde uma inscrição
ou exige um gesto para recriá-la, o ERP mostra o botão de ativação; não pede de
novo uma permissão que ainda está concedida.

No iPhone/iPad, instalar o ERP em **Adicionar à Tela de Início** e abrir por esse
ícone; Web Push requer iOS/iPadOS 16.4 ou superior. Android, Samsung Internet e
desktop dependem de suporte do navegador, HTTPS e permissão do sistema. Navegação
privada, economia de energia, restrições corporativas ou bloqueio de notificações
podem impedir a entrega. Cada instalação deve ser ativada separadamente.

Depois de ativado, o serviço de push do navegador pode entregar avisos com a
aplicação fechada. Isso não mantém a página rodando continuamente. Som/vibração
externos obedecem ao modo silencioso e às preferências do sistema; o som dentro
do ERP precisa de uma interação anterior e da opção habilitada. Não há promessa
de aviso sonoro em todos os aparelhos.

O aviso externo mostra o título e o texto da notificação, respeitando o limite
do payload e o espaço disponível no celular. O sistema operacional pode ocultar
a prévia na tela bloqueada. O conteúdo completo e as respostas ficam no ERP.
O envio e o clique respeitam o destinatário, o vínculo do aparelho, o acesso
atual ao destino e a validade da sessão. Ao abrir, é necessário estar autenticado.
Sair, trocar de conta, revogar a sessão ou desativar o usuário impede novas
entregas por aquela sessão. A sessão vence às **21h de Brasília**, e mensagens
do push recebidas após seu vencimento são descartadas. Entrar às 21h ou depois
gera uma sessão válida até o próximo dia às 21h. Na atualização inicial, sessões
antigas ficam limitadas ao primeiro corte após a migração, preservando o turno
atual e vencimentos/revogações anteriores. Abrir novamente revalida a conta e
restaura a inscrição quando permitido.
Depois do corte, é necessário entrar novamente para voltar a receber avisos
vinculados à conta. A autorização já concedida no navegador é reaproveitada;
o novo login não deve pedir uma nova permissão nativa.

## Administração por Lucas

Em **Auditoria → Notificações**, Lucas pode:

- Criar, agendar, editar e cancelar mensagens com destinatários, categoria,
  destaque e atalho interno autorizado.
- Pedir confirmação ou uma resposta, inclusive o motivo de uma venda avulsa.
- Conferir leituras, respostas, versão confirmada, histórico de edições e estado
  do envio ao serviço de push.
- Editar modelos e regras de vendas, rastreio, saudações e lembrete diário.

A permissão é verificada no backend pela identidade proprietária existente;
ter apenas o perfil ADMIN não concede essa administração. Usuários consultam
somente as próprias mensagens. Atalhos respeitam os módulos e vendas pessoais
permitidos ao destinatário. Uma resposta confirmada permanece registrada; não
se altera silenciosamente ao editar a mensagem. A confirmação identifica a versão
lida/respondida. Para pedir outra resposta a quem já confirmou, criar novo aviso.
Editar uma mensagem publicada não dispara outro push para a mesma inscrição.

### Avisar a partir de uma venda ou produto

Em **Vendas**, Lucas encontra **Notificar vendedor** tanto na listagem quanto
nos detalhes. O formulário já traz o código da venda e o vendedor como
destinatário; abrir ou cancelar não envia mensagem. Cada produto vinculado nos
detalhes também oferece **Notificar sobre produto**. Antes de enviar, Lucas
confere o texto, o destinatário e o destino: **Venda** ou **Produto de referência**.
O destino Produto abre a ficha de consulta do item no estoque, inclusive quando
ele não está na página ou nos filtros atuais da listagem.

O produto de referência pode ser escolhido no catálogo mesmo em uma venda com
avulsos. Isso apenas orienta a conferência: não vincula a peça à venda, não
converte avulsos em produtos cadastrados e não modifica estoque ou valores.
Itens excluídos ou inativos não podem ser escolhidos como nova referência.
Na administração central, é possível buscar uma venda por código e reutilizar
o mesmo fluxo, sem copiar o endereço da página.

Modelos manuais mostram uma prévia com os campos preenchidos. `{user_name}` usa
o vendedor da venda vinculada ou o nome do único destinatário (com vários,
“equipe”); `{sale_code}` exige escolher uma venda. `{date}` e `{time}` usam
Brasília. O servidor resolve e valida novamente os campos antes de salvar.
Em rastreios, `{cliente_username}` representa o nome do destinatário do pacote;
`{tracking_code}` e `{status}` usam aquele rastreio. Nas mensagens manuais, escolha
**Rastreamento** como destino e informe um código cadastrado para conferir a
prévia. Na regra automática, os valores são preenchidos no evento. O nome do
pacote é prioritário; somente quando ausente entram vínculos explícitos de pedido
ou cliente. Sem um nome disponível, aparece **destinatário não informado**.
Não há inferência por nomes parecidos nem preenchimento de CPF com zeros.
O modelo inicial intacto passa a incluir o destinatário; modelos personalizados
por Lucas permanecem como foram salvos e podem usar a nova variável.
Variáveis que precisam de um contexto ausente impedem o envio com uma explicação,
em vez de entregar os códigos literais. Mensagens antigas com campos sem preencher
ganham uma apresentação legível; quando não existe vínculo suficiente, o sistema
informa que a venda não foi vinculada e preserva o histórico original.

As permissões da venda são conferidas também ao listar, ler, responder e entregar
o push. Trocar o escopo de vendas de uma conta não permite que uma mensagem antiga
exponha uma venda que saiu desse escopo. O atalho de produto respeita o acesso
atual ao catálogo.
Avisos antigos com atalhos de venda ambíguos ficam ocultos para contas com vendas
pessoais. Lucas pode escolher novamente a venda na edição para gerar um atalho
válido, preservando as revisões anteriores.

**Aceito pelo serviço de push** não significa entregue fisicamente no telefone.
Leitura e confirmação são registros distintos, realizados no ERP. Não há recibo
universal de entrega do sistema operacional. Após uma interrupção entre envio e
confirmação no servidor, o provedor pode receber uma repetição; identificadores
estáveis reduzem avisos duplicados, sem garantir entrega exatamente uma vez.

## Regras iniciais

| Evento | Destinatários permitidos | Comportamento inicial |
| --- | --- | --- |
| Nova venda do PDV concluída | Lucas | Aviso informativo |
| Nova venda com avulsos e sem observação | Lucas e vendedor daquela venda | Pede motivo e confirmação, sem impedir uma venda legítima |
| Ticket em falha ou envio incerto | Lucas e vendedor daquela venda | Solicita conferir a fila; não reimprime |
| Rastreio existente muda de situação | Lucas e criador do rastreio | Atalho para a consulta |
| Bom dia / boa tarde | Usuários ativos ou seleção de Lucas | 09h / 14h de Brasília, uma vez ao dia |
| Lembrete diário | Usuários configurados | Desligado até configuração |

As regras operacionais podem restringir esses destinatários, nunca ampliar uma
venda para um colega sem relação com ela. O motivo de um avulso fica no recibo da
notificação; não reescreve dados financeiros da venda. Avulso não é tratado como
fraude nem como prova de baixa indevida. Saudações têm janela de 60 minutos após
o horário configurado, evitando mensagens de manhã durante um deploy à noite.
Novas regras não notificam retroativamente vendas ou rastreios históricos.

## Arquitetura e operação

`notification_events` registra listeners transacionais de venda, rastreio e fila
de tickets. Sessões da aplicação optam por esses eventos em `SessionLocal`.
Avisos e destinatários são gravados junto à transação de negócio; rollback,
inclusive de savepoint, não publica vendas desfeitas. Consultar um histórico não
cria mensagens. Não remover a importação dos listeners por ausência de chamadas
diretas no arquivo.

O worker `notification_worker` publica agendamentos e processa uma fila persistida
no PostgreSQL. Possui lotes pequenos, lease para recuperação de processo, tentativas
limitadas, espera progressiva e tratamento de inscrições vencidas (404/410).
Nenhuma conexão com o provedor fica dentro da transação que grava uma venda.
Regras diárias e idempotência persistidas evitam duplicação durante deploys
sobrepostos. A saúde aparece em `/health` como `notification_worker`; uma falha
desse canal é informada sem retirar o restante do ERP de operação.

As chaves VAPID são criadas uma vez, com trava no PostgreSQL, e persistidas no
banco. A chave privada é cifrada com derivação da `SECRET_KEY`; não aparece em
respostas ou logs. Preservar banco e `SECRET_KEY` nos backups. Alterar essa chave
exige planejar também a renovação das inscrições. O registro de aparelhos exige
sessão ativa, vínculo por conta e um segredo do aparelho; endpoints externos são
validados contra provedores de push conhecidos, sem redirects arbitrários.

O frontend consulta a caixa somente com sessão válida, janela visível e conexão,
descartando respostas de contas anteriores. `notifications-sw.js` recebe push e
abre o destino interno autorizado; não intercepta requisições nem mantém cache de HTML, JS ou APIs.
Publicar esse arquivo como JavaScript e com `Cache-Control: no-store`, sem
redirecioná-lo ao HTML. Não inserir chaves privadas em `VITE_*`.

As tabelas e revisões novas são aditivas. Não apagam históricos operacionais.
Leituras, polling e tentativas de push não poluem a auditoria genérica; criação,
edição, cancelamento e configuração feitos por Lucas têm auditoria explícita,
sem registrar o texto da mensagem nos logs de auditoria.

## Verificação sem avisar funcionários

Os testes usam contas sintéticas, banco SQLite e schemas isolados em PostgreSQL,
provedor simulado e nenhuma inscrição real. Cobrem permissões, concorrência,
agendamento, rollback, edição, autenticação, fila, isolamento de aparelhos e
eventos de negócio. Conferência visual usa a interface com dados locais.
Validação física de som/push depende de aceitar a permissão no aparelho real;
nunca enviar uma venda, impressão ou alerta real somente para testar a interface.

### Valor no aviso de venda concluída

O modelo padrão passa a **Venda U$ {sale_total} concluída**, com o nome do vendedor
no texto (`{user_name}`) e o mesmo atalho para a venda. `{sale_total}` é o total
**das mercadorias em dólares**, calculado com a cotação congelada da venda,
formatado sem centavos quando inteiro (ex.: `800`, ou `800,50`). Não usa a cotação
atual nem acrescenta ressarcimento de cartão. Sem evidência de cotação, exibe `—`.
A variável também funciona em modelos manuais com uma venda real vinculada e na
prévia. Somente o modelo original intocado é atualizado automaticamente; edições
de Lucas e notificações já enviadas permanecem preservadas.
