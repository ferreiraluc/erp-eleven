# Notificações da Eleven

## Uso por aparelho

O sino abre **Notificações** (`/notificacoes`), com mensagens pessoais, pendências,
confirmação de leitura, respostas e preferências de categorias e som. A central
continua disponível mesmo quando o aparelho não permite notificações externas.

Na próxima abertura autenticada de cada aparelho, aparece o convite **Ativar
notificações**. O usuário precisa tocar nesse botão e aceitar a permissão do
navegador. Adiar oculta o convite por 24 horas naquele aparelho/conta. O ERP não
pode aceitar a permissão por ninguém nem desfazer uma recusa nas configurações
do navegador. Contas com senha temporária precisam primeiro concluir a troca.

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

O aviso externo contém texto genérico, sem valores de venda, nomes de clientes ou
corpo da mensagem. Para ver os detalhes, o usuário abre o ERP e se autentica.
Sair, trocar de conta, revogar a sessão ou desativar o usuário impede novas
entregas por aquela sessão. A sessão continua com o prazo existente de sete dias;
abrir novamente revalida a conta e restaura a inscrição quando permitido.

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
abre a central; não intercepta requisições nem mantém cache de HTML, JS ou APIs.
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
