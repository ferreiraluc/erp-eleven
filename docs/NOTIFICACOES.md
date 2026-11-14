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

| Evento | Destinatários padrão, sem seleção | Comportamento inicial |
| --- | --- | --- |
| Nova venda do PDV concluída | Lucas | Aviso informativo |
| Ticket em falha ou envio incerto | Lucas e vendedor daquela venda | Solicita conferir a fila; não reimprime |
| Rastreio existente muda de situação | Lucas e criador do rastreio | Atalho para a consulta |
| Bom dia / boa tarde | Todos os usuários ativos | 09h / 14h de Brasília, uma vez ao dia |
| Lembrete diário | Todos os usuários ativos | Desligado até configuração |

Vendas com itens avulsos enviam somente o aviso normal de venda concluída, conforme
os destinatários configurados. Não geram mais o alerta automático pedindo motivo.
Avisos antigos, respostas e o modelo para cobranças manuais permanecem disponíveis;
essa mudança não remove histórico nem altera a auditoria da venda.

Ao marcar usuários e salvar uma regra, a seleção **substitui** os destinatários
padrão nos próximos eventos. Lucas precisa estar marcado para continuar recebendo
essa regra quando há uma seleção. Rastreios podem ser enviados aos usuários ativos
selecionados, mesmo quando outra pessoa cadastrou o pacote.

Avisos de venda respeitam o acesso atual de cada selecionado: contas limitadas às
próprias vendas recebem somente eventos das suas vendas; contas com acesso geral
podem receber eventos de todos os vendedores. Selecionar alguém na regra não
amplia permissões de consulta nem expõe valores de uma venda fora do seu escopo.
As mesmas restrições continuam na caixa, na abertura do destino e no envio push.
Usuários inativos não recebem novos avisos. As seleções já salvas são aproveitadas
pelos próximos eventos, sem reenviar notificações antigas.

O perfil **Revendedor — somente consulta** pode ser selecionado na regra de venda
concluída. Recebe um resumo separado: **Venda U$ … concluída** e o nome do vendedor,
sem cliente, pagamentos, detalhes ou atalho para a venda. A caixa e o push usam
esse mesmo resumo; tocar no aviso abre a central de notificações. O modelo interno
personalizado e os atalhos dos funcionários continuam preservados. Outras regras
e mensagens manuais não são destinadas a esse perfil. A seleção não cria acesso
ao PDV e não reenvia vendas anteriores; avisos antigos de um perfil de funcionário
ficam indisponíveis se a conta for convertida para revendedor.
O editor mostra revendedores apenas entre os destinatários da regra **Venda
concluída**; **Selecionar todos** em um recado manual inclui somente a equipe.
Ao editar um recado ou outra regra, destinatários convertidos para revendedor
são retirados da seleção antes de salvar. O backend continua validando o perfil.

O motivo de um avulso fica no recibo da
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

## Aplicativos Android/iOS — piloto nativo

O piloto Capacitor usa FCM no Android e APNs diretamente no iOS, reaproveitando
a caixa, os destinatários, a fila e o worker existentes. O navegador/PWA continua
com Web Push, sem depender de Firebase nem de uma conta Apple para operar.
A migração `d2m3n4o5p6q7` é aditiva: inscrições antigas recebem transporte `web`;
nenhuma inscrição ou entrega histórica é apagada ou reenviada.

**O push nativo começa desligado.** Sem configuração, a caixa interna funciona e
mostra que os avisos externos estão em preparação; o aplicativo não abre pedidos
de permissão repetidos nem tenta registrar um Firebase inexistente. Para ativar
um build de piloto depois da configuração e validação física, são necessários os
dois controles: `VITE_NATIVE_PUSH_ENABLED=true` no build nativo e
`NATIVE_PUSH_ENABLED=true` no backend. O flag `VITE_*` é público e não é segredo.
Não ativar o flag de build Android antes de adicionar sua configuração Firebase.

Ao entrar com o transporte configurado, a faixa **Receba os avisos do ELEVEN**
oferece **Ativar notificações**. O toque pede a permissão do Android/iOS; uma
permissão concedida é reaproveitada nos próximos logins. Recusar não bloqueia o
ERP e não dispara pedidos nativos repetidos. No Android, **Abrir configurações**
leva apenas às notificações do próprio Eleven. Ao voltar, o app revalida a sessão
e reconecta a inscrição sem esperar o próximo polling. O agente consulta também
o bloqueio geral e o canal `eleven-updates`, pois Android anterior ao 13 pode
reportar permissão de runtime concedida mesmo com notificações bloqueadas nos
Ajustes. O app não modifica permissões, Não Perturbe nem economia de bateria.

| Plataforma | Configuração necessária |
| --- | --- |
| Android | Projeto Firebase com Cloud Messaging HTTP v1; `google-services.json` do aplicativo correspondente em `frontend/android/app/` no ambiente de build. O pacote debug usa `com.elevenparispy.erp.pilot`; distribuição usa `com.elevenparispy.erp`, exigindo cadastros correspondentes. |
| FCM no backend | `NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON`: credencial privada de conta de serviço com permissão para enviar mensagens nesse projeto. Nunca incluir esse JSON no aplicativo, `VITE_*`, repositório ou log. Não confundir com `google-services.json`, que contém configuração do aplicativo. |
| iOS | App ID `com.elevenparispy.erp`, capability Push Notifications, perfil de assinatura compatível e chave APNs `.p8` da conta Apple. |
| APNs no backend | `NATIVE_PUSH_APNS_KEY_ID`, `NATIVE_PUSH_APNS_TEAM_ID`, `NATIVE_PUSH_APNS_PRIVATE_KEY` (PEM com quebras de linha), `NATIVE_PUSH_APNS_TOPIC` e `NATIVE_PUSH_APNS_SANDBOX`. Sandbox somente para build/provisionamento de desenvolvimento; TestFlight/distribuição usa produção. Não misturar os ambientes. |

As credenciais são inseridas no ambiente secreto do serviço existente; não há
novo worker ou serviço pago dedicado a push. O backend usa destinos fixos Google
e Apple, TLS, timeout, sem redirects/proxy herdado; APNs usa HTTP/2 e reaproveita
conexão e token do provedor, renovado antes de uma hora. Tokens de instalação
ficam cifrados no banco com a proteção já utilizada pelo Web Push. O registro
usa `GET /api/notifications/push/native/config?platform=android|ios` e
`POST /api/notifications/push/native/subscribe`, sempre autenticados, vinculados
à própria sessão; a API não aceita escolher outro destinatário.

O aplicativo guarda um segredo de instalação no Keychain/Keystore pelo plugin
`ElevenSecureStorage`, além de um vínculo aleatório por sessão. O token de login
não é gravado nesse registro de notificação. A troca de usuário exige um novo
vínculo, descarta resultados assíncronos da conta anterior e não reproduz avisos
antigos. Conhecer um token FCM/APNs não basta para transferir uma inscrição:
é necessário provar o mesmo segredo de instalação. Se o cofre for perdido mas
o provedor mantiver o token, o registro falha de forma explícita, exigindo
reconciliação administrativa; não toma a inscrição de outra instalação.

**No piloto, a notificação do sistema operacional é genérica:** título `ELEVEN`
e texto “Há uma atualização na sua caixa de notificações.” Não contém valores,
clientes, vendedor, descrição, imagem, URL da venda ou dados de rastreio. O SO
pode exibir um aviso já aceito pelo provedor depois de logout/troca de usuário;
por isso não transportamos conteúdo operacional nessa etapa. O payload inclui
somente identificador opaco, vínculo da sessão e vencimento, com TTL máximo de
cinco minutos e nunca posterior ao fim da sessão. O clique valida o vínculo e
abre exclusivamente `/notificacoes`; a caixa busca os detalhes com a sessão e
as permissões atuais. Alertas expirados ou de outra conta não navegam.

No Android, esses avisos visíveis usam prioridade FCM **high**, permitindo ao
provedor tentar a entrega durante o modo Doze. Não é um serviço permanentemente
ativo nem uma sincronização silenciosa. A prioridade não ignora permissão negada,
canal bloqueado, aplicativo forçado a parar, falta de rede ou restrições do aparelho,
e não garante entrega imediata. O TTL permanece limitado a cinco minutos e ao fim
da sessão; avisos vencidos não são recuperados como alertas novos. Validar também
com tela bloqueada/app em segundo plano em um Android real, usando uma notificação
de teste autorizada, sem venda ou impressão. A recomendação segue a
[documentação de prioridade do FCM](https://firebase.google.com/docs/cloud-messaging/android-message-priority),
que reserva prioridade alta para conteúdo visível e pode reduzir a prioridade
quando as mensagens repetidamente não produzem avisos ao usuário.

Revogação, usuário inativo, alteração de perfil e corte das 21h continuam sendo
verificados antes do envio. Logout desativa a inscrição da sessão e limpa avisos
já apresentados no aparelho; o cofre conserva somente a identidade da instalação
para o próximo login. Revendedores continuam restritos ao resumo permitido de
vendas na caixa. Nenhum caminho nativo amplia seu acesso a clientes ou vendas.

Os testes automatizados simulam os provedores e verificam assinatura/protocolo,
rotatividade de token, expiração, troca de conta, logout, payload mínimo e
registro concorrente em PostgreSQL isolado. Não comprovam entrega física,
som, comportamento sob economia de energia nem abertura a partir do aplicativo
encerrado. Antes de ativar para a equipe, validar em iPhone/iPad e Android reais:
aceitar/recusar permissão, retomada do app, troca de conta, corte de sessão e
toque em alerta antigo. Essa etapa depende das contas Apple/Firebase, assinatura
e consentimento no aparelho; nenhuma permissão do SO pode ser imposta pelo ERP.

Referências: [Capacitor Push Notifications](https://capacitorjs.com/docs/apis/push-notifications),
[FCM HTTP v1](https://firebase.google.com/docs/cloud-messaging/send/v1-api) e
[autenticação APNs](https://developer.apple.com/documentation/usernotifications/establishing-a-token-based-connection-to-apns).

### Valor no aviso de venda concluída

O modelo padrão passa a **Venda U$ {sale_total} concluída**, com o nome do vendedor
no texto (`{user_name}`) e o mesmo atalho para a venda. `{sale_total}` é o total
**das mercadorias em dólares**, calculado com a cotação congelada da venda,
formatado sem centavos quando inteiro (ex.: `800`, ou `800,50`). Não usa a cotação
atual nem acrescenta ressarcimento de cartão. Sem evidência de cotação, exibe `—`.
A variável também funciona em modelos manuais com uma venda real vinculada e na
prévia. Somente o modelo original intocado é atualizado automaticamente; edições
de Lucas e notificações já enviadas permanecem preservadas.
