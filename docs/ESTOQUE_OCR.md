# Estoque e leitura de etiquetas

## Movimentações nos cards

Os cards, a lista e as peças de uma grade não oferecem mais a saída rápida
**−1**. Use **Movimentar** para registrar entrada, saída ou ajuste, com as
validações e o histórico existentes. A remoção do atalho não altera saldos nem
apaga movimentos anteriores. **Movimentar** e **Editar** ficam lado a lado nos
cards, inclusive em Quadrados no celular e no desktop, com espaçamento compacto.
Com **Ver grades** ativo, salvar uma edição de produto, movimentação ou transferência
reconsulta as grades exibidas; o total do card e a quantidade de cada tamanho
acompanham o saldo confirmado pelo servidor. O botão **+ Grades** abre o gerenciamento
das peças de uma grade ou dos itens selecionados.

Ao abrir um modal com itens selecionados, a barra flutuante de ações sai da frente
dos controles. Cancelar ou concluir uma edição, transferência, vínculo a lote ou
agrupamento devolve a barra com os mesmos itens marcados, para conferência; **Limpar**
ou desligar **Selecionar** encerra a seleção. Na exclusão, apenas os produtos
efetivamente excluídos deixam de estar marcados. Se uma edição tirar um item da
lista filtrada, a seleção ainda o conta e avisa que está fora da lista atual.
Ajuste os filtros antes de editar, transferir ou gerenciar a grade em lote; essas
ações não abrem com apenas parte dos itens selecionados.

## Busca no catálogo

Ao lado de **Selecionar**, a linha **Visualização** mostra o total de produtos
que correspondem à busca e aos filtros, mesmo antes de terminar a paginação.
**Ver grades** conta somente as peças correspondentes; os outros tamanhos
exibidos para contexto não aumentam esse total. Cada SKU/variante conta como um
item, independentemente da quantidade física disponível.

Durante a busca aparece **Buscando...**; durante a rolagem, **Carregando mais
itens...**, quantidade carregada/total e, ao terminar, **Fim dos resultados desta
busca**. O celular mantém um resumo visível mesmo com os filtros recolhidos.
Falha de uma página preserva os resultados já carregados e oferece nova tentativa,
sem afirmar que a busca terminou nem disparar tentativas contínuas. A listagem
não baixa todas as páginas em segundo plano: usa a rolagem ou **Carregar mais**.
Se uma nova busca falhar, a tela mostra o erro sem exibir como resultado os cards
guardados da busca anterior. O QR `INV-XXXXXX` usa a identidade exata do produto;
a ordenação dessa busca é uma expressão compatível com PostgreSQL, inclusive na
listagem de estoque e na visualização por grades.

### Fotos e consumo de memória

O catálogo pede `include_images=false` nas rotas de itens, grades e sugestões.
Essas respostas contêm `has_image` e omitem o conteúdo da foto original na consulta
SQL. Miniaturas autenticadas são pedidas em lotes de até 12 IDs em
`GET /api/inventory/items/thumbnails`, com no máximo dois lotes simultâneos.
A rota individual continua disponível. Só entram na fila fotos próximas da área
visível; componentes removidos são descartados e IDs repetidos compartilham a
mesma consulta. O navegador mantém no máximo 128 prévias por cinco minutos,
separadas por sessão e versão do item (até ~6 MiB); trocar visualização reutiliza
esse cache. Uma miniatura ocupada pode ser tentada novamente uma vez após 2 s.

O servidor produz JPEG de até 256px/48 KiB, serializa a conversão dos originais e
mantém um cache em memória limitado a 64 prévias. As miniaturas prontas também
ficam persistidas em `thumbnail_data`/`thumbnail_ready`: um lote já preparado usa
uma única consulta leve, sem reabrir as fotos originais, inclusive após deploy.
A primeira abertura de uma foto antiga ainda precisa prepará-la. A sessão de
leitura é fechada antes de esperar/converter. Mudanças na foto invalidam a prévia
por listener ORM e trigger PostgreSQL; alterações de nome/saldo não exigem nova
conversão. A escrita técnica da prévia não muda a data do produto nem gera auditoria
de alteração do cadastro. Fotos inválidas recebem placeholder.

A migração `e7f8a9b0c1d2` cria índices GIN com `pg_trgm` nas expressões usadas
pela busca e índices parciais para facetas/ordenação, somente nos itens não
excluídos. Os índices são construídos de forma concorrente; construções inválidas
interrompidas são recuperadas ao repetir a migração. Buscas antigas são canceladas
no navegador quando substituídas por outra; isso não garante cancelar uma query
que o PostgreSQL já começou. Grades completas deixam de ser buscadas na abertura
do modo comum; são carregadas ao usar grades, seleção ou cadastro.

Ampliar ou editar busca a foto original pela ficha individual. O editor só abre
depois dessa leitura, evitando apagar ou substituir a foto por uma miniatura ao
salvar/duplicar. Nenhuma imagem armazenada é regravada e não há consumo de IA.
A galeria ampliada abre em uma camada fixa sobre a listagem, tanto no celular
quanto no desktop. Fechar pelo ×, pelo fundo ou por Esc devolve a rolagem da
lista; a janela continua podendo ser fechada durante carregamento ou erro das fotos.
As APIs preservam o modo completo por padrão para consumidores existentes;
grades continuam retornando todos os metadados correspondentes, sem paginação.
Os contadores do dashboard são agregações SQL, sem carregar fotos ou cadastros
inteiros em memória.

A busca combina nome/categoria, descrição, marca, cor e **tamanho** no mesmo produto:
`Tênis tamanho 11`, `Armani 7`, `Boss 40`, `Tênis Boss 41`, `Camiseta tamanho S`
e `T-shirt tamanho M`. Aceita maiúsculas/minúsculas, acentos, `tam.`, `tamanho`,
`size` e `talle`. Camiseta e T-shirt são sinônimos na busca; tênis e sneakers também.
Tamanhos de roupas reconhecem as equivalências `P=S`, `G=L`, `GG=XL` e `XXL=2XL`.
Numeração de roupas continua exata: `40` não inclui `40.5`.
SKU/código completo continuam encontráveis, inclusive identificadores curtos.

### Detalhes e palavras-chave na descrição

Em **Novo item/Editar → Organização e limites → Descrição**, registre detalhes
visuais, material, acabamento e outras palavras úteis. Não é necessário repetir
essas informações no nome, SKU ou código de barras. Por exemplo, a descrição
“Camiseta de placa de metal, com logo emborrachado” permite buscar `placa`,
`metal emborrachado` ou `Boss placa tamanho S`, se a marca/tamanho corresponderem.
A ordem das palavras não importa; palavras comuns precisam corresponder ao mesmo
produto, podendo estar em campos diferentes. A busca ignora caixa e acentos,
inclui fragmentos e mantém os sinônimos de tipo de peça e as regras de tamanhos.

Descrições já salvas também participam, sem recadastrar nem sincronizar. Alterar
ou remover a descrição passa a valer na próxima consulta. Vale para itens,
grades e consultas de estoque do bot, com os mesmos filtros, permissões,
contadores e paginação. Nas grades, outros tamanhos exibidos como contexto não
somam como correspondências se não atenderem à consulta. A tolerância a erros
ortográficos continua restrita ao vocabulário descrito abaixo; não há correção
genérica de qualquer palavra da descrição nem interpretação de imagem nesta etapa.

A migração `l4a5b6c7d8e9` adiciona um GIN parcial `pg_trgm` na descrição normalizada,
construído com `CONCURRENTLY`, sem regravar produtos/fotos. O índice combina com
os índices existentes e se atualiza nas gravações normais; não há custo de IA,
varredura de descrições em Python nem carregamento das 50 mil peças no navegador.
O teste PostgreSQL isolado usa 50 mil itens sintéticos e verifica o índice na
listagem paginada e na contagem. Em uma execução local, consultas seletivas de
descrição levaram aproximadamente 0,1–1,4 ms de execução SQL (sem planejamento,
rede, serialização ou renderização). Isso não é SLA de produção: termos muito
curtos ou comuns, volume das descrições e recursos do banco alteram o custo.

### Escrita aproximada e referências de modelo

A mesma interpretação vale para itens, grades e consultas do assistente, antes da
contagem e paginação. Os filtros explícitos de marca, cor, local e tamanho continuam
obrigatórios. Exemplos:

| Busca | Correspondência |
| --- | --- |
| `Y 26`, `Y-26`, `Y26` | Modelo `Y-26-09`, sem interpretar 26 como tamanho |
| `8UB102`, `UB102`, `UB 102` | Referência `UB102` ou `8UB102`, mesmo com outros códigos no nome |
| `AF16548 UB102` | Primeiro os itens com ambas as referências; depois os que compartilham uma delas |
| `calsa` | Calça/calças, sem incluir calçados por essa palavra |
| `tsirt`, `camseta` | Camisetas/T-shirts; `tsirt G` mantém o filtro L/G |
| `Emprio Armani`, `Emporio Armnai` | Emporio Armani |

Erros de uma letra (inserção, remoção, substituição ou troca adjacente) são
comparados com tipos conhecidos e o vocabulário de marcas, categorias e cores
cadastradas. Palavras válidas/fragmentos existentes mantêm seu significado. A
expansão é limitada a oito alternativas por termo e não aplica similaridade a
números, tamanhos ou códigos de barras. Códigos de modelo aceitam separadores e
um único dígito inicial antes de duas ou mais letras e dois ou mais dígitos:
`8UB102/UB102`. Não corrigimos `DN0282` para `DN0281` por distância textual.

Resultados literais precedem aproximações na ordem padrão. A ordenação explícita
por data continua sendo respeitada. São relações **apenas para consulta**: não
fundem produtos, grades ou saldos e não modificam os nomes/SKUs. Números isolados
continuam podendo representar tamanhos; use o modelo completo para desambiguar.

Não há chamadas de IA nem carregamento de fotos/produtos em memória
para filtrar. O vocabulário pequeno é reaproveitado na requisição; as expressões
SQL preservam os índices existentes. Termos muito curtos podem não aproveitar
trigramas, e uma busca sem relação reconhecida ainda pode retornar vazia.

### Equivalências de calçados

A busca aplica a **tabela operacional definida pela loja**, sem substituir a
numeração do produto ou afirmar que fabricantes têm modelagem idêntica:

| US | BR | Boss | EU/IT (D&G) |
| --- | --- | --- | --- |
| 6 | 38 | 39 | 40 |
| 7 | 39 | 40 | 41 |
| 8 | 40 | 41 | 42 |
| 9 | 41 | 42 | 43 |
| 10 | 42 | 43 | 44 |
| 11 | 43 | 44 | 45 |
| 12 | 44 | 45 | 46 |
| 13 | 45 | 46 | 47 |

Cada linha inclui também os meios tamanhos: `chinelo 11` encontra 11/11.5 US,
43/43.5 BR, 44/44.5 Boss e 45/45.5 EU/IT. O tamanho exato na escala buscada vem
primeiro, seguido dos equivalentes, depois dos meios tamanhos. Buscar `11.5`
prioriza os meios tamanhos da mesma linha e também permite conferir os inteiros.
Aceita ponto/vírgula e escala antes/depois do número (`US 11`, `11US`, `43 BR`,
`44BOSS`, `45 EU/IT`). A ordenação por relevância ocorre antes da paginação;
se o consumidor pedir explicitamente ordenação por data, ela é respeitada.

- Indicação de escala no campo tamanho prevalece sobre a marca.
- Sem indicação: 6 a 13 (e seus meios tamanhos) são US. Números maiores usam BR;
  produtos da marca Boss/Hugo Boss usam a coluna Boss, e D&G/DG/Dolce & Gabbana usam EU/IT.
- Na consulta sem escala, aplicam-se as mesmas regras. `Tênis Boss 44` restringe
  a marca e usa sua escala; `Tênis 44BOSS` procura equivalentes entre marcas.
  O filtro separado de marca também orienta a interpretação.
- Expansão apenas em produtos cujo nome ou categoria identifiquem calçados
  (tênis, chinelos, sapatos, sandálias etc.). Roupas e itens sem essa identificação
  mantêm comparação literal, sem conversões. Não extrapola outras tabelas/faixas.
- A consulta preserva tamanho, SKU, código, grade e saldo originais. Não converte
  os cadastros nem sugere que peças aproximadas tenham ajuste garantido.

As rotas de itens e grades usam a mesma interpretação, aplicada antes da contagem
ou paginação. **Ver grades** mostra a grade completa quando uma de suas peças
satisfaz todos os termos e filtros, preservando o contexto dos outros tamanhos;
as grades correspondentes ao tamanho exato aparecem primeiro.
O assistente usa a mesma busca, inclusive quando recebe tamanho como campo
separado, e deve informar a numeração original de cada resultado. A consulta
não faz chamadas a provedores de IA.

No celular (até 600px), a barra reúne voltar, **Estoque**, **Novo**, menu **Mais
ações** e **Filtros**. O painel inicia recolhido e conserva busca/filtros/seleção
ao fechar. Aberto, organiza tags arredondadas em duas linhas: status, marca,
categoria, local, sem grade e ver grades. A seleção recebe destaque azul; textos
longos cabem na tag e o nome completo aparece nas opções. Os modos de visualização
usam ícones com nomes acessíveis, ao lado de seleção e quantidade de resultados.
Ações de importação, etiquetas, conferência e histórico continuam disponíveis no
menu, respeitando o perfil. Desktop preserva filtros visíveis e as mesmas tags.
O filtro de situação usa um único menu com Todos, Baixo, Sem estoque, Excesso,
Inativos e Revisar estoque no celular e no desktop; os números do resumo não
duplicam esses botões. O filtro de categoria inclui **Sem categoria** mesmo quando
nenhuma categoria foi cadastrada, para localizar e classificar itens antigos;
categorias vazias ou só com espaços também entram nessa escolha.
Em **Ver grades**, a grade mostra outras peças como contexto, mas selecionar a
grade com **Sem categoria** ativo inclui apenas as peças sem categoria na edição
em massa. **Inativos** mostra somente os membros inativos da grade.

Uma busca ou filtro sem correspondências oferece **Limpar Filtros**, removendo
texto, status, marca, categoria, local e seleção de itens sem grade. O modo de
visualização e agrupamento é preservado. Uma lista vazia sem filtros permite
**Novo item**, sem afirmar que não existem outros produtos fora da seleção.

## Lotes de recebimento

**Estoque → Mais ações → Lotes de recebimento** organiza chegadas com nome livre,
data de recebimento e descrição. Por exemplo, “Leva 1” e “1ª leva do container”.
Em **Novo lote**, escolha o intervalo de **cadastro** e use **Buscar produtos**;
confira a lista, retire os itens indesejados e confirme. A consulta inclui todos
os cadastros do período, inclusive inativos, sem depender da página do estoque
carregada. Limites: 93 dias e 1000 produtos por seleção; períodos maiores pedem
um intervalo menor. As datas são dias inteiros em Brasília. No PostgreSQL, os
limites são convertidos para os timestamps UTC legados antes de consultar o índice.

Para escolher manualmente, use **Selecionar** nos produtos e **Vincular a lote**.
Pode criar um lote ou usar **Vincular seleção** em um já existente. **Conferir**
permite editar nome/data/descrição, adicionar produtos por outro período/seleção
e retirar um vínculo. **Ver no estoque** aplica o lote junto dos demais filtros;
**Limpar filtro** sai dele. Em **Ver grades**, aparecem somente membros daquele
lote, sem misturar tamanhos recebidos em outra chegada. A busca e os contadores
continuam no servidor, antes da paginação.

Um produto pode estar em várias chegadas, mas só uma vez em cada lote. A operação
não modifica família, fotos, SKU, data de cadastro, saldo ou movimentos. Este é
um agrupamento de cadastros: **não representa quantidades recebidas por lote nem
rastreabilidade física de unidades**. Entradas de reposição continuam em Movimentar.
Excluir um produto mantém a identificação histórica no lote; retirar do lote
remove apenas o vínculo. Consultas exigem login; alterações seguem ADMIN/GERENTE,
com auditoria de modificações. Repetir uma confirmação após falha de rede não
repete o lote nem seus membros. O servidor valida todos os IDs na mesma transação.

Migração `j2e3f4a5b6c7`: tabelas de lotes e vínculos, índices e FK que preserva o
nome/SKU histórico quando um produto sem vínculos operacionais é excluído de vez.
Nenhum produto existente é agrupado automaticamente durante o deploy.

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
operacionais; para venda fora do acesso, omite referência, notas, motivo livre e
autor, mantendo quantidades e saldos. Vendas excluídas aparecem somente para
Lucas, inclusive nos totais e detalhes financeiros deste histórico; os demais
perfis conservam o movimento de estoque sem os dados privados da venda.
As listagens `GET /api/inventory/movements` e `/movements/item/{id}` usam a mesma
permissão por página: movimentos PDV fora do acesso retornam `reference_id`,
`reason`, `notes`, `created_by` e `unit_cost` vazios. Quantidade, saldos, locais,
datas e identificação do produto continuam presentes; movimentos manuais mantêm
seus dados. Referências antigas UUID em hexadecimal ou maiúsculas são comparadas
sem reescrever o identificador histórico. A ocultação ocorre somente na resposta.
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
Ao selecionar **S → 2XL**, por exemplo, a peça branca S (ou P) origina S, M, L, XL e 2XL
no mesmo grupo, com foto, marca, descrição e preços compartilhados. O tamanho da
peça base é preservado se estiver fora do modelo escolhido. Sem outras cores
selecionadas, todas as variações usam a cor da peça. É possível cancelar a grade
sem perder os dados e cadastrar somente a peça. O estoque informado na grade é
**por variação**, com total visível antes da confirmação.

Essa opção monta uma grade no novo cadastro. Para produtos já salvos, use as ações
descritas abaixo. Códigos de barras iguais não provam identidade. O cadastro
unificado mantém a regra de negócio da grade: **código de barras base + tamanho**
(por exemplo, `789123S`, `789123M`, `789123XL`), além de um SKU independente por
variação. A prévia mostra cada código resultante, inclusive na matriz de cores e
tamanhos. No produto avulso o código permanece como informado. Os tamanhos de uma
solicitação são normalizados e
deduplicados no backend. Cada chamada de criação de grade confirma produtos e
movimentações iniciais na mesma transação, com rollback se uma movimentação falhar.

O aviso de código de barras compartilhado no cadastro acompanha apenas o código
atual: trocar ou limpar o campo descarta respostas anteriores, inclusive ao voltar
ao mesmo código. Fechar a janela encerra essa verificação. Na edição, o próprio
produto é desconsiderado; o aviso continua informativo e não impede salvar um
código compartilhado após conferência.

**Nome das grades automáticas:** a tela mostra o nome do modelo a partir do membro
mais antigo disponível na grade, retirando somente o sufixo que corresponde ao seu
tamanho. Por exemplo, `Tênis Givenchy DN0281 11` aparece como `Tênis Givenchy DN0281`.
A grafia e os códigos do modelo são preservados; nomes personalizados continuam
como definidos. Isso vale também para grades antigas com identificadores UUID,
sem migração, alteração de produtos ou fusão por semelhança de nomes. O `group_key`
continua sendo a identidade interna para vínculos, expansão, linhas e operações.
Títulos, edição e avisos usam o nome legível. Ao agrupar produtos selecionados,
o seletor **Grade de destino** lista as grades pelo nome e envia a chave da opção
escolhida; **Criar uma nova grade** permite digitar um novo nome.

### Duplicar produto e adicionar cores/tamanhos a uma grade existente

Em **Estoque → editar produto**, os perfis ADMIN/GERENTE podem escolher **Duplicar
produto** (cadastro completo preenchido) ou **Adicionar grade** (mesmo editor de tamanhos, cores, modelos salvos e quantidades do novo cadastro). Exemplo: abrir o tênis 9 e criar o 8 sem reenviar a foto.
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

O seletor **Vínculo com o produto original** oferece **Adicionar à grade do produto original**
ou **Criar um modelo independente**, conservando a escolha explícita de família. Na mesma grade, tamanho+cor já existentes
são recusados. Quantidade inicial começa em zero. O novo endpoint
`POST /api/inventory/items/{id}/duplicate` exige ADMIN/GERENTE, versão da origem e
conferência, cria identidade própria e grava o item/grade/movimento atomicamente.
A identidade da operação e a impressão digital dos dados confirmados permitem
recuperar a mesma criação após perda da resposta, sem repetir estoque. Reutilizar
essa identidade com outros dados é recusado. O botão **Conferir resultado do cadastro**
reenvia exatamente a operação original. SKU, saldos e vínculos não são aceitos no
objeto de dados editáveis. Para vários novos tamanhos de um produto salvo, continua
existindo a ação separada **Adicionar grade**.

Em **Adicionar grade**, a mesma tela de grade do cadastro novo recebe os dados da
matriz já salva. Escolha modelos de tamanhos, adicione/remova cores e tamanhos,
remova combinações pelo × e ajuste quantidades por cor, tamanho ou linha. A prévia
mostra só as combinações novas; as existentes (inclusive inativas) aparecem como
**estoque preservado** e não recebem nova entrada. Quantidades começam em zero.
Fotos, marca, descrição, preços e demais dados vêm da matriz; o nome do modelo e
o código base são conferidos antes de criar. Para alterar os dados da própria
matriz, salve a edição antes de abrir Adicionar grade.

O código base é informado explicitamente, sem tamanho: não retiramos dígitos do
código original, pois podem fazer parte do código real. Cada código novo recebe o
tamanho ao final; campo vazio cria variantes sem código. O código original permanece
intacto. O endpoint aceita até 250 combinações tamanho/cor, com até 1.000.000 unidades
por combinação. Tamanhos e cores equivalentes são comparados antes de criar.

`GET /api/inventory/items/{id}/variants?all_colors=true` retorna o contexto de todas
as cores da família explícita. `POST` aceita uma matriz de `variants` com `size`,
`color`, `quantity`; o contrato anterior `sizes` permanece compatível na cor da
origem. Matriz, vínculo e movimentos são criados atomicamente. Repetir a chamada
não repete entradas de combinações existentes. Uma resposta incerta bloqueia a
edição até **Conferir tamanhos cadastrados**, que relê a matriz antes de nova revisão.

A leitura da prévia carrega a foto original somente do produto escolhido, junto
dos dados usados na conferência e no token de versão. As demais peças da grade
são consultadas apenas pelos campos do resumo de variantes, sem carregar fotos,
preços ou saldos e sem uma consulta adicional por peça. A identidade, ordem e
inclusão de tamanhos inativos permanecem iguais.

Na confirmação de novos tamanhos ou de uma duplicação, as mesmas linhas da grade
continuam bloqueadas na mesma ordem, inclusive outras cores e itens inativos.
A consulta não carrega as fotos dos demais membros: relê a foto original da
origem depois dos locks, preservando a verificação de versão. Uma foto alterada
durante a espera exige nova prévia. A resposta de novos tamanhos é preparada
antes do commit para não recarregar cada produto durante a serialização;
os campos e a confirmação transacional permanecem iguais. A duplicação continua
retornando o cadastro completo criado e respeitando sua identidade de operação.
`test_inventory_write_reads.py` verifica essas leituras e os contratos em SQLite
e PostgreSQL isolado, incluindo alteração concorrente da foto da origem.

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

### Seletores no cadastro e na etiqueta

Marca e marca de referência da etiqueta usam `ErpDropdown`, compartilhado com
categoria, subcategoria, unidade, moedas, vínculo de duplicação, destino de
quantidades e seleção de recebimento. O estilo segue os seletores do cabeçalho:
contorno arredondado, seta e lista com opção ativa. Campos editáveis aceitam marca
nova; escolher uma sugestão aplica seu valor imediatamente. IDs são únicos por
instância, inclusive com o cadastro original e sua cópia abertos. A lista permanece
no modal, respeita o foco e fecha por escolha, toque externo ou Escape; perder foco
sem destino em um toque não descarta a escolha. Setas/Home/End e Enter permitem
uso por teclado. Marca de referência orienta os exemplos, mas não é preenchida
como marca detectada pela IA sem evidência da etiqueta.

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

Cada produto pode ter **até cinco fotos**: uma principal e quatro adicionais.
No cadastro novo, a galeria aparece em **Foto e etiqueta/Conferência**; nos produtos
salvos, também na aba **Foto**. É possível selecionar vários arquivos, fotografar,
remover uma foto e escolher a principal. A remoção da principal promove a seguinte.
Clicar na foto do estoque abre a galeria; só uma imagem ampliada é renderizada por vez.
A edição/geração por IA continua sendo uma ação opcional sobre a foto principal,
com as confirmações e limites existentes; adicionar fotos não chama provedores de IA.

A principal continua em `Item.image_data`. As adicionais ficam na coluna JSON
**deferred** `additional_images`, fora das respostas de catálogo, PDV e ficha comum.
`GET /api/inventory/items/{id}/photos` busca as adicionais somente ao abrir a galeria
ou o editor, com autenticação e bloqueio de produtos excluídos. JPEG/PNG/WebP novos
são comprimidos no navegador (até 1200 px e 340.000 caracteres de data URL por foto,
aproximadamente 250 KB de arquivo). O backend confere formato real, dimensões,
quantidade e tamanho. Processamento e miniaturas de 128 px são sequenciais.
A galeria não mantém um cache global de originais no navegador ou no servidor.

Falha ao buscar as fotos bloqueia o salvamento do editor até tentar novamente;
edições comuns e clientes antigos preservam as adicionais. Fotos inalteradas não
são reenviadas ao atualizar nome/preço. Duplicação e grades herdam a galeria da matriz;
a conferência de versão detecta mudança nas fotos. Grades usam uma escrita da
coleção com um único parâmetro de imagens, evitando um buffer grande por variante.
A exclusão do catálogo limpa a galeria e preserva o histórico existente.

### Foto principal por cor na edição em lote

Em **Selecionar → Editar Massivo → Fotos por cor**, escolha uma cor no dropdown
**Aplicar foto a** e use **Enviar foto** ou **Câmera**. Todos os tamanhos daquela
cor dentro da seleção recebem a mesma foto principal. Maiúsculas, acentos e espaços
não separam as cores. **Todos os selecionados** mantém a troca compartilhada.
É possível preparar fotos para várias cores e conferir os produtos de cada foto
antes de **Salvar**; desfazer uma foto preparada mantém a foto já salva no banco.
Enviar novamente para a mesma seleção substitui a preparação anterior.

As fotos ficam vinculadas aos IDs selecionados no momento do envio. Renomear uma
cor depois não transfere sua foto para outros produtos. O editor mostra a cor e os
itens atuais na conferência. Produtos fora da seleção, fotos adicionais, família,
estoque e preços são preservados, salvo outras alterações explícitas no mesmo modal.
A troca substitui a principal; não acrescenta a imagem antiga à galeria.

As imagens são preparadas sequencialmente com os limites da galeria, sem IA,
e o botão Salvar aguarda o processamento. São até 20 fotos distintas por edição;
cada foto atende até 2.000 IDs. `PATCH /api/inventory/items/batch/photos` valida os
grupos, não aceita IDs repetidos ou fora da seleção e usa a mesma transação/locks
dos metadados e ajustes de estoque. O caminho próprio impede que um servidor ainda
antigo ignore as novas fotos durante um deploy. Nenhum original ou galeria é lido
para substituir as capas; cada arquivo é enviado e vinculado uma vez por grupo,
invalidando as miniaturas. A auditoria registra os IDs e a troca, sem guardar a
imagem no evento. O armazenamento final continua sendo por produto, como no cadastro.

A migração `k3f4a5b6c7d8` acrescenta uma coluna nullable, sem regravar as imagens
anteriores. Não existe armazenamento separado da foto original em alta resolução;
use **Baixar foto escolhida** para conservar a prévia da IA. Cada variante possui
sua própria galeria no banco; imagens adicionais de grades não têm deduplicação de
armazenamento. Para um marketplace com muitas imagens, migrar mídia para object
storage é uma evolução separada. Veja [medição de desempenho da galeria](DESEMPENHO_GALERIA.md).

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

### Nome do produto e códigos de modelo

O nome/título preserva as maiúsculas e minúsculas escolhidas na conferência:
`Tênis Givenchy DN0281`, `TÊNIS GIVENCHY DN0281` e `Tênis Givenchy dN0281`
são salvos como digitados, sem capitalizar palavras automaticamente. O cadastro,
a edição, a criação de grades e o bot removem apenas espaços redundantes; a grade
continua acrescentando o tamanho ao nome. Duplicação e novos tamanhos também
preservam a grafia revisada. Busca e verificação de duplicatas continuam ignorando
diferenças de caixa, sem alterar o texto exibido.

Marcas, cores e categorias seguem o vocabulário unificado abaixo. A correção não
reescreve títulos antigos, pois a grafia original não pode ser deduzida com segurança.
Um título antigo pode ser editado e salvo com o código desejado.

### Vocabulário unificado de marcas, categorias e cores

O estoque compara marcas, cores e categorias sem distinguir maiúsculas, minúsculas,
acentos ou espaços repetidos. Hierarquias usam `Calçados > Tênis`. `PRADA`, `Prada`
e `pRADA` pertencem à marca **Prada**; `EA7 Emporio Armani`, `Emporio Armani` e
`Empório Armani` pertencem a **Emporio Armani**. Os aliases são explícitos:
Armani Exchange, Giorgio Armani e EA7 isoladamente não são unidos automaticamente.
Cores de significados diferentes, como Navy e Azul, também permanecem distintas.

A regra de persistência se aplica a cadastros ORM: formulário, bot, CSV, edição em
lote, duplicação e novas grades. Os filtros reconhecem também grafias antigas e
acentos; a categoria principal inclui suas subcategorias. A busca corrige pequenos erros em tipos conhecidos de produto, conforme a seção de
aliases. Não há união automática de produtos ou grades por semelhança de nomes. SKUs,
códigos de barras e nomes de modelos mantêm suas identidades.

A migração `d6e7f8a9b0c1` consolida somente marca/categoria/cor dos produtos não
excluídos, guardando os valores anteriores em `inventory_taxonomy_snapshot_v1`.
Não altera saldos, IDs, grupos, timestamps, vendas ou histórico. O snapshot é de
recuperação, não uma tabela de uso do aplicativo; uma restauração requer migração
explícita para preservar edições feitas depois. Os filtros também consolidam
valores antigos caso uma integração externa grave diretamente no banco; escritas
SQL externas devem usar as mesmas regras, pois não passam pelo listener ORM.

### Seleção múltipla e identificação visual de grades

**Selecionar** ativa as ações da seleção; **+ Grades** aparece na barra para
vincular produtos a uma grade existente ou criar uma nova. **Selecionar todos** inclui apenas os produtos da
visualização atual (e os membros dos cards de grade exibidos), sem adicionar
grupos ocultos.

### Gerenciar produtos em grades existentes

Uma grade pode reunir tamanhos e cores diferentes do mesmo modelo. No card de uma
grade, **+ Grades** abre a gestão dos membros: é possível buscar um produto avulso,
vinculá-lo à grade e remover apenas um membro. No card de um produto avulso,
**Vincular à grade** mostra grades semelhantes e permite buscar outra pelo nome ou
referência. Ao selecionar uma peça e tocar em **+ Grades**, a gestão permite
vinculá-la, transferi-la ou removê-la da grade. Com várias peças avulsas
selecionadas, **+ Grades** permite vinculá-las a uma grade existente ou criar
uma nova; a criação exige ao menos duas peças. Se todas as peças selecionadas
já pertencem à mesma grade, abre-se a gestão dessa grade. A escolha e a
confirmação são explícitas.

As sugestões comparam o nome do modelo, marca, categoria e unidade, ignorando
apenas os sufixos de tamanho/cor que correspondem aos campos do próprio item.
Em cadastros antigos sem tamanho preenchido, somente letras de tamanho conhecidas
no fim do nome podem ser retiradas; números permanecem parte do modelo.
Assim, `Boné Boss 2001020` mantém `2001020` como parte do modelo e pode sugerir
outra cor. Código de barras igual, sozinho, não cria nem sugere vínculo. A busca
e as sugestões são limitadas e carregadas ao abrir a gestão, sem consultar cada
card da listagem. Se não houver sugestão, a busca manual continua disponível.
As sugestões gerais da barra **Selecionar** consideram até 1.000 avulsos recentes;
o painel de uma peça ou grade faz busca dirigida no catálogo, e a busca manual
permite encontrar candidatos fora desse recorte.
Em grades geradas com o nome da primeira cor, o título passa a mostrar só o modelo
quando a grade ganhar outras cores; a chave interna não muda.
No cadastro de uma grade com várias cores, o nome usado para todas as variações
retira apenas os sufixos de tamanho e cor presentes nos campos da peça inicial,
mantendo a referência numérica do modelo.

Vincular, transferir para outra grade ou remover o vínculo exige ADMIN/GERENTE.
O backend confere que a grade de destino existe, que a combinação tamanho/cor
ainda não está nela e que o vínculo do produto não mudou desde a conferência.
Uma divergência pede atualização da lista antes de tentar novamente. Essas ações
alteram somente o `group_key`: não criam produto, não ajustam saldos e não apagam
vendas, movimentações ou histórico. O SKU e o código interno permanecem os mesmos.

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

### Seleção por toque e janelas de cadastro

No touchscreen, deslizar sobre os cards mantém a rolagem nativa; a seleção é feita
por toque. Arrastar para selecionar continua disponível com mouse. Os listeners
pertencem a um único gesto e são removidos em cancelamento, perda de foco, saída da
seleção e desmontagem. A supressão do clique pós-arraste vale apenas para um card
na mesma lista e expira imediatamente; não captura uma confirmação posterior em
um modal. Ver [navegação e confirmações do cadastro](UI_MODAIS.md#cadastro-e-grade-navegação-e-confirmação).

### Remover variações antes de cadastrar a grade

Após selecionar um modelo, como **S → 2XL**, a prévia tem um **× em cada linha**.
Remover P e M deixa apenas L, XL e 2XL para criação. Com várias cores, o × remove
somente aquela combinação de tamanho e cor. **Restaurar variações removidas**
recupera as linhas; aplicar um modelo de tamanhos novamente também refaz a prévia.
O contador e o estoque inicial total consideram apenas as linhas restantes.
Remover todas bloqueia a criação, sem cadastrar uma peça avulsa por engano.

A exclusão é apenas da prévia: não apaga produtos existentes nem altera os modelos
salvos no navegador. Durante o envio ou após uma criação parcial/incerta, a seleção
fica protegida pelo fluxo de recuperação existente.

### Ordem de cadastro e conferência de quantidades

O seletor **Ordem padrão → Adicionados mais recentemente** ordena por data de
criação, sem confundir edição ou movimentação com cadastro novo. A ordem inicial
continua a mesma. A API aplica a ordenação antes da paginação, com desempate por ID;
busca, filtros e carregamento progressivo permanecem ativos. Em **Ver grades**, a
posição do grupo considera o cadastro mais recente entre suas variações visíveis.
Limpar filtros conserva a ordem escolhida; selecione **Ordem padrão** para voltar.

No cadastro de um novo produto com grade, cada linha da prévia tem **Qtd.** editável.
**Estoque inicial por tamanho** continua sendo o padrão das linhas sem ajuste.
**Aplicar quantidade a** permite definir todas as variações, uma cor em todos os
seus tamanhos ou um tamanho em todas as cores. O botão **Aplicar** substitui apenas
as quantidades das linhas selecionadas e presentes na prévia; não restaura linhas
removidas. Alterar o padrão não apaga ajustes individuais. Restaurar uma variação
recupera seu ajuste anterior; sair do modo grade descarta esses ajustes.

A conferência mostra variações (cadastros/SKUs), peças e grades completas por cor.
Uma grade completa equivale a uma peça de cada tamanho **selecionado naquela cor**;
sua quantidade é o menor saldo entre essas linhas. Por exemplo, cinco tamanhos em
branco com 3 peças cada, azul com 4 e preto com 8 somam **15 variações, 75 peças e
15 grades completas**. Quantidades desiguais podem deixar peças fora de conjuntos
completos. Zero cria a variação sem entrada de estoque; não remove o tamanho.

A API `POST /api/inventory/items/grade` aceita `stock_by_size`, com quantidades
inteiras não negativas por tamanho. O campo é opcional; consumidores anteriores
continuam usando `initial_stock`. Tamanhos desconhecidos/repetidos no mapa e
quantidades inválidas são recusados antes de gravar. Cada chamada de grade mantém
itens e movimentos na mesma transação; o fluxo de recuperação de criação parcial
entre cores permanece. As quantidades finais são lançadas no local escolhido.
O frontend usa a rota equivalente `/items/grade/quantities`, para que um backend
ainda anterior à atualização recuse o pedido em vez de ignorar as quantidades.
Essa edição se refere à prévia de **Novo item**; adicionar tamanhos a um produto já
salvo continua usando seu fluxo de conferência próprio.

Na seleção múltipla da listagem, a barra também informa quantas grades distintas
estão representadas e quantas peças pertencem **aos itens selecionados**, somando
loja e depósito. Não inclui automaticamente outros tamanhos do grupo. Se algum
saldo não estiver confirmado, o total aparece como **Não informado**. Essa contagem
de grupos existentes é distinta dos conjuntos completos calculados na prévia.


## Correção de nomes, tamanhos e busca (15/10/2026)

**Selecionar → Editar Massivo → Corrigir nomes em lote** permite localizar uma
palavra/trecho e substituí-la nos nomes selecionados, ignorando caixa. A prévia
mostra antes/depois; **Aplicar correção aos nomes** apenas prepara a edição,
e **Salvar** confirma no backend com as permissões e auditoria existentes.
`Biss → Boss` mantém `Y-26-09` e o tamanho de cada item. Não interpreta expressões
regulares, não altera palavras parciais nem sobrescreve códigos/modelos por similaridade.

Nos formulários de estoque, os campos numéricos têm +/− em celulares e telas de toque.
Eles respeitam os limites de cada campo e não focam o texto ao tocar nos botões.
Na edição em lote, o motivo é opcional; o histórico registra o responsável e um
motivo contextual quando o campo fica vazio. Os controles não movimentam estoque
antes da confirmação do formulário.

**DolceGabbana, Dolce&Gabbana, D&G e DG** usam **Dolce & Gabbana** como marca.
Tamanhos de roupa usam **S (P), M, L (G), XL (GG), 2XL (XXL)**. Criação, duplicação,
grade, importação, filtros e busca compartilham as equivalências. Grades antigas
salvas no navegador são interpretadas com os mesmos tamanhos; uma grade não cria
um novo S quando já contém P. Quantidades conflitantes para P e S na mesma
requisição são rejeitadas para evitar perda de quantidade.

A migração `i1d2e3f4a5b6` corrige marcas e tamanhos dos produtos não excluídos em
lotes de 500, sem carregar fotos. Ajusta o sufixo do nome somente quando ele
corresponde exatamente ao tamanho antigo, por exemplo `DN0281 P → DN0281 S`.
Preserva ID, SKU, códigos de barras já impressos, grupos, saldos, vendas,
movimentações e datas. Registra antes/depois em `inventory_catalog_snapshot_v2`.
Se já existem dois cadastros equivalentes na mesma grade, ambos são preservados:
a migração não soma saldos nem exclui produtos automaticamente.

A busca reconhece `camseta`, `tsirt`, `t-sirt` e sinônimos de camiseta/T-shirt.
`tsirt G` encontra camiseta/T-shirt L. Calçados mantêm suas escalas numéricas e
meios tamanhos. A tolerância posterior para marcas e referências de modelo está
descrita em **Escrita aproximada e referências de modelo**, acima. Os filtros
continuam no SQL antes da paginação, sem IA nem leitura de fotos para pesquisar.

## Visualização do estoque no celular (16/10/2026)

Em telas de até 600 px, tocar no ícone **Quadrados** seleciona essa visualização
e abre um dropdown com **Zoom** em três posições: quatro, três ou duas colunas.
O controle fica sobre os produtos, sem acrescentar altura ao cabeçalho. Tocar
novamente no ícone, fora do dropdown, mudar de visualização ou pressionar Escape
fecha o controle. Os botões −/+ também mudam a posição. O padrão
continua sendo duas colunas com os detalhes atuais; a preferência de zoom fica
salva naquele navegador. Se os filtros estiverem recolhidos, abra **Filtros** para
acessar o ícone. O ajuste não altera a busca, a seleção nem os produtos já carregados.

Nas posições menores, cada card prioriza foto, nome, cor, tamanho e saldo total
(loja + depósito). Movimentar e Editar aparecem como ícones identificados; os
vínculos e indicadores de grade continuam visíveis. Amplie o zoom para conferir
os demais dados e a separação dos saldos por local. Quatro colunas permitem ver
oito cards em duas linhas no espaço do print de referência (408 × 622 px), mas
a quantidade inteiramente visível depende da altura da tela e do texto ampliado.

**Lista** ganhou miniaturas de 26 px dentro das linhas de 32 px já existentes.
No celular, prioriza nome, tamanho e saldos, com as ações em ícones. Tocar na
miniatura abre a foto; itens sem foto mostram um ícone neutro. As imagens usam
o carregamento progressivo e o cache limitado existentes; o original só é
solicitado ao abrir a foto ou a edição. **Compacto**, **Ver grades** e o tamanho
dos cards em tablets/desktop preservam seus controles anteriores; o zoom é
exclusivo dos quadrados individuais no celular.


## Edição em lote: cor e conferência de estoque (17/10/2026)

Em **Selecionar → Editar Massivo**, a seção **Estoque por item** abre com os saldos
atuais e controles **− / quantidade / +**, também no computador. Escolha **Loja** ou
**Depósito**; as alterações feitas em cada local permanecem na prévia ao alternar.
Cada linha informa a **quantidade final** naquele local, e o resumo soma as peças
selecionadas dos dois locais. Zero é um saldo válido; saldo desconhecido permanece
bloqueado e nunca vira zero automaticamente.

**Aplicar quantidade a** prepara todos os selecionados, somente uma cor ou somente
um tamanho. **Definir quantidade** substitui o saldo na prévia; **Somar ou retirar**
modifica a quantidade que está na prévia. Um resultado negativo/inválido recusa a
aplicação inteira, sem recortar saldos para zero. É possível conferir e ajustar
qualquer linha depois. **Aplicar** não salva: somente **Salvar** confirma o lote.

Em **Campos compartilhados → Cor para vários itens**, digite/escolha a cor e clique
em **Aplicar cor a todos**. A cor preenche os campos individuais, que ainda aceitam
exceções antes de salvar. Cores e tamanhos continuam usando as equivalências do
catálogo; nomes, fotos, códigos e vínculos de grade não são recriados.

O motivo de estoque é **opcional**, tanto compartilhado quanto por item. Quando
omitido, o movimento registra **Conferência de estoque — edição em lote**, com ator,
data, local e saldos antes/depois. Não é necessário preencher um motivo para cada
produto. O endpoint anterior de entrada/saída em lote também aceita motivo vazio e
continua disponível para versões antigas; seus movimentos usam motivo contextual.

A API **PATCH /api/inventory/items/batch/quantities** recebe `stock_adjustments`,
com quantidades finais de loja/depósito e os três saldos vistos na abertura.
Todos os produtos são bloqueados em ordem de ID, e esses saldos são relidos e
comparados **antes de alterar qualquer dado**. Uma venda, transferência ou outro
ajuste posterior à prévia devolve conflito 409 e recusa o lote inteiro: reabra a
edição para conferir. Produtos removidos, IDs duplicados/fora da seleção e mistura
de quantidade final com deltas também são recusados. Alterações de cadastro e
movimentos ficam na mesma transação. Saldo inalterado não cria movimento artificial.
A rota específica impede que um backend antigo ignore as novas quantidades.

Em **Ver grades**, a foto ocupa **112 × 112 px** no computador/tablet e **80 × 80 px**
no celular, sem recortar a peça. Tamanhos e ações ficam ao lado/abaixo, e expandir a
grade mantém os itens dentro do mesmo card. Continua usando a miniatura existente;
não carrega fotos originais nem as imagens extras na listagem.

Validação: `test_inventory_bulk_edit.py`, `test_inventory_bulk_edit_postgres.py`
(concorrência real com duas prévias antigas), `BulkEditModal.test.ts` e
`InventoryFlow.test.ts`. Nenhuma migração de banco ou ajuste em produção é necessário.

### Edição completa em lote e referências curtas

Em **Selecionar → Editar Massivo**, **Dados do produto em lote** permite substituir
ou limpar descrições e acrescentar texto ao final, preservando as descrições
individuais. O campo escolhido pode ser aplicado a todos os selecionados, por cor
ou tamanho, com revisão individual antes de Salvar. Também estão disponíveis
marca, categoria, unidade, localização, fornecedor, família/grade, moedas,
limites de estoque e situação ativo/inativo. Os controles existentes continuam
responsáveis por nomes (inclusive substituição de trechos), tamanhos, cores,
preços, foto principal por cor e saldos por local. Alterar a moeda **não converte**
o valor. Galerias adicionais continuam no editor individual.

**Códigos de barras em lote** oferece digitação/leitor USB por item (Enter avança),
câmera e prévia de preenchimento com o mesmo código base ou base + tamanho
canônico: `00123` + P resulta em `00123S`. Zeros à esquerda são preservados.
Por padrão só preenche vazios; é possível revisar a substituição dos existentes.
A prévia não salva sozinha. Códigos repetidos **entre os selecionados** são avisados,
mas permitidos: não unem produtos. Base + tamanho é uma referência interna,
não um EAN/GTIN atribuído pelo fabricante. Câmera depende da permissão do aparelho.

Cada produto recebe `inventory_code` no formato `INV-XXXXXX`, com seis símbolos
maiúsculos legíveis (letras/números, sem 0/O/1/I). Esta é a referência curta exibida
no catálogo, PDV e histórico. UUID e `sku_internal` anteriores permanecem intactos;
a busca aceita ambos, assim como o novo código e seus seis caracteres finais. O código curto é
imutável pela API de edição e não substitui o código de barras comercial.

A migração `m5b6c7d8e9f0` preenche os produtos existentes em lotes de 500 sem mudar
nomes, fotos, vínculos, saldos ou `updated_at`. PostgreSQL aloca referências com
sequência e permutação sem colisões dentro de 32^6 posições; códigos não são
reciclados quando produtos são excluídos. Um índice único atende à busca pela referência curta. SQLite local usa geração aleatória com verificação; os
testes de concorrência e migração são executados em PostgreSQL isolado.

`PATCH /api/inventory/items/batch/details` usa o mesmo processamento transacional
com bloqueio de linhas das outras edições em lote. Valida campos, fornecedor,
limites e comparação de versão enviada por item antes de aplicar mudanças.
Se um cadastro mudou durante a conferência, retorna 409 sem salvar o lote.
Campos omitidos permanecem; `null` explícito limpa apenas os campos opcionais.
Descrições acrescentadas são enviadas como texto final, evitando repetir o
acréscimo em uma tentativa idêntica. A edição não carrega originais das imagens.

## Etiquetas internas de produtos (21/10/2026)

O componente **Estoque → Mais ações → Etiquetas de produtos** permite selecionar
produtos, grades ou lotes, conferir cópias por variação/cor/tamanho e imprimir
QR + código interno na Zebra USB/Windows, em etiquetas de 60 × 30 mm. Não altera
estoque e não depende do Sumatra. Tickets ficam na 3nStar; a configuração exclusiva
da Zebra exige fila anterior concluída e preserva histórico.
Instalação, limites, reconexão e teste físico: [guia de etiquetas](ETIQUETAS_PRODUTOS.md).
