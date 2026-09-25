# Fluxos operacionais do assistente

Atualização de 25/09/2026, baseada nas conversas registradas no ERP.

## Rastreios de clientes

“Manda o rastreio do Taigoro” consulta os envios em trânsito. Se não houver, procura pendentes ou falhas de consulta, identificando o estado real. Entregues não entram nessa resposta; precisam de solicitação explícita de histórico, período ou código específico. Nomes diferentes em entregas antigas não criam ambiguidade sobre um único envio atual.

Um destinatário identificado recebe cada código em uma mensagem isolada, seguido pelos detalhes do ERP em outra mensagem. Vários pacotes atuais do mesmo cliente recebem pares separados; homônimos atuais continuam exigindo identificação. Listagens gerais mantêm datas, paginação e totais. As consultas não atualizam o rastreio nos Correios: exibem os dados atuais salvos no ERP.

## Contexto e etiquetas

Continuações usam somente o histórico do próprio autor no canal/conversa. Cadastros e memória confirmada continuam compartilhados conforme as permissões. Não se reaproveitam dados de outro funcionário. Dados históricos de pacote/declaração são referência, não padrão automático para novos envios.

Cotações só são apresentadas após uma operação real persistida. Escolhas curtas como “2” se vinculam à última cotação mostrada ao autor; botões identificam a cotação exata. Consultas de PDF/etiquetas não são substituídas por uma resposta de rastreio apenas porque apareceu um código.

## Produtos e entradas de estoque

Gestores habilitados podem pedir cadastro de produtos/variantes ou entrada de unidades em um produto existente. Há prévia, confirmação do autor, proteção contra repetição da confirmação e movimentação de estoque auditada no mesmo módulo do ERP. Cadastro duplicado pede reaproveitamento do produto. Moeda precisa ser informada quando houver preço; local é necessário para quantidade positiva. Campos opcionais do produto não são inventados; valores ausentes usam os mesmos zeros do formulário e aparecem na prévia.

Não há lançamento de venda, saída, transferência nem ajuste absoluto por essas ferramentas. Mercadorias descritas para uma etiqueta não movimentam estoque automaticamente.

## Ponte de PDF sem arquivo no ERP

Envie um PDF ao Telegram com “imprima este PDF”, ou envie o arquivo e depois peça a impressão. O bot mostra quantidade de páginas e botão de confirmação. Não exige endereço, cliente nem emissão SuperFrete. Limites: 5 MB, 1 a 30 páginas, sem senha. Outros formatos devem ser exportados para PDF.

O servidor baixa o PDF apenas em memória para validar e calcular a assinatura. Não extrai texto, não envia conteúdo à IA, não grava bytes do documento no banco/disco e não cria cadastro ou arquivo no histórico de endereços. O nome original também não é preservado.

Até a confirmação existe apenas uma referência técnica temporária ao anexo Telegram. Na confirmação, a referência vai para a fila por até 24 horas. O agente Windows pede o documento usando sua credencial atual; o servidor busca os mesmos bytes em memória, confere a assinatura e os encaminha. O computador usa um PDF temporário para o Sumatra, removido após o processamento e confirmação ao ERP. A referência no servidor é removida ao receber resultado, cancelar ou expirar; ficam somente estados/IDs técnicos para evitar impressão duplicada. O documento original continua no Telegram conforme as regras desse canal.

O bot não confirma a saída física do papel. O Windows precisa estar ligado, conectado e com Eleven Impressão aberto. Não é necessário reinstalar o agente para este fluxo. Quando a conexão cai durante o processamento, a limpeza local ocorre na retomada do agente.

Referências de integração: [Telegram Document](https://core.telegram.org/bots/api#document), [Telegram getFile](https://core.telegram.org/bots/api#getfile), [pypdf](https://pypdf.readthedocs.io/en/stable/).
