# Estoque e leitura de etiquetas

## Busca no catálogo

Uma busca ou filtro sem correspondências oferece **Limpar Filtros**, removendo
texto, status, marca, categoria, local e seleção de itens sem grade. O modo de
visualização e agrupamento é preservado. Uma lista vazia sem filtros permite
**Novo item**, sem afirmar que não existem outros produtos fora da seleção.

## Exclusão definitiva de produto

Somente Lucas (`lucas@eleven.com`, ADMIN) vê **Excluir definitivamente** ao editar
um produto. O backend aplica a mesma autorização nas rotas
`GET /api/inventory/items/{id}/deletion-preview` e
`DELETE /api/inventory/items/{id}/permanent`. A desativação existente continua
separada; a seleção múltipla usa as mesmas rotas individuais. Não há ferramenta de exclusão no bot.

A prévia mostra nome, tamanho, cor, SKU, saldos e quantidade de movimentações a
remover. Após marcar a conferência e confirmar, apaga o item, a imagem armazenada
nele e suas movimentações sem vínculo operacional, inclusive a entrada inicial
de um cadastro de teste. Não exige zerar um estoque de teste. As demais variações
da grade permanecem. Auditoria conserva ator, identificação do produto, saldos e
quantidade removidos; não guarda a imagem nem recria o cadastro excluído.

Vendas PDV (inclusive canceladas), referências históricas pelo SKU, contagens de
inventário e movimentações com referências a pedidos/vendas/outras operações
impedem a exclusão. Referências de entrada pelo assistente são permitidas; suas
ações e mensagens históricas continuam preservadas. O bloqueio verifica vínculos
registrados, não infere relações por nomes iguais ou códigos de barras repetidos.
Pedidos em texto livre e linhas financeiras do Excel não possuem relação
estruturada com itens de estoque; esta regra não comprova ausência de menções a
um produto nesses textos.

A confirmação contém o SKU e o token da prévia. Alteração do produto ou de suas
movimentações exige nova conferência. A remoção é transacional e usa bloqueio da
linha e FKs PostgreSQL para impedir vínculos órfãos em operações simultâneas.
Falha de rede não provoca retentativa automática. Os testes de exclusão usam
somente produtos locais descartáveis; não se remove estoque real para validar UI.

## Histórico por produto e retirada do catálogo

Em **Estoque → Editar → Histórico**, a ficha apresenta criação, responsável,
última atualização, SKU/variante e saldos. As seções paginadas mostram:

- **Movimentações**: entradas, saídas, ajustes, transferências, responsável, motivo,
  local e saldo total antes/depois. No ajuste, a quantidade é o valor definido no
  local; não uma quantidade vendida. Transferência conserva o total.
- **Vendas**: vendas PDV distintas, inclusive canceladas, com suas linhas deste
  produto, data, vendedor, cliente, valores em G$, ID e estado da baixa de estoque.
  O total da linha e o total da venda inteira são identificados separadamente.
  ID do produto é vínculo direto; SKU exato em linha antiga sem ID é referência
  histórica. Mesmo nome/código de barras nunca cria vínculo.
- **Contagens**: sessão, local, saldo de referência, quantidade contada e aplicação.
- **Alterações**: auditoria de campos do produto, exclusiva de Lucas. Nomes antigos
  e valores não registrados não são reconstruídos; campos apenas sinalizados como
  alterados são apresentados dessa forma. Consultas não geram novos eventos.

`GET /api/inventory/items/{id}/history` exige autenticação e aplica o escopo de
vendas pessoais antes das contagens e da paginação. Movimentações de estoque são
operacionais; para venda alheia, omite referência, notas, motivo livre e autor.
Dados ausentes não viram zero. Não há backfill nem inferência de lançamentos.
O histórico ainda não associa vendas operacionais/planilhas a itens, pois essas
fontes não possuem vínculo estruturado de produto.

Para produto com vínculos, o modal de exclusão oferece **Excluir e manter histórico**,
exclusivo de Lucas, em `POST /api/inventory/items/{id}/delete-from-catalog`.
Exige revisão e token do estado do produto; o atalho **Ver histórico e vínculos**
abre a seção que explica o bloqueio. A contagem do aviso é de vendas distintas,
e não de linhas de itens dentro da mesma venda.

Essa modalidade marca `deleted_at`/`deleted_by`, inativa e remove a foto. O registro
interno e seu SKU permanecem reservados para preservar FKs, nomes originais, saldos,
vendas, contagens e movimentações. Nas respostas históricas aparece **Produto
excluído — nome original**. Não é exclusão física da linha do banco nem simples
inativação reversível. Não há reativação pelo formulário, ajustes ou pelo bot.
As listas de estoque, inclusive inativos, grupos, opções, OCR, PDV, diagnósticos e
bot excluem esses registros. Lucas os encontra em **Histórico de excluídos**,
cuja consulta é paginada e não carrega fotos.

A retirada do catálogo não cancela vendas, não devolve dinheiro, não remove
faturamento histórico nem registra saída física fictícia. Saldos preservados não
entram no disponível. Uma venda com produto excluído que precise de devolução de
estoque exige revisão: a reposição é recusada atomicamente, sem reativar o
produto. No gestor de Vendas, Lucas pode escolher estorno sem reposição, com
prévia dos efeitos financeiros. A exclusão física para itens sem vínculos
continua disponível pelo fluxo anterior.

Migração: `f2a3b4c5d6e7`, sem alterar registros existentes. Testes de histórico,
permissões, exclusão do catálogo e concorrência usam bases isoladas. O teste
PostgreSQL comprova migração preservando linhas e movimentação concorrente
bloqueada após a retirada do catálogo. Nenhum produto real é removido no deploy.

## Cadastro unificado: foto, etiqueta e estoque

O cadastro segue o [padrão compacto de modais](UI_MODAIS.md), com ações persistentes
e organização/limites opcionais em seção expansível. Na listagem, a visualização
em cards se chama **Quadrados**; **Ver grades** continua sendo o agrupamento de variantes.

**Estoque → Novo item** e o atalho **Novo produto** do dashboard abrem o mesmo
cadastro, em três etapas:

1. **Foto e etiqueta**: duas fontes opcionais, em qualquer ordem. Pode usar só uma,
   ambas ou continuar sem imagens. Cada assistente adiciona sugestões à mesma
   conferência; não cria produtos nem lança estoque. Os provedores continuam
   independentes, sem uma terceira chamada paga para combinar os resultados.
2. **Conferência**: foto escolhida e dados em um formulário. Campos vazios recebem
   as sugestões; valores diferentes aparecem como escolhas **Manter formulário**,
   **Usar foto** ou **Usar etiqueta**. Preço e moeda são tratados juntos. Reabrir uma
   leitura já aplicada não desfaz correções manuais. As diferenças devem ser
   resolvidas e a revisão marcada; mudar os dados/foto reinicia a revisão.
3. **Estoque**: escolha loja/depósito e quantidade. O resumo informa produtos e
   unidades antes de criar. Quantidades não vêm da IA; zero cria somente o cadastro.

**Criar grade deste modelo** habilita a grade apenas por escolha do operador.
Em **Modelo de grade**, o **+** abre nome e tamanhos: por exemplo, nome **M ao 3XL**
e tamanhos **M, L, XL, 2XL, 3XL**. A prévia normaliza e remove tamanhos repetidos;
**Adicionar modelo** ou **Enter** salva todos os tamanhos digitados e aplica o
modelo, incluindo a peça base. Não é necessário confirmar cada tamanho antes.
O nome é apenas um rótulo: intervalos devem ser informados como lista de tamanhos.
Nomes de modelos repetidos geram orientação, sem sobrescrever a opção anterior.
Em **Cores**, o **+** abre um campo compacto na própria linha. Digite a nova cor e
clique em **Adicionar** ou pressione **Enter**. A cor vira um botão reutilizável e
é selecionada para a grade atual. **Esc** ou cancelar recolhe o editor; selecionar
uma cor já existente a reaproveita, sem duplicação.
Modelos e cores personalizados ficam salvos **neste navegador**, não no servidor:
reabrir o cadastro conserva os botões, mas outro dispositivo ou limpeza do navegador
não os conserva. Falha de armazenamento mantém o editor aberto com orientação.
O **×** das cores selecionadas retira apenas a seleção atual; o botão salvo permanece.
Para apagar qualquer botão, use **Editar opções**, ao lado do título da
grade. Aparece um **×** em todos os modelos e cores, inclusive os padrões; **Concluir edição**
recolhe os controles. Remover uma cor também retira sua seleção da grade em edição,
mas não altera a cor da peça base nem tamanhos. Remover um modelo apaga o atalho,
preservando os tamanhos já escolhidos no formulário. Padrões removidos ficam ocultos
por uma preferência local e não reaparecem ao reabrir o cadastro. Opções personalizadas
anteriores são preservadas. Pelo **+**, é possível adicionar a cor padrão novamente
ou cadastrar um novo modelo com o mesmo nome e os tamanhos desejados.
A remoção é salva no mesmo navegador e pode ser revertida cadastrando a opção
novamente. Se o armazenamento falhar, o botão e a seleção permanecem, com aviso.
Nenhum produto salvo ou histórico é alterado por essa organização de atalhos.
Salvar modelo/cor não cria produtos nem movimenta estoque: isso ocorre na confirmação
final do cadastro, após a conferência obrigatória.
Ao selecionar **P → 2XL**, por exemplo, a peça branca P origina P, M, L, XL e 2XL
no mesmo grupo, com foto, marca, descrição e preços compartilhados. O tamanho da
peça base é preservado se estiver fora do modelo escolhido. Sem outras cores
selecionadas, todas as variações usam a cor da peça. É possível cancelar a grade
sem perder os dados e cadastrar somente a peça. O estoque informado na grade é
**por variação**, com total visível antes da confirmação.

Essa opção monta uma grade no novo cadastro. Para produtos já salvos, use as ações
descritas abaixo. Códigos de barras iguais não provam identidade. O cadastro
unificado mantém a regra de negócio da grade: **código de barras base + tamanho**
(por exemplo, `789123P`, `789123M`, `789123XL`), além de um SKU independente por
variação. A prévia mostra cada código resultante, inclusive na matriz de cores e
tamanhos. No produto avulso o código permanece como informado. Os tamanhos de uma
solicitação são normalizados e
deduplicados no backend. Cada chamada de criação de grade confirma produtos e
movimentações iniciais na mesma transação, com rollback se uma movimentação falhar.

### Duplicar produto e adicionar tamanhos a uma grade existente

Em **Estoque → editar produto**, os perfis ADMIN/GERENTE podem escolher **Duplicar
produto** (cadastro completo preenchido) ou **Adicionar grade** (vários tamanhos e modelos salvos
no navegador). Exemplo: abrir o tênis 9 e criar o 8 sem reenviar a foto.
A operação usa os **dados já salvos**; cancelar retorna ao formulário e preserva
as edições locais. Foto, marca, cor, descrição, fornecedor, preços/moedas e limites
são copiados; SKU, vendas, movimentos e saldos não são copiados.

**Duplicar produto** abre o mesmo cadastro unificado, diretamente na conferência.
Todos os campos cadastrais ficam editáveis, incluindo nome, marca, cor, categoria,
preços/moedas, fornecedor, localização, limites, tamanho, código e foto. **Editar foto**
abre a imagem copiada no assistente atual: é possível trocar o arquivo, remover o
fundo localmente ou gerar no cabide com a confirmação de créditos já existente.
A imagem original e seus dados não são sobrescritos. Ao trocar só o tamanho, um
sufixo de tamanho no nome acompanha a alteração; o código é copiado exatamente e
pode ser conferido/editado, sem tentar adivinhar quais dígitos pertencem ao tamanho.

A opção **Adicionar à grade do produto original** conserva o vínculo explícito;
desmarcada, cria um modelo independente. Na mesma grade, tamanho+cor já existentes
são recusados. Quantidade inicial começa em zero. O novo endpoint
`POST /api/inventory/items/{id}/duplicate` exige ADMIN/GERENTE, versão da origem e
conferência, cria identidade própria e grava o item/grade/movimento atomicamente.
A identidade da operação e a impressão digital dos dados confirmados permitem
recuperar a mesma criação após perda da resposta, sem repetir estoque. Reutilizar
essa identidade com outros dados é recusado. O botão **Conferir resultado do cadastro**
reenvia exatamente a operação original. SKU, saldos e vínculos não são aceitos no
objeto de dados editáveis. Para vários novos tamanhos de um produto salvo, continua
existindo a ação separada **Adicionar grade**.

Em **Adicionar grade**, a prévia exige conferir nome, tamanhos, código base opcional e quantidade **por novo
tamanho** (inicialmente zero). O código base é informado explicitamente, sem tamanho:
não tentamos retirar dígitos do código original, pois podem fazer parte do código real.
Cada código novo recebe o tamanho ao final; campo vazio cria variantes sem código.
O código original permanece intacto. Para meios números use ponto (por exemplo `8.5`).

`GET/POST /api/inventory/items/{id}/variants` trabalha somente com o produto escolhido
e sua grade explícita, na mesma cor. Tamanhos já existentes, inclusive inativos, são
preservados e não recebem estoque adicional. Um produto avulso é agrupado com as
novas variantes. Não há associação automática por nome ou código repetido.

No PostgreSQL, lock transacional por grade e locks dos itens serializam criações
concorrentes. Produtos, agrupamento e estoque inicial são uma transação; falhas
revertem tudo. Repetir tamanhos já criados não repete movimentações. Mudança dos dados
salvos desde a prévia retorna 409 e exige nova conferência. Se a conexão falhar, a
interface bloqueia o envio até reler os tamanhos cadastrados. Auditoria e histórico
usam os listeners normais de produtos e movimentações. As operações não fazem
alterações em vendas ou no histórico do produto de origem.

As prévias e leituras ficam em memória enquanto o cadastro está aberto. Reabrir
**Rever foto/etiqueta** conserva a leitura e a edição já feitas, sem disparar IA.
Falhar ou cancelar uma fonte não apaga os dados aplicados pela outra. A original
é exibida junto da imagem recortada/gerada para comparação, mas não é enviada no
cadastro do produto. Na edição de um item, as mesmas sugestões podem ser usadas
com revisão, sem alterar saldos por isso.

## Leitura revisável com IA

Em **Foto e etiqueta → Ler etiqueta**, o leitor aceita câmera ou arquivo
JPEG, PNG ou WebP estático. O serviço compartilhado de visão usa
`VISION_PROVIDER=auto`: prefere `DEEPSEEK_API_KEY` com
`DEEPSEEK_VISION_MODEL=deepseek-flash`; sem essa chave, usa `ANTHROPIC_API_KEY`
com `claude-haiku-4-5`. O ambiente também pode selecionar explicitamente
`deepseek` ou `anthropic`. Não há chave no frontend nem troca de provedor
após erro de uma leitura.

O backend valida os bytes, o formato real, a correspondência com o MIME informado,
o número de quadros e as dimensões. Limites do ERP: 5 MB, pelo menos 64 px por lado,
até 4096 px por lado e 16 megapixels. A imagem é decodificada, orientada, reduzida a
até 1600 px e reencodificada em JPEG sem metadados, somente em memória. Não se salva
a imagem do pedido de leitura em arquivo, cadastro ou banco de dados.

O contrato retorna nome/modelo, marca, tamanho, cor, GTIN, preço, moeda, transcrição,
qualidade de leitura e evidências textuais. Campos sem evidência permanecem nulos.
Códigos GTIN de 8/12/13/14 dígitos passam por conferência do dígito verificador;
um código inválido é removido da prévia, sem tentar corrigir seus dígitos.
Um preço sem moeda identificada também fica vazio: `$` sozinho não identifica a moeda.
A marca escolhida para localizar exemplos não é tratada como marca detectada.

A prévia exibe os campos revisáveis, trechos que sustentam a leitura e possíveis
cadastros com o mesmo código. **Adicionar à conferência** envia os rascunhos para
revisão conjunta no cadastro. O componente também preserva seu modo independente,
que exige revisão antes de **Usar no formulário**. Salvar um exemplo sempre exige
revisão explícita, mesmo no modo integrado. Nenhuma dessas ações cria o produto. A foto
não estabelece SKU, quantidade disponível, entrada, saída ou transferência.

**Salvar exemplo revisado** é uma ação separada. A tela avisa que ela guarda a imagem
sanitizada e os campos corrigidos no ERP para serem enviados como exemplos em
leituras futuras. Não é treinamento de um modelo novo. Exemplos antigos inválidos
são ignorados na leitura; não são apagados automaticamente.

A IA pode errar mesmo quando fornece uma evidência. O GTIN válido não comprova
que os dígitos correspondem à foto, nem a autenticidade do produto. Não há contagem
automática de peças por foto, identificação de falsificações ou associação visual
com o catálogo. O fluxo aqui é de etiquetas; comprovantes dos Correios enviados ao
Telegram usam outro contrato.

Referências: [visão da DeepSeek](https://api-docs.deepseek.com/guides/vision/) e
[visão da Anthropic](https://platform.claude.com/docs/en/build-with-claude/vision).
Os limites acima são os limites locais do ERP, independentemente de limites maiores
disponíveis no provedor.

## Cadastro por foto do produto

**Foto e etiqueta → Adicionar foto** prepara a imagem e as sugestões para o mesmo
cadastro que recebe a etiqueta. Fotografe uma peça estendida inteira. A importação
aceita JPEG/PNG/WebP de até 15 MB/48 MP e reduz a imagem para 1600 px, sem EXIF.
O servidor valida novamente o formato real e os limites de imagem do ERP.

- **Sugerir dados** usa o provedor de visão já configurado, uma foto e até 650 tokens
  de saída. Sugere nome, descrição visual, categoria e cor. Marca e tamanho precisam
  de evidência textual legível; ficam vazios sem ela. A análise não prova autenticidade.
- **Remover fundo · grátis** executa U2NetP (Apache 2.0) em um Web Worker no navegador,
  usando ONNX Runtime Web. Modelo e runtime são carregados sob demanda do próprio
  ERP (aproximadamente 19 MB na primeira utilização). Não existe custo de API por
  recorte nem upload para segmentação. A foto mantém a pose original, centralizada
  em fundo branco. Bordas finas ou fundos semelhantes à roupa podem falhar.
- **Gerar no cabide** é opcional e exige um segundo clique que informa o uso de
  créditos OpenAI. Backend envia uma foto reduzida a 1024 px, prompt fixo, `n=1`,
  `quality=low`, saída JPEG 1024×1024; sem retries nem troca automática de modelo.
  A geração pode alterar estampas, logos ou o corte: a comparação com a original
  e a revisão humana são obrigatórias antes de aplicar. Original/recorte/gerada
  podem ser escolhidas e baixadas sem executar novamente a IA.

O atalho **Gerar foto no cabide** aparece em **Foto e etiqueta** e junto à foto na
**Conferência**, inclusive no celular. Ele reabre a foto já escolhida e a confirmação
de custo; sem foto, pede a seleção ou captura primeiro. Os controles de edição
ficam antes das prévias, no início do modal. Reabrir preserva a geração e o bloqueio
contra repetição de uma tentativa paga. **Adicionar à conferência** usa a imagem
selecionada como miniatura do produto após conferir e salvar o cadastro.

`OPENAI_API_KEY` existe somente no backend, via ambiente ou `/etc/secrets/openai.env`
no Render. `PRODUCT_PHOTO_IMAGE_MODEL` padrão é `gpt-image-1-mini`, escolhido pelo
custo. Em 07/10/2026, a saída low quadrada custa US$ 0,005, além de tokens de entrada.
O custo exibido após a geração é uma estimativa com o uso retornado, não consulta ao
saldo da conta. O modelo tem retirada anunciada para **01/12/2026**: reavaliar preços
antes de mudar a variável; não há fallback pago silencioso.

Os endpoints `/api/product-photo/status`, `/analyze` e `/catalog` exigem ADMIN ou
GERENTE. Não criam produtos, vínculos, códigos ou movimentações. Há limite inicial
por processo de 20 solicitações por usuário/operação/hora e 32 prévias simultâneas.
O cache em memória reutiliza a mesma foto/operação/usuário durante 10 minutos e
bloqueia solicitações sobrepostas ou repetidas após erro; reinícios e múltiplos
processos não compartilham esse cache. Não é idempotência de cobrança durável.
Falha/timeout não causa retentativa automática, e a interface bloqueia nova edição
paga da foto na sessão. Memória de prévias é descartada em novas solicitações após
o prazo, ou no reinício; não há histórico de arquivos de origem no banco.

No cadastro unificado, **Adicionar à conferência** aceita também apenas a foto,
sem nome e sem análise; a revisão é obrigatória no formulário conjunto. No modo
independente do componente, **Usar no cadastro** ainda requer nome e revisão.
Alterar dados ou escolher outra foto reinicia a conferência.
Preço, estoque, código de barras, SKU e variantes nunca são inferidos pela imagem.
O SKU continua sendo gerado pelo cadastro; códigos repetidos não mesclam produtos.
O botão normal de salvar continua responsável por persistir e movimentar o estoque.

Nesta versão a foto escolhida fica em `Item.image_data`, JPEG até 1200 px e cerca de
250 KB, com redução adicional quando necessário, e aparece nas miniaturas existentes.
Não existe galeria nem armazenamento separado de original/alta resolução; use
**Baixar foto escolhida** para conservar a prévia antes de fechar. Para um marketplace
com muitas imagens, migrar a mídia para armazenamento próprio e miniaturas separadas.

Código: `ItemFormModal.vue`, `services/productIntake.ts`, `ProductPhotoAssistant.vue`, `services/productPhoto.ts`, worker de recorte,
`api/endpoints/product_photo.py`, `services/product_photo.py` e contrato correspondente.
Testes usam fornecedores simulados, nunca imagens ou estoque da produção.

Referências: [preço do Mini](https://developers.openai.com/api/docs/models/gpt-image-1-mini),
[edição](https://developers.openai.com/api/reference/resources/images/methods/edit),
[retirada anunciada](https://developers.openai.com/api/docs/deprecations),
[U-2-Net](https://github.com/xuebinqin/U-2-Net) e
[ONNX Runtime Web](https://onnxruntime.ai/docs/get-started/with-javascript/web.html).

## Integridade das movimentações

O serviço de estoque bloqueia a linha do item e relê seus saldos por local antes de
movimentar. Isso evita usar um saldo antigo carregado na sessão antes de outra
transação terminar. As regras são compartilhadas pela API e pelas entradas do bot:

- Entrada/saída/transferência exigem quantidade inteira positiva; ajuste aceita zero.
- Saída exige saldo no local indicado. Saldo disponível no depósito não é consumido
  implicitamente por uma saída da loja.
- Transferência exige locais válidos e diferentes, com saldo suficiente na origem;
  a soma de loja e depósito permanece igual. Não se zera a origem artificialmente
  para adicionar uma quantidade maior ao destino.
- Total divergente dos locais ou saldo negativo exige conferência e ajuste explícito.
  A movimentação não corrige silenciosamente os dados históricos.
- Qualquer saldo ausente (total, loja ou depósito) bloqueia entrada, saída,
  transferência e ajuste com conflito recuperável, sem registrar movimentação.
  O PDV também recusa baixar ou devolver estoque desconhecido, preservando a venda
  e seu estado quando a operação falha. Um zero cadastrado continua sendo zero.
- Lotes de transferências e edições com alteração de estoque são atômicos: se um item
  falhar, nenhum saldo ou metadado do lote é confirmado.
- Novas importações CSV/NF-e colocam o estoque inicial na loja e mantêm depósito zero,
  total coerente e movimento inicial. Dados já existentes não são reclassificados.

Não há migração ou correção automática de saldos históricos nesta atualização.
A conferência dos locais deve usar a contagem real, evitando transferir para uma
localização arbitrária apenas para fazer o total fechar.

O formulário de movimentação permite selecionar loja/depósito também no ajuste
físico, inclusive ajustar a zero. A criação de item avulso e de lotes com várias cores ainda usa
etapas distintas; uma chamada de grade de tamanhos é atômica. Se um item/parte da grade foi criado e a próxima etapa falhar,
o formulário mostra os nomes e SKUs já persistidos, atualiza a lista e bloqueia
repetir aquele cadastro. O operador deve conferir os saldos e movimentar somente
o que faltar. Uma interrupção de rede sem resposta de criação também pede essa
conferência: não se supõe que houve rollback no servidor.

## Conferência dos cadastros e saldos

O botão **Conferir estoque** abre um diagnóstico sob demanda dos itens ativos.
A consulta sinaliza total diferente de loja + depósito, saldos negativos, campos
de saldo ausentes e códigos de barras compartilhados por mais de um cadastro.
Não lê fotos, preços ou dados de clientes para produzir o diagnóstico.

Os contadores abrangem todos os itens ativos, antes da busca e paginação. Um item
pode ter mais de um alerta; a soma dos tipos não equivale à quantidade de produtos
afetados. A tabela contém apenas os produtos com alertas e permite abrir o cadastro
para revisão. Atualizar o painel apenas consulta novamente, sem ajustes automáticos.

Códigos são comparados removendo espaços, tabulações, quebras e espaço não separável.
Zeros à esquerda, pontuação e caixa são preservados, pois códigos alfanuméricos
podem ter significado diferente. Um código repetido é evidência para conferir a
etiqueta e a variante: não é prova de cadastro duplicado e não provoca fusão.

A coluna diferença corresponde ao total cadastrado menos a soma dos locais.
Quando falta algum saldo, a soma/diferença permanece indisponível, sem substituir
o valor ausente por zero. Saldos podem mudar durante a consulta; atualize antes de
decidir o ajuste e faça a contagem física pelo fluxo apropriado.

`GET /api/inventory/diagnostics` exige sessão autenticada e suporta filtros por
tipo, busca literal e paginação limitada. `services/inventory_diagnostics.py`
executa agregações SQL antes da paginação, sem carregar imagens do catálogo.
`test_inventory_diagnostics.py` cobre grupos normalizados, ausência de dados,
paginação, isolamento de inativos, ausência de gravação e somas grandes no PostgreSQL.

### Cadastros com saldo não informado

A lista, o cadastro e as consultas por código/grade aceitam saldos legados nulos.
O ERP exibe **— / Não informado**, mantém os valores originais e permite revisar
metadados do produto. Esses itens têm alerta próprio (`unknown`) e filtro
`status=unknown_stock`; não são classificados como estoque zerado, baixo ou alto.
O resumo acrescenta `unknown_stock_count` sem ocultá-los da quantidade de itens ativos.
Se alguma variante não tem total cadastrado, o total da grade também fica ausente,
em vez de mostrar a soma parcial como saldo completo.

No bot, a consulta preserva saldos ausentes por local, informa quantos cadastros
estão incompletos e separa o subtotal dos valores conhecidos. `nao_informado`
procura o saldo ausente no local solicitado. A agregação considera todos os
produtos filtrados antes da paginação; nenhum resultado ou horário é inventado.

Esta compatibilidade de leitura não é um reparo de dados: não há backfill nem
migração. A restauração de saldos desconhecidos exige conferência física e um
procedimento explícito que preserve o valor anterior ausente. O ajuste comum
continua bloqueado nesses casos, pois seu histórico exige saldo anterior conhecido.


## Idiomas

Lista, filtros, importação, leitor de código, edição individual/em lote, grupos,
transferência, movimentação e exemplos têm interface reativa em português, espanhol
e inglês. `components/inventory/i18n.ts`/`messages.json` guardam o vocabulário local e
reutilizam mensagens comuns do ERP. Números acompanham o idioma selecionado.

Trocar idioma não altera `loja`, `deposito`, tipos de movimento, moedas, códigos,
nomes de produtos/clientes, categorias já armazenadas ou modelos criados pelo usuário.
Mensagens conhecidas do serviço de estoque são traduzidas; detalhes inéditos vindos
do servidor/importação preservam o texto original para permitir diagnóstico.

## Código e testes

- `services/ocr_images.py`: validação e sanitização em memória.
- `services/ocr_service.py`, `schemas/ocr.py`, `api/endpoints/ocr.py`: leitura e contrato.
- `components/inventory/OcrScanner.vue`: câmera, arquivo, revisão e exemplos separados.
- `services/inventory_service.py`: conservação dos saldos, custos e movimentações.
- `tests/test_inventory_ocr.py`: imagens inválidas, evidências, moeda, GTIN, leitura sem
  escrita, exemplos explícitos, conservação e rollback de lotes.
- `OcrScanner.test.ts`: revisão obrigatória, marca não inventada, moeda e idiomas.
- `InventoryFlow.test.ts`: troca de idioma com modal aberto, validação reativa,
  parâmetros intactos, ajuste zero no depósito, cadastro parcial e timeout incerto.
- `tests/test_inventory_postgres.py`: duas saídas simultâneas de oito unidades contra
  saldo dez, com instâncias ORM previamente carregadas: uma saída aceita, outra
  rejeitada por saldo insuficiente, saldo final dois e uma única movimentação.
- `tests/test_inventory_unknown_stock.py`: leitura, filtros, edição de metadados,
  zero conhecido e bloqueio/rollback de movimentações com qualquer saldo ausente.
- `tests/test_assistant_unknown_stock.py`: totais incompletos antes da paginação,
  subtotais conhecidos e distinção entre consulta vazia, zero e saldo ausente.
- `tests/test_pdv_unknown_stock.py` e `test_pdv_unknown_stock_postgres.py`: criação
  e cancelamento sem efeitos parciais; releitura após espera real por lock.
- `tests/test_pdv_stock.py`, `test_pdv_stock_postgres.py` e `test_pdv_stock_audit.py`:
  quantidades exatas, conservação por local, concorrência e auditoria transacional do PDV.

As verificações locais usam imagens sintéticas e respostas simuladas do provedor.
SQLite testa regras e estado. O teste de concorrência foi executado em PostgreSQL
local com schema descartável e remoção ao terminar, usando `ACCESS_TEST_DATABASE_URL`.
Esses testes não comprovam qualidade visual real da IA; ela exige conferência de
resultados reais com revisão humana.

## Estoque no PDV

As baixas de vendas e as entradas de cancelamento usam o mesmo serviço de estoque
das movimentações. Uma venda de catálogo exige produto existente e ativo,
quantidade inteira positiva e saldo suficiente no local informado. O limite por
linha é 9.999.999 unidades, compatível com a coluna de quantidade do PDV.
Itens avulsos não movimentam o catálogo; admitem quantidades positivas com até três
casas decimais, no máximo 9.999.999,999. Nenhuma quantidade é truncada para concluir
a operação. Avulsos não alteram estoque mesmo quando um registro antigo contém um
vínculo de produto.

O servidor bloqueia os produtos por UUID em ordem estável e relê os saldos após
adquirir os locks. Linhas repetidas do mesmo produto consomem o saldo acumulado;
o saldo do depósito não completa uma saída da loja. Um saldo negativo, ausente,
divergente, insuficiente ou acima do limite numérico recusa toda a operação.
Se o segundo item falha, o primeiro não fica baixado: venda, itens, pagamentos,
movimentos, débito de fiado e eventos de auditoria das mutações são revertidos juntos.

O cancelamento bloqueia a venda antes dos produtos e devolve a quantidade ao local
original uma única vez. É possível devolver estoque de um produto que ficou
inativo após a venda. Dados legados sem produto/local ou com quantidade de catálogo
fracionária exigem revisão; o sistema não inventa o local nem arredonda a devolução.
O histórico original é preservado. A permissão de vendas pessoais continua sendo
verificada na leitura. Cancelamentos e demais alterações são exclusivos de Lucas.

Na tela, a busca indica o saldo por loja/depósito e permite escolher o local.
Linhas de locais diferentes permanecem separadas. O carrinho considera todas as
linhas do produto/local, mesmo com preços diferentes, ao limitar a quantidade.
Esses valores são uma referência da consulta, não uma reserva: o servidor
confere o estoque novamente ao concluir. Erros de consulta não são tratados como
produto inexistente nem abrem automaticamente o cadastro avulso.

Conflitos conhecidos preservam o carrinho e os pagamentos para correção. Uma
resposta de rede ausente ou erro de servidor deixa o resultado da conclusão
incerto e bloqueia novo envio daquele rascunho. Confira o histórico antes de limpar
o carrinho e tentar de novo. O POST de criação ainda não tem chave de idempotência;
a trava na tela não garante execução única entre dispositivos ou chamadas diretas.

O gestor documentado em [VENDAS_PDV.md](VENDAS_PDV.md) permite correção, devolução
parcial, estorno integral e exclusão com histórico. Estoque e fiado são ajustados
atomicamente; a prévia identifica o valor a devolver por fora do ERP. Nenhum
reembolso bancário é automatizado. O BI Excel não cria vendas ou baixas no PDV.


## Contagem física por local

Novas sessões de inventário exigem `count_location` explícito: `loja` ou
`deposito`. `location_filter` continua sendo metadado livre e não define o local
contado. A resposta da sessão inclui o novo campo. A migração
`b8c9d0e1f2a3`, após `a7b8c9d0e1f2`, somente acrescenta a coluna nullable:
todas as sessões antigas mantêm `count_location=null`, quantidades, estados e
linhas originais. Não há backfill por suposição, fusão ou remoção de duplicatas.
O downgrade automático é recusado para não perder o escopo das novas contagens.

- A leitura recebe o UUID do produto escolhido e quantidade inteira de zero a
  2.147.483.647. O saldo de referência é apenas o local contado, capturado novamente
  a cada recontagem. O total do item não é usado como saldo daquele local.
- Sessões abertas ou em contagem aceitam leituras; a primeira leitura passa a
  sessão para contagem. A aplicação exige revisão e pelo menos um produto contado.
  Em revisão, é possível retornar à contagem para conferir novamente. Sessões
  aplicadas e canceladas são terminais: não reabrem nem aceitam novas leituras.
  Marcar o status como aplicado diretamente é recusado; somente a aplicação real
  ajusta saldo e registra responsável/movimentações.
- A sessão é bloqueada antes dos produtos; aplicações bloqueiam os produtos por
  UUID em ordem estável. Leituras simultâneas do mesmo produto atualizam uma única
  linha. Duplicatas históricas são detectadas e bloqueiam a aplicação, sem escolher
  um registro arbitrário ou apagá-lo. Todas as alterações do lote são atômicas.
- Após obter os locks, a aplicação confere novamente o saldo atual **do local**
  contra a referência capturada. Se o saldo desse local mudou, retorna conflito
  e pede recontagem. Movimentação somente no outro local não invalida a leitura;
  seu saldo é preservado. Total/local desconhecido ou outro local negativo impede
  a aplicação, sem presumir zero ou redistribuir saldo.
- Sessões antigas sem escopo continuam consultáveis e podem ser canceladas quando
  não forem terminais. Não aceitam leitura ou aplicação: o operador deve iniciar
  outra contagem com local explícito. O editor geral permite consultar saldos nulos
  e editar metadados; restaurar quantidades ausentes exige revisão técnica, não
  correção automática por esta migração.
- Códigos de barras duplicados retornam todos os candidatos. O PDV e o bot não
  escolhem automaticamente o primeiro; movimentações usam o produto identificado.
  O bot também rejeita códigos repetidos entre produtos de uma mesma solicitação,
  tanto ao preparar quanto ao confirmar um lote. Isso não cria unicidade global
  nem altera os códigos já cadastrados.

Não existe atualmente uma tela consumindo o fluxo de sessões; os endpoints e o
wrapper do frontend continuam disponíveis. Clientes antigos da API precisam
informar o novo campo em `POST /api/inventory/sessions` e seguir as transições.

`tests/test_inventory_sessions.py` cobre local, estados, recontagem, histórico,
quantidades, lotes, ambiguidade e rollback em SQLite sintético.
`tests/test_inventory_sessions_postgres.py` valida a migração aditiva, duas leituras
concorrentes, aplicação única, movimentação enquanto se espera o lock e ordem
estável entre sessões com produtos em comum. Esses testes usam apenas schemas
locais descartáveis; não corrigem nem consultam o estoque de produção.

### Vocabulário unificado de marcas, categorias e cores

O estoque compara marcas, cores e categorias sem distinguir maiúsculas, minúsculas,
acentos ou espaços repetidos. Hierarquias usam `Calçados > Tênis`. `PRADA`, `Prada`
e `pRADA` pertencem à marca **Prada**; `EA7 Emporio Armani`, `Emporio Armani` e
`Empório Armani` pertencem a **Emporio Armani**. Os aliases são explícitos:
Armani Exchange, Giorgio Armani e EA7 isoladamente não são unidos automaticamente.
Cores de significados diferentes, como Navy e Azul, também permanecem distintas.

A regra de persistência se aplica a cadastros ORM: formulário, bot, CSV, edição em
lote, duplicação e novas grades. Os filtros reconhecem também grafias antigas e
acentos; a categoria principal inclui suas subcategorias. Não há aproximação por
semelhança de nomes nem união automática de produtos, tamanhos ou grades. SKUs,
códigos de barras e nomes de modelos mantêm suas identidades.

A migração `d6e7f8a9b0c1` consolida somente marca/categoria/cor dos produtos não
excluídos, guardando os valores anteriores em `inventory_taxonomy_snapshot_v1`.
Não altera saldos, IDs, grupos, timestamps, vendas ou histórico. O snapshot é de
recuperação, não uma tabela de uso do aplicativo; uma restauração requer migração
explícita para preservar edições feitas depois. Os filtros também consolidam
valores antigos caso uma integração externa grave diretamente no banco; escritas
SQL externas devem usar as mesmas regras, pois não passam pelo listener ORM.

### Seleção múltipla e identificação visual de grades

**Selecionar** ativa as ações da seleção; **Agrupar** continua disponível dentro
da barra para criar uma grade. **Selecionar todos** inclui apenas os produtos da
visualização atual (e os membros dos cards de grade exibidos), sem adicionar
grupos ocultos.

Somente Lucas vê **Excluir** na barra. O modal lista cada SKU/variante, saldos,
movimentações e vínculos, distinguindo exclusão física de retirada com histórico.
Uma conferência explícita autoriza as operações indicadas. Cada item usa seu
próprio token e a autorização do backend, sem contornar vínculos ou auditoria.
As operações são sequenciais e transacionais **por produto**, não por seleção
inteira. Em falha ou resultado incerto, a sequência para: sucessos permanecem
identificados; os pendentes exigem nova prévia e confirmação. Não há retentativa
automática. Sair da página impede o início de novas exclusões da seleção, mas
não cancela uma requisição já enviada.

Fora de **Ver grades**, os cards mostram um identificador de grade e uma linha
entre vizinhos com o mesmo `group_key`. A linha acompanha as quebras de linha e
o redimensionamento em Quadrados, Compacto e Lista. A numeração é relativa à
lista visível; o nome/código real aparece no tooltip. Cards não adjacentes seguem
identificados, sem linhas atravessando outros produtos. Não se infere grade por
marca, nome, cor ou código de barras, nem se alteram filtros ou ordem dos itens.
