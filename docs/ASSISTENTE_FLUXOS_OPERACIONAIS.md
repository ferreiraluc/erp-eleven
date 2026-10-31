# Fluxos operacionais do assistente

Atualização de 30/10/2026, conforme os fluxos implementados e testes isolados.

Telegram e WhatsApp Web para a equipe reutilizam as mesmas ferramentas, vínculos
de usuário e confirmações. A conexão WhatsApp por QR, grupos autorizados e limites
estão descritos em [WhatsApp da equipe](WHATSAPP_EQUIPE.md). O canal Twilio anterior
permanece separado. A nova conexão não ativa nem migra números automaticamente.

## Rastreios de clientes

“Manda o rastreio do Taigoro” consulta os envios em trânsito. Se não houver, procura pendentes ou falhas de consulta, identificando o estado real. Entregues não entram nessa resposta; precisam de solicitação explícita de histórico, período ou código específico. Nomes diferentes em entregas antigas não criam ambiguidade sobre um único envio atual.

Um destinatário identificado recebe cada código em uma mensagem isolada, seguido pelos detalhes do ERP em outra mensagem. Vários pacotes atuais do mesmo cliente recebem pares separados; homônimos atuais continuam exigindo identificação. Listagens gerais mantêm datas, paginação e totais. As consultas não atualizam o rastreio nos Correios: exibem os dados atuais salvos no ERP.

Avisos automáticos de novos rastreios no WhatsApp exigem ativação explícita no
painel e só alcançam os grupos autorizados. O código é enviado primeiro, isolado;
os detalhes dependem da aceitação desse envio. Alterar apenas o status de um
rastreio não gera outro aviso de cadastro. Os avisos existentes do Telegram são
preservados.

## Contexto e etiquetas

Continuações usam somente o histórico do próprio autor no canal/conversa. Cadastros e memória confirmada continuam compartilhados conforme as permissões. Não se reaproveitam dados de outro funcionário. Dados históricos de pacote/declaração são referência, não padrão automático para novos envios.

Cotações só são apresentadas após uma operação real persistida. Escolhas curtas como “2” se vinculam à última cotação mostrada ao autor; botões identificam a cotação exata. Consultas de PDF/etiquetas não são substituídas por uma resposta de rastreio apenas porque apareceu um código.

## Prévias de impressão e confirmação

Depois de um pedido de impressão, enviar somente os dados do destinatário continua o pedido na mesma conversa. Para PY, use os dados disponíveis, sem exigir rua, remetente ou documento; RUC/C.I é opcional.

A confirmação é vinculada a uma solicitação persistida. O servidor devolve sua prévia com **Imprimir** e **Cancelar** assim que a ferramenta a prepara, sem outra chamada à IA para reescrever o resultado. Respostas em texto que imitam a prévia A4 ou pedem “diga confirmo” sem criar essa solicitação são retidas e encaminhadas novamente à preparação. Essas prévias inválidas antigas deixam de servir como exemplo no contexto da IA, preservando os dados enviados pelo autor e o histórico original no ERP.

“Confirmo” executa uma única prévia pendente do próprio autor, na mesma conversa, válida por 24 horas. Havendo várias, o bot mostra botões para escolher ou aceita “confirmar impressão NOME”; não seleciona silenciosamente outra impressão ou um pagamento. O botão identifica a solicitação exata, e repetir a confirmação não duplica o trabalho. Se a ferramenta não conseguir preparar a solicitação, o bot informa a falha sem oferecer uma confirmação sem efeito. Corrigir o fluxo não reenvia impressões antigas.

“Pode imprimir” e “imprimir” sem novos dados selecionam somente prévias de impressão
(endereço A4, PDF avulso ou etiqueta já emitida). Mesmo quando resta apenas uma
prévia de pagamento, esse pedido não autoriza pagar ou emitir outra etiqueta.
“Pode imprimir NOME” também mantém essa restrição ao selecionar o destinatário.

## Comprovantes dos Correios em foto

Envie uma foto/JPG/PNG com “Cadastre os rastreios deste comprovante” no Telegram ou
WhatsApp Web conectado. O bot lê os códigos e destinatários legíveis, valida o
dígito verificador e mostra prévia para confirmação. Não cadastra só por receber a
imagem, não inventa caracteres e não duplica códigos existentes. Vínculos de pedido
são sugestões explícitas na prévia, revalidadas ao confirmar. No WhatsApp, a imagem
fica temporariamente protegida por até 24 horas e é apagada ao preparar a prévia;
esta leitura usa o provedor de visão configurado (DeepSeek ou Anthropic). Veja os
limites, privacidade e operação em [Rastreios por comprovante](RASTREIOS_COMPROVANTES.md).

## Produtos e entradas de estoque

Gestores habilitados podem pedir cadastro de produtos/variantes ou entrada de unidades em um produto existente. Há prévia, confirmação do autor, proteção contra repetição da confirmação e movimentação de estoque auditada no mesmo módulo do ERP. Cadastro duplicado pede reaproveitamento do produto. Moeda precisa ser informada quando houver preço; local é necessário para quantidade positiva. Campos opcionais do produto não são inventados; valores ausentes usam os mesmos zeros do formulário e aparecem na prévia.

Não há lançamento de venda, saída, transferência nem ajuste absoluto por essas ferramentas. Mercadorias descritas para uma etiqueta não movimentam estoque automaticamente.

Saldos ausentes de cadastros antigos permanecem **não informados**, distintos de
zero. As consultas de estoque mostram totais incompletos como indisponíveis e
separam a soma dos saldos conhecidos com a quantidade de cadastros sem saldo.
O filtro `nao_informado` consulta o local escolhido (total, loja ou depósito).
A confirmação de entrada é recusada se algum saldo do produto estiver ausente;
consulte **Estoque → Conferir estoque** para identificar os campos a revisar.

## Ponte de PDF com referência temporária

Envie um PDF ao Telegram ou WhatsApp Web conectado com “imprima este PDF”, ou envie
o arquivo e depois peça a impressão. O bot mostra quantidade de páginas e exige
confirmação. Não exige endereço, cliente nem emissão SuperFrete. Limites: 5 MB,
1 a 30 páginas, sem senha. Outros formatos devem ser exportados para PDF.

O PDF não é enviado à IA, não tem seu texto extraído e não cria cadastro nem arquivo
no histórico de endereços. O nome original não é preservado. No Telegram o servidor
baixa o arquivo apenas em memória; conserva somente a referência de download.
No WhatsApp a ponte transfere os bytes autenticados para armazenamento temporário
no banco: até 24 horas desde o recebimento, 25 MB por usuário e 100 MB no total.
São aceitos somente PDF validado e JPG/PNG; não são aceitas URLs ou caminhos locais.

Na confirmação, a referência técnica vai para a fila por até 24 horas. O WhatsApp
preserva o vencimento original do anexo: confirmar depois não renova a retenção.
O agente Windows pede o documento usando sua credencial atual; o servidor confere
autor, conversa e assinatura dos mesmos bytes aprovados antes de encaminhá-los.
O computador usa um PDF temporário para o Sumatra, removido após o processamento e
confirmação ao ERP. A referência da fila é removida ao receber resultado, cancelar
ou expirar. Bytes temporários do WhatsApp são limpos ao vencer; nunca entram no
histórico de conversa enviado à IA. Estados/IDs técnicos ficam para evitar impressão
duplicada. O documento original permanece no aplicativo de mensagens conforme as
regras do canal.

O bot não confirma a saída física do papel. O Windows precisa estar ligado, conectado e com Eleven Impressão aberto. Não é necessário reinstalar o agente para este fluxo. Quando a conexão cai durante o processamento, a limpeza local ocorre na retomada do agente.

Referências de integração: [Telegram Document](https://core.telegram.org/bots/api#document), [Telegram getFile](https://core.telegram.org/bots/api#getfile), [pypdf](https://pypdf.readthedocs.io/en/stable/).
