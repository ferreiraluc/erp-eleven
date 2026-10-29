# Monitoramento Wonca e pausa noturna

Lucas configura **Configurações → Atualização automática dos rastreios**. Crie no
painel oficial Wonca um endpoint HTTPS apontando para
`https://erp-eleven-backend.onrender.com/api/tracking-monitor/webhook`, copie seu
signing secret uma única vez e crie um perfil de **2 horas**, **30 dias**, com
**Parar quando entregue → Parar imediatamente**. Informe os IDs e o segredo no ERP;
o intervalo informado deve corresponder ao perfil real na Wonca. A confirmação
explicita o consumo. A migração não ativa nenhum consumo por conta própria.

O servidor utiliza a `WONCA_API_KEY` já existente. O signing secret fica cifrado
no banco com chave derivada de `SECRET_KEY`; não é retornado pelas consultas,
auditado em texto ou colocado no frontend. Deixar o campo vazio preserva o segredo.
Trocar `SECRET_KEY` exige informar novamente o segredo antes de reativar. Somente
Lucas consulta e altera a configuração. A assinatura não permite consultas públicas
aos rastreios nem substitui o login dos usuários.

## Horário e consumo

A opção **Pausar das 21h às 07h (Brasília)** vem marcada. A Wonca não apresenta
faixa de horário no perfil: o worker do ERP encerra as inscrições próprias à noite
via `DeleteTrackingSubscriptions` e reinscreve os objetos abertos de manhã via
`UpsertTrackingSubscriptions`. Reconcilia em lotes de até 100, a cada minuto.
O prazo local de 30 dias começa na primeira inscrição e não reinicia de manhã.
Após a entrega, arquivamento, desativação ou prazo, a inscrição é encerrada.
Registros fora do formato Correios (duas letras, nove dígitos, duas letras) não
são inscritos por este conector. Não há remoção de inscrições de outros sistemas.

A pausa depende do ERP e da confirmação da Wonca. Uma indisponibilidade pode
atrasar o encerramento; o estado **removing** e o contador de falhas permanecem
visíveis e novas tentativas usam espera progressiva. Silenciar notificações ou
pausar o endpoint não interromperia a cobrança das consultas do provedor. Não
prometer uma garantia absoluta de zero consultas durante falhas externas.
A intenção de inscrição é confirmada no banco antes do envio ao provedor, sob um
lock separado. Uma resposta perdida ou reinício após aceite remoto pode ser
recuperado pelo upsert e cancelado quando necessário. O primeiro webhook também
é aceito se chegar antes da confirmação local do ID remoto.

Cada verificação automática consome uma consulta mesmo sem alterações, usando
primeiro a franquia e depois os créditos Wonca. Sem pausa, 2h permite até 12
verificações por código/dia; com pausa são menos, conforme o agendamento da Wonca.
O ERP não compra créditos nem altera planos. Consultas manuais continuam explícitas.
O job diário anterior ignora os códigos administrados pelo conector, inclusive os
pausados e expirados, evitando consultas duplicadas; os demais preservam o fluxo
existente. Após 30 dias, o operador deve conferir manualmente objetos ainda abertos.

## Recepção e processamento

`POST /api/tracking-monitor/webhook` aceita JSON de até 256 KiB, confere HMAC-SHA256
sobre os bytes brutos, timestamp com tolerância de 5 minutos e identidade do evento.
O segredo é usado como string original, sem decodificar base64. A resposta 202 só
ocorre após o recibo durável ser confirmado no banco. Reentregas com o mesmo ID e
conteúdo não repetem o processamento. Eventos assinados de códigos não administrados
são ignorados, sem criar inscrições. Não se faz nova chamada a Track ao receber.

O worker `wonca` aplica o histórico normalizado, sincroniza pedidos com a ordem de
locks existente e gera notificações transacionais com o nome do destinatário.
Uma nova ocorrência pode avisar mesmo permanecendo **Em trânsito**; reconsulta
idêntica não duplica avisos. Eventos anteriores à consulta já aplicada e regressões
de Entregue são ignorados. Consultas manuais registram o mesmo marcador temporal.
O campo `provedor_verificado_em` utiliza UTC explícito, sem reinterpretar datas
antigas locais. Eventos que falhem cinco vezes são sinalizados para revisão e não
bloqueiam os seguintes. O payload bruto é eliminado após processar/ignorar/falhar;
recibos sem dados brutos são mantidos por 90 dias para idempotência.

`/health` informa `wonca_worker`; um problema neste conector não deve interromper
PDV ou outras funções. O painel mostra inscrições ativas, pendentes, pausadas,
encerradas e falhas. A própria Wonca pausa o endpoint após dez entregas falhas;
confira e reative pelo painel do provedor após corrigir o destino.

A validação automatizada usa assinaturas e eventos sintéticos, provedores falsos,
PostgreSQL isolado para migração/concorrência/rollback, e testes do painel. Ela não
comprova uma consulta real dos Correios nem a execução exata do agendamento externo.
Referência oficial: https://labs.wonca.com.br/webhooks/api.
