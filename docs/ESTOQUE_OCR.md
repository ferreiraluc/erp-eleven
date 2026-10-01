# Estoque e leitura de etiquetas

## Leitura revisável com IA

No formulário de produto, **Conferir etiqueta com IA** aceita câmera ou arquivo
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
cadastros com o mesmo código. O usuário precisa conferir e marcar a revisão antes
de **Usar no formulário**. Alterar um campo exige revisar novamente. Esse botão
somente preenche o formulário; o cadastro ainda exige seu botão de salvar. A foto
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
- Lotes de transferências e edições com alteração de estoque são atômicos: se um item
  falhar, nenhum saldo ou metadado do lote é confirmado.
- Novas importações CSV/NF-e colocam o estoque inicial na loja e mantêm depósito zero,
  total coerente e movimento inicial. Dados já existentes não são reclassificados.

Não há migração ou correção automática de saldos históricos nesta atualização.
A conferência dos locais deve usar a contagem real, evitando transferir para uma
localização arbitrária apenas para fazer o total fechar.

O formulário de movimentação permite selecionar loja/depósito também no ajuste
físico, inclusive ajustar a zero. A criação de item com estoque inicial ainda usa
etapas distintas. Se um item/parte da grade foi criado e a próxima etapa falhar,
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

As verificações locais usam imagens sintéticas e respostas simuladas do provedor.
SQLite testa regras e estado. O teste de concorrência foi executado em PostgreSQL
local com schema descartável e remoção ao terminar, usando `ACCESS_TEST_DATABASE_URL`.
Esses testes não comprovam qualidade visual real da IA; ela exige conferência de
resultados reais com revisão humana.


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
  outra contagem com local explícito. O editor geral de produtos ainda não suporta
  todos os saldos nulos legados; esses casos exigem revisão técnica, não correção
  automática por esta migração.
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
