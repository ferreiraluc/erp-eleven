# Gestor de Vendas do PDV

## Ticket automático no caixa

Lucas configura **PDV → Tickets** para o agente Windows exclusivo da Zebra ZD220.
Ao ativar, **Confirmar e imprimir** grava a venda e uma solicitação de ticket na
mesma transação, inclusive em vendas pelo celular. Sem ativação, o recibo continua
disponível para impressão neste aparelho/PDF. Não depende de IA nem de AirPrint.

O recibo mostra fila, processamento, envio ou resultado incerto. Atualizar estado
não imprime; outra cópia exige confirmação e respeita a identidade da venda, o
escopo do vendedor e a chave de repetição. Vendas estornadas, anuladas ou devolvidas
exibem essa situação e as quantidades/valores devolvidos no comprovante. Não são
apresentadas como uma venda normal. O ticket conserva o snapshot da revisão enviada.
Alterações posteriores não reimprimem automaticamente.

Filas A4 e tickets permanecem separadas. Para bobina contínua de 80 mm, selecione
**Bobina contínua** em PDV → Tickets: uma página com altura calculada (até 991 mm),
sem separação em etiquetas. Requer agente Windows 2026.10.14.3. Etiquetas fixas
continuam disponíveis; trocar formato exige fila vazia. Instalação,
limites e migração futura ao Mac: [Impressão](IMPRESSAO_WINDOWS.md#tickets-do-pdv--zebra-zd220-14102026).

A página **Vendas** (`/vendas-pdv`) fica nas ações rápidas do dashboard, ao lado de
Nova Venda. Consulta exclusivamente `PdvSale`. `/vendas` conserva os lançamentos
operacionais antigos; `/bi-vendas` conserva as planilhas. Nenhuma destas operações
altera Excel, cria conciliações automáticas ou soma receitas entre fontes.

**Ver venda** no histórico do cliente abre os detalhes no gestor por um vínculo
`/vendas-pdv?sale_id=…`, inclusive para vendas fora da página atual. Fechar o modal
remove apenas esse parâmetro; voltar/avançar no navegador acompanha a seleção.
A API de detalhes continua conferindo o acesso do vendedor. O atalho não concede
edição, estorno ou exclusão: essas operações continuam exclusivas do Lucas, com
prévia, confirmação e idempotência.

## Consultar, baixar e reimprimir tickets

Em **Vendas → Ver venda → Ticket / PDF**, o operador autorizado a consultar a venda
pode baixar o PDF ou enviar uma cópia para a mesma fila de tickets do caixa. Abrir
a prévia e **Salvar PDF** são leituras: não criam venda, movimentação ou impressão.
Vendas excluídas permanecem no histórico administrativo, sem emissão de ticket.
O botão **Ler ticket** usa a câmera; leitores USB podem preencher a busca textual.
A leitura limpa os demais filtros para localizar o ticket, mantendo o escopo de
acesso imposto pelo backend. Não abre nem seleciona automaticamente a primeira venda.

O comprovante é sempre em espanhol, inclusive com o ERP em português/inglês:
ELEVEN, Shopping Paris - PY, contato@elevenparispy.com, data/hora local, produtos,
subtotal, descontos, total, pagamentos na moeda original, vendedor e cliente.
Não inventa dados de cartão, autorização, impostos ou condições de garantia.
A prévia HTML, o PDF baixado e o arquivo da Zebra usam a mesma apresentação no
backend (`pdv_receipt_layout`). O PDF conserva as dimensões configuradas na fila;
sem configuração, usa 80 × 200 mm. A paginação continua necessária em etiquetas curtas.
Não é necessária atualização do agente Windows para esse layout.

O Code 128 contém os primeiros **10 caracteres hexadecimais do UUID**, em caixa alta.
Esse código legível e o UUID completo também aparecem no papel. A busca aceita
ambos; o prefixo é consultado por intervalo no índice UUID. Ele é um localizador,
não uma nova identidade única: se houver colisão, todos os resultados autorizados
são exibidos para conferência. O ID real e as chaves de idempotência não mudam.

O snapshot da revisão já enviada é reutilizado mesmo após a remoção do PDF
temporário. Uma venda editada/devolvida usa a revisão atual; cópias são identificadas
como **COPIA**. Nenhuma consulta dispara impressão ou refaz lançamentos financeiros.

## Cliente e moeda na nova venda

Em `/pdv`, busque o cliente por **nome, telefone, documento (CPF/RUC/C.I.) ou CEP**.
A busca desconsidera acentos, espaços e pontuação. Retorna até 20 opções e pede
refinamento quando há mais; CEP compartilhado não escolhe uma pessoa sozinho.
São consultados cadastros ativos do PDV, do diretório Clientes (incluindo CEP de
8 dígitos no endereço textual antigo) e endereços ativos com vínculo confirmado.
Endereços sinalizados para revisão não atribuem dados
a um cliente. A busca não cria registros e não retorna saldos financeiros.

Selecione o resultado para associá-lo à venda. Um cliente do diretório recebe um
vínculo explícito em `pdv_clientes.cadastro_cliente_id` (migração `c5d6e7f8a9b0`).
Se já existir cadastro PDV único com documento/telefone e nome completo compatíveis,
ele é reaproveitado; conflitos pedem seleção do cadastro PDV existente. Seleções
simultâneas do mesmo cliente são serializadas. Nenhum saldo ou venda anterior é
fundido. A consolidação de clientes move apenas esse vínculo, preservando contas
PDV distintas; nesse caso o operador escolhe qual conta utilizar.

O cliente pode ser removido/trocado antes de concluir. **Usar somente o nome, sem
cadastro** é uma opção explícita para visitantes; digitar uma busca não grava esse
texto como nome. Ao concluir, o backend valida novamente o cliente e salva seu
nome cadastrado como snapshot da venda. Checkout fica bloqueado durante a seleção.

No modal de **produto avulso**, escolha **G$, R$, U$ ou EUR** e informe o preço
nessa moeda. A prévia mostra o câmbio do PDV e o equivalente unitário em G$;
cotação inválida bloqueia a inclusão. O carrinho conserva moeda/preço digitados e
calcula o total em guaranis com a mesma conversão dos produtos de catálogo. Como
nos demais itens do PDV, as linhas da venda persistem em G$; os pagamentos têm
seu próprio registro de moeda e cotação. Incluir um avulso não cadastra produto
nem movimenta estoque.

## Uso rápido no celular

O botão **+** junto à busca abre o cadastro compacto de cliente: nome, telefone e
CPF/RUC/C.I.; endereço fica em uma seção opcional. Usa o diretório Clientes e a
mesma validação de duplicidade. Após salvar, o vínculo PDV existente é selecionado
ou criado pelo fluxo de associação. Se a seleção falhar depois do cadastro, o botão
**Associar cliente cadastrado** repete só o vínculo, sem cadastrar outra pessoa.

A aba Produtos começa com os **8 produtos ativos mais recentes por criação**.
Busca retorna até 20 resultados, cancela a consulta anterior e descarta respostas
atrasadas. Usa listagem sem imagens originais e a fila/cache de miniaturas sob demanda.
O ícone de câmera continua abrindo o leitor de código de barras.
Essa leitura e o aviso de código já cadastrado também consultam produtos sem
transportar as fotos originais (`include_images=false`). Miniaturas continuam
carregadas sob demanda; todos os produtos ativos com o mesmo código são oferecidos
para escolha, sem selecionar uma peça arbitrariamente. O endpoint mantém a opção
legada de incluir imagens para outros consumidores.
Enquanto o produto desse código está sendo consultado, o checkout aguarda: o
resultado ainda pode alterar o carrinho. Limpar o carrinho ou iniciar outra busca
descarta essa resposta pendente, sem adicionar produtos à venda seguinte. Limpar
a busca recupera os produtos recentes mesmo quando o carregamento inicial foi
interrompido. Os cartões recentes usam o último saldo consultado para validar a
inclusão; uma cópia antiga do cartão não substitui esse saldo.
Limpar um carrinho ainda não enviado libera as reservas locais e conserva os saldos
consultados, permitindo iniciar outro carrinho sem recarregar a página. Após uma
venda concluída, ou ao descartar um checkout de resultado incerto, a lista é
reconsultada: saldos antigos não são oferecidos durante essa atualização.
Preços Decimal enviados como texto pela API são interpretados como números;
preço ausente/inválido continua desconhecido e bloqueia a inclusão, sem virar zero.

A lista se adapta à largura do painel de produtos, inclusive no iPad com carrinho
lado a lado. Nome e SKU têm espaço próprio; avisos de estoque podem quebrar linha
sem comprimir o nome nem deslocar o botão de adicionar.
**Total**, **Adicionar**, **Concluir** e as demais ações não focam campos de texto.
Ao tocar em um botão, um teclado aberto é dispensado. Campos continuam editáveis
ao toque, e os atalhos explícitos F2/F5 e Enter permanecem disponíveis. Abrir um
produto avulso ou remover o cliente também não abre o teclado automaticamente.

Quantidade, preço e remoção ficam na mesma linha. O símbolo do preço abre um seletor
**U$, R$, G$ ou EUR**: troca a moeda da linha, convertendo o valor pelo câmbio vigente
com arredondamento a centavos. Não altera o preço/moeda do catálogo. O preço continua
editável; conversões e total respondem a cada digitação, aceitando ponto ou vírgula
decimal. Campos vazios/inválidos não confirmam uma venda com o preço anterior.

### Uma fonte de câmbio

Dashboard, PDV e gestão de câmbio usam `stores/currency` e
`GET /api/exchange-rates/current`, com os mesmos pares da tabela `exchange_rates`.
Valores Decimal vindos como texto são convertidos para número nessa fronteira.
O cache único `erp_rates` é apenas uma prévia; o antigo `erp_exchange_rates` é migrado
e deixa de ser escrito. Abrir diretamente o PDV também busca as taxas atuais.

O editor compartilhado `ExchangeRateModal` é exibido em `body`, fora da rolagem
do carrinho. Carrega os valores persistidos, mostra erro/repetição e não substitui
as taxas de EUR por constantes. Salvar altera só os campos editados e recarrega o
estado compartilhado. Perfis e validação do servidor continuam vigentes; pagamentos
já adicionados guardam suas cotações negociadas. A gestão de histórico continua
separada das taxas atuais. Não altera valores históricos do PDV/BI.

## Métodos e moeda do pagamento

Novos pagamentos possuem moeda obrigatória, conferida na tela e na API:

| Método | Moeda de lançamento |
| --- | --- |
| Dinheiro U$ | USD |
| Dinheiro R$ | BRL |
| Dinheiro G$ | GS |
| Dinheiro EUR | EUR |
| Cartão Crédito PY, Cartão Débito PY, QR Máquina PY Débito | GS |
| PIX (pessoal), PIX (Thais), MaquinaThais, MercadoPago (link) | BRL |
| TransferenciaPY | GS |
| USDT | USDT |
| Anotar (fiado) | GS, com cliente cadastrado selecionado |

Nos pagamentos em dinheiro, o símbolo também permite trocar a moeda, selecionando
o método Dinheiro correspondente e limpando o valor anterior. PIX, cartão e os
outros métodos conservam suas moedas obrigatórias.

O botão **Total** preenche o restante na moeda do método. Trocar o método limpa
o valor ainda não adicionado, para não reinterpretar dólares como reais/guaranis.
O operador pode alterar o câmbio para G$ de um pagamento em moeda estrangeira;
guaranis usam sempre taxa 1. USDT começa com a mesma cotação de USD (1 USDT = 1 U$),
por convenção confirmada pela loja, podendo ser ajustado. Não há cotação de cripto
nem cobrança/transferência automática em provedores.

Busca de produtos, itens do carrinho e total mostram G$, U$ e R$ pelo câmbio vigente;
produtos em EUR conservam também o valor original. O modal de câmbio continua
disponível aos perfis autorizados. Uma alteração recalcula os itens do carrinho
aberto a partir do preço original. Pagamentos já adicionados mantêm a taxa acordada;
remova e adicione novamente para renegociá-los. A razão BRL/EUR usa seis casas de
precisão, sem arredondar previamente a cotação para guaranis inteiros.

O livro financeiro interno e os saldos de fiado permanecem em G$. Cada pagamento
guarda unidade, valor original, taxa para G$ e equivalente convertido. São validados
moeda/método, valores finitos, até duas casas no valor e consistência da conversão
(tolerância de 1 G$ para arredondamentos históricos). A migração `f8a9b0c1d2e3`
amplia `pdv_payments.currency` para quatro caracteres, preservando todos os registros.

Recibos, filtros e gestor compartilham os nomes atuais. Métodos genéricos antigos
(como Cartão/PIX) continuam legíveis e filtráveis, sem supor se eram crédito/débito
ou Pix pessoal/Thais. Uma correção do Lucas pode conservar o pagamento antigo
integralmente; para alterá-lo, selecione um método atual e confira valor e moeda.

## Consulta e acesso

Filtros por período inclusivo em Brasília, vendedor, pagamento, situação e busca
por cliente, produto, SKU ou UUID. Paginação no servidor, totais do filtro completo
e exportação CSV da página visível. As datas originais de criação são preservadas.
Lucas e Wissam consultam o geral; os usuários com escopo pessoal consultam apenas
suas próprias vendas. O filtro financeiro precede paginação e agregação.

**Somente Lucas** (`is_owner`) pode editar, devolver, estornar ou excluir, inclusive
pela API antiga de cancelamento. Os demais usuários continuam criando vendas.
Esconder botões no frontend não é a autorização efetiva: preview e commit exigem
`require_owner`, e o serviço também confere a identidade.

## Correção

Lucas pode trocar/adicionar/remover itens, quantidades, local, preço, desconto,
cliente, vendedor, observações e pagamentos. O vínculo de catálogo usa ID; o nome,
SKU, cor e tamanho vêm do produto selecionado. Código de barras repetido não
resolve identidade. Itens avulsos não movimentam estoque.

Os pagamentos corrigidos representam o valor aplicado à venda, **sem troco**,
e devem somar exatamente seu total. Moeda original, conversão para guaranis,
valor convertido e referências ficam registrados. A prévia valida limites,
valores finitos, descontos, produtos ativos e saldos suficientes.

A correção aplica apenas a diferença de estoque por produto/local e a diferença
de fiado por cliente. Preserva uma revisão completa antes/depois em
`pdv_sale_events`, antes de substituir as linhas/pagamentos da representação atual.
Não apaga movimentos anteriores nem recebimentos de fiado.
Vendas que já tiveram devolução/cancelamento não são reescritas: a revisão anterior
continua disponível, e outra operação comercial deve ser uma nova venda.

## Devolução e estorno

- **Devolução parcial:** selecionar linha e quantidade restante, com ou sem
  reposição ao local original. Aceita quantidades fracionárias apenas em avulsos.
- **Estorno integral:** estorna todas as quantidades ainda não devolvidas, com
  escolha explícita de repor ou não o estoque.
- Desconto geral distribuído proporcionalmente, com arredondamento cumulativo
  determinístico. Devolver tudo em etapas chega exatamente ao total da venda.
- Fiado é abatido primeiro, limitado ao valor estornado e ao débito efetivamente
  lançado para a venda. A diferença é mostrada como valor a devolver fora do ERP.
  Se o cliente já pagou o fiado, a reversão pode gerar saldo negativo, identificado
  como crédito a favor dele; pagamentos recebidos não são apagados.
- **Nenhum reembolso bancário, Pix ou cartão é executado pela API.** O gestor
  registra o estorno administrativo. O operador realiza e confere a devolução
  financeira no meio original, evitando pagar novamente um crédito já concedido.
- Pagamentos antigos insuficientes, fiado divergente ou totais inconsistentes
  exigem conferência/correção; o sistema não presume dinheiro recebido.
- Produtos retirados do catálogo não são reativados. Uma devolução sem reposição
  pode ser registrada; reposição exige produto válido e saldo consistente.

Situações: `completed`, `partially_refunded`, `refunded`, `cancelled`. Quantidades
acumuladas ficam nas linhas; valores acumulados na venda. Consultas do bot usam o
valor líquido e desconsideram canceladas/excluídas. O histórico de pagamentos da
venda mostra os registros originais; estornos são eventos separados.

## Exclusão preservando auditoria

Excluir uma venda ativa estorna o restante conforme a prévia e marca `deleted_at`.
Uma venda já cancelada/estornada apenas sai da listagem. Nunca remove fisicamente
venda, movimentos, pagamentos, revisões ou recebimentos. Lucas pode consultar
**Histórico de excluídas** no filtro Listagem; não há reativação nesta versão.
Registros cancelados antes deste módulo são preservados sem tentar reconstruir
estornos financeiros que não foram gravados.

## Confirmação, concorrência e histórico

Todas as novas ações passam por motivo → prévia do efeito → checkbox → confirmação.
O plano inclui estado da venda, estoque e fiado. Se algo mudar, retorna 409 e exige
nova revisão. Locks seguem venda, produtos ordenados e clientes ordenados. Falhas
revertem estoque, fiado, venda e auditoria juntos.

`request_id` único e fingerprint vinculam a confirmação à operação exata. Repetir a
mesma requisição retorna o evento existente; outra operação com a mesma chave é
rejeitada. Falha de rede no frontend conserva a chave e permite repetir a mesma
confirmação. Não há integração com provedores de pagamento neste processo.

Lucas vê até as 100 revisões mais recentes na ficha, incluindo itens antes/depois;
as revisões anteriores permanecem no banco. Eventos da auditoria geral:
`pdv_edit`, `pdv_return`, `pdv_cancel`, `pdv_delete`. Consultas não geram auditoria.
A conciliação com o caderno/BI continua planejada em `CONCILIACAO_VENDAS.md`.

## Implementação e validação

- Serviço: `app/services/pdv_management.py`.
- Contratos: `app/schemas/pdv_management.py`.
- API: `GET /api/pdv/management`, `/options`, `/{sale_id}`;
  `POST /{sale_id}/preview` e `/{sale_id}/commit`.
- Frontend: `SalesManagementView.vue`, componentes `pdv/management/`.
- Migração `a3b4c5d6e7f8`: valores iniciais neutros para vendas antigas, devoluções
  por linha e tabela de revisões. Downgrade destrutivo não é automático.
- Testes isolados de cálculo, permissões, devoluções consecutivas, idempotência,
  troca de produto/cliente, fiado, rollback e revisão obsoleta. PostgreSQL valida
  migração e concorrência real; UI validada com dados sintéticos, sem emitir
  pagamentos, estornos externos ou impressões reais.
