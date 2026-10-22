# Etiquetas internas de produtos — Zebra ZD220

## Uso

**Estoque → Mais ações → Etiquetas de produtos** abre `/inventory/labels`.
Também é possível selecionar produtos no estoque e usar **Imprimir etiquetas**.
O módulo é independente dos exemplos de etiquetas usados no OCR e das etiquetas
de transporte SuperFrete. Não usa IA, não movimenta estoque e não cria vendas.

1. Em **Selecionar**, procure produtos, grades ou lotes de recebimento. Uma grade
   ou lote adiciona todos os produtos ativos vinculados, inclusive além da página
   visível. Selecionar a mesma peça por dois caminhos não aumenta suas cópias.
2. Em **Conferir**, ajuste cada quantidade com `− / +`, remova linhas ou aplique a
   quantidade a todos, a uma cor ou a um tamanho. É possível usar o saldo da loja,
   depósito ou total explicitamente. Saldos desconhecidos/zero não são inventados:
   revise a linha ou remova-a. Quantidade inicial: uma etiqueta por produto.
3. Abra a prévia, confira os produtos, quantidades e papel, marque a confirmação e
   envie. A primeira instalação deve começar com **uma etiqueta** e conferência
   física de margens, alinhamento e leitura antes de imprimir lotes grandes.
4. A aba **Fila** consulta os últimos 20 pedidos. Funcionários veem os próprios;
   Lucas pode consultar todos. **Cancelar pendentes** afeta somente os trabalhos
   ainda não recolhidos. A confirmação não pode recolher papel já enviado ao Windows.

Limites por confirmação: **500 produtos, 100 cópias de cada produto e 2.000
etiquetas no total**. Um trabalho por variação conserva a ordem da conferência.
Os jobs pendentes deste perfil não expiram automaticamente. O Windows pode receber
vários trabalhos autorizados e mantê-los no spooler quando a USB estiver desligada.

## Papel e identificação

Zebra ZD220 **203 dpi**, etiquetas adesivas de **60 mm de largura × 30 mm de
altura**, uma por fileira, com intervalo entre etiquetas. ZPL usa 480 × 240 pontos,
modo de sensor por intervalo (`^MNY`) e destaque/tear-off. Não enviar este perfil
para bobina contínua de tickets, etiquetas em duas colunas ou mídia de marca preta.
Calibre a mídia no driver/Zebra ao trocar a bobina; o agente não faz calibração
automática nem grava configurações na memória flash.

O layout dos novos trabalhos segue o arquivo `PADRAO.nlbl` recebido em 22/10/2026:
**ELEVEN** centralizado no alto; nome, tamanho, cor e código interno à esquerda;
QR do produto à direita; preço de venda abaixo. O preço usa a moeda cadastrada no
produto (U$, R$, G$ ou €); sem valor positivo aparece apenas `-`. Quando existe
código de barras cadastrado, ele aparece em texto pequeno no canto inferior
direito. A etiqueta não inventa país de origem: o exemplo `Made in: IT` do arquivo
não é impresso porque o cadastro ainda não contém esse dado. Os campos longos são
reduzidos/abreviados somente na etiqueta; não alteram o cadastro. A prévia PNG
usa o mesmo bitmap monocromático de 480 × 240 pontos enviado à Zebra.
Para os novos trabalhos (layout v4), o servidor desenha o título em Arimo Bold
e os detalhes em Arimo; as fontes residentes da Zebra não mudam o resultado.
As fontes e licenças OFL estão em `backend/app/assets/fonts/`. A posição e o
espaçamento foram calibrados pela etiqueta física impressa do `PADRAO.nlbl`:
ELEVEN centralizado com cerca de 150 × 29 pontos, quatro linhas à esquerda mais
espaçadas e QR de 29 × 29 módulos, 3 pontos por módulo, à direita. O QR continua
contendo só o código interno. Preço em USD aparece com `$`, como no padrão.
O arquivo `.nlbl` não é enviado diretamente à Zebra: o agente recebe ZPL RAW
gerado dos dados de cada produto. A impressão física ainda deve ser conferida
para margens, avanço da mídia, contraste e leitura do QR.

Trabalhos v1/v2/v3 criados antes desta mudança mantêm seus ZPLs originais ao serem
recolhidos ou baixados; alterar seus bytes invalidaria o SHA-256 já registrado.
Cada novo trabalho guarda a versão do layout e o preço no
snapshot, para que edições posteriores do produto não modifiquem uma etiqueta já
confirmada. Se preço ou moeda mudar entre a seleção e a confirmação, o ERP pede
para atualizar a seleção antes de imprimir.

O QR contém **somente `inventory_code`**, por exemplo `INV-A7K4P2`. Cada tamanho/cor
é um cadastro diferente e tem seu próprio código. Várias unidades desse cadastro
recebem etiquetas iguais; não há serialização de unidades físicas. Preços, URLs,
credenciais e dados de clientes não entram no QR. UUID, SKU legado e código do
fabricante permanecem intactos.

Use a câmera **dentro do ERP**: PDV resolve a referência exata e segue as regras
atuais do carrinho/local/saldo; estoque filtra a identidade exata. Um código interno
inexistente ou inativo não vira produto avulso no PDV e não busca produtos parecidos.
A câmera nativa do telefone vê o texto do código, não um link público de produto.

## Instalação e separação das impressoras

O responsável confirmou em 21/10/2026 que a **3nStar já imprime os tickets do PDV**.
A mudança da Zebra é aplicada na configuração explícita deste módulo:

1. Conclua os trabalhos antigos da Zebra e feche **Eleven Tickets** no Windows.
2. Como Lucas, abra **Etiquetas de produtos → Impressora**, marque o uso exclusivo
   e clique **Configurar Zebra para etiquetas**.
3. Havendo uma Zebra de tickets ativa, o backend exige 3nStar/ESC-POS como destino
   automático e ausência de tickets pendentes/em processamento. Reutiliza o ID da
   Zebra, preserva seus jobs/histórico, muda a finalidade para `product_labels`,
   desliga `auto_receipts` e revoga a credencial antiga. Duas Zebras exigem revisão.
   Sem Zebra anterior, cria um destino próprio. Samsung/A4 e 3nStar não são alteradas.
4. Copie a credencial exibida uma única vez. Baixe **agente Windows**, extraia todo
   o ZIP e execute `Instalar.cmd`. Escolha a fila USB da ZD220 e informe a credencial.
5. Abra **Eleven Etiquetas** na Área de Trabalho e coloque/calibre o papel 60 × 30.
   O programa deve continuar aberto para imprimir; não é serviço e não configura
   inicialização automática. Não requer Sumatra para etiquetas de produtos.

Instalação isolada em `%LOCALAPPDATA%\ElevenPrintLabels`, com configuração protegida
por DPAPI e diário próprio. O perfil A4 permanece em `ElevenPrint`; o histórico
local de `ElevenPrintTickets` não é apagado. Atualizar a instalação com Enter mantém
a credencial existente. Se ela for perdida, Lucas pode gerar outra, desde que
nenhum job esteja em processamento, e atualizar o agente.

A instalação não imprime e a publicação do ERP não instala o programa no Windows.
Vendas continuam direcionadas à 3nStar. Após reservar a Zebra, a API bloqueia sua
recriação pelo configurador legado de tickets.

## Entrega, reconexão e limites reais

- Render mantém `print_jobs`, snapshots e idempotência. O Windows consulta por
  HTTPS com credencial própria, baixa somente seus ZPLs e verifica SHA-256.
  Nenhuma porta USB/TCP é exposta à internet. Não usa conexão ao celular.
- O perfil novo exige capacidade `product_labels=true` e uma `claim_key` persistida
  antes da coleta. Uma resposta perdida recupera o mesmo trabalho. Não há segunda
  coleta enquanto a anterior estiver em processamento.
- O agente guarda estado antes de enviar RAW ao spooler. Falhas de internet ou de
  pré-verificação anteriores ao envio deixam o trabalho para reconexão. Após iniciar
  o envio, erro, timeout ou reinício resultam em **incerto**, sem reenvio automático.
- `submitted` significa aceito pelo spooler, não prova da impressão física. Confira
  papel e fila Windows antes de selecionar novamente um item incerto para nova cópia.
- A confirmação web é mantida por usuário em `sessionStorage` até uma resposta
  conclusiva. **Recuperar confirmação** repete a mesma chave/corpo, inclusive após
  recarregar. Não gerar uma nova confirmação para resolver uma resposta perdida.
- Nos trabalhos v3/v4, textos, QR e valores são pixels de um gráfico `^GFA` gerado
  pelo servidor a partir do snapshot: nomes nunca viram comandos ZPL. Trabalhos
  v1/v2 continuam escapando texto byte a byte com `^FH`. O agente segue enviando
  RAW e aceita o gráfico dentro do seu limite de 32 KiB; não recebe ZPL
  arbitrário de usuários.

Implementação: `services/product_labels.py`, `api/endpoints/inventory_labels.py`,
extensões do agente em `api/endpoints/printing.py`, `ProductLabelsView.vue` e
`tools/eleven-print-agent/{AgenteEtiquetas,Etiquetas}.ps1`. Não exige nova migração:
reutiliza as colunas de perfil, snapshot, parent_id e claim_key existentes.

Validação: seleção de lotes/grades, limites, permissões, snapshots, rollback,
idempotência, cancelamento e coleta concorrente em PostgreSQL isolado; frontend com
resposta perdida/recarregamento; PowerShell com envio substituído por teste local,
sem tocar spooler/papel. A impressão física 60 × 30 continua dependendo da
instalação e da primeira etiqueta conferida na loja.
