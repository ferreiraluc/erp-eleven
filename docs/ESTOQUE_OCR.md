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
localização arbitrária apenas para fazer o total fechar. O painel de diagnóstico
automático de duplicatas/divergências não foi adicionado nesta entrega.

O formulário de movimentação permite selecionar loja/depósito também no ajuste
físico, inclusive ajustar a zero. A criação de item com estoque inicial ainda usa
etapas distintas. Se um item/parte da grade foi criado e a próxima etapa falhar,
o formulário mostra os nomes e SKUs já persistidos, atualiza a lista e bloqueia
repetir aquele cadastro. O operador deve conferir os saldos e movimentar somente
o que faltar. Uma interrupção de rede sem resposta de criação também pede essa
conferência: não se supõe que houve rollback no servidor.

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
