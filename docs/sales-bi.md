# Visão de vendas — OneDrive

O painel `/bi-vendas`, acessível pelo dashboard a administradores e gerentes, lê planilhas externas sem criar vendas no ERP e sem editar o Excel. A configuração das fontes é restrita ao administrador.

## Resultados e cobertura

- O leitor usa `openpyxl` com `data_only=True`, `read_only=True` e `keep_links=False`. Consome os resultados calculados e salvos pelo Excel, incluindo correções já incorporadas. Não executa fórmulas, não remove constantes das fórmulas e não as envia à API do frontend.
- Na planilha **atual**, soma os resultados salvos de semanas únicas e da aba corrente. Isso acompanha novos lançamentos mesmo quando o resumo mensal lateral, preenchido manualmente, ainda não foi atualizado. A identidade dos lançamentos evita contar a aba corrente novamente quando já foi copiada para uma semana.
- Nos arquivos **mensais**, o total vem do fechamento mensal salvo. O resultado mensal por vendedor tem prioridade quando publicado. Quando ele não existe, só é derivado de semanas cujo detalhamento foi identificado. Uma divergência entre um resumo de semana e a aba impede atribuir esse detalhamento a um período por suposição.
- Os formatos observados incluem `Planilha1`, `Vendas`, `Plhanilha1`, `semana1` e `semana 1`. O leitor localiza o cabeçalho dos vendedores acima das moedas e o total semanal entre as linhas 5 e 12, acompanhando linhas inseridas ou removidas. Aceita períodos escritos como texto ou como datas do Excel e resumos colados como texto monetário explícito (`$1.234,56`); formatos numéricos ambíguos permanecem ausentes. Modelos desconhecidos geram uma pendência visível, preservando a última leitura válida.
- Quando todos os resultados mensais por vendedor estão disponíveis, o leitor compara sua soma com o fechamento mensal. Diferenças acima de US$ 0,05 aparecem em **Fontes**, sem redistribuir ajustes gerais entre vendedores nem substituir os resultados salvos. Esse aviso identifica uma diferença entre resumos, não prova um erro na planilha. Fórmulas com referências incorretas ou resultados colados como texto precisam ser revisados na origem pelo responsável.
- Ano e mês dos arquivos históricos vêm da pasta de ano e do nome do mês no arquivo. Na planilha atual, vêm do ano informado no resumo e das datas semanais; podem ser definidos explicitamente na configuração.
- Um arquivo mensal arquivado tem prioridade sobre a planilha atual do mesmo mês. Dois arquivos históricos do mesmo período também produzem apenas um resultado (prioridade à versão mais recentemente modificada no OneDrive).
- Ausência de dado é `null`, não zero. Os rankings e as moedas indicam quantos meses têm detalhamento. O mês atual aparece como em andamento. Os acumulados anuais somam apenas os meses disponíveis; não reutilizam os acumulados anuais repetidos em cada arquivo.
- Os valores por moeda vêm dos resumos salvos, sem nova cotação. Não são misturados diretamente entre moedas. As datas dos rankings semanais preservam os períodos definidos pelo usuário, que não precisam coincidir com semanas ISO.

## Sincronização

`app.services.sales_bi_sync` roda em uma thread independente do assistente e da impressão. Uma concessão temporária no banco impede execuções simultâneas durante deploys. A primeira leitura descobre as pastas anuais e arquivos XLSX. A leitura automática ocorre uma vez por dia, às **18h no fuso America/Sao_Paulo (Brasília)**, baixando a planilha atual e apenas os históricos cuja versão mudou. O botão **Atualizar dados** permite solicitar uma leitura imediata a qualquer hora, sem deslocar o próximo horário diário. Após falhas, a última leitura válida é preservada e a próxima tentativa ocorre no horário diário ou mediante o botão; não há repetição automática a cada dois minutos. Salvar a configuração das fontes agenda a próxima leitura diária, sem iniciar uma sincronização imediata.

O conector só possui operações **GET**, com links compartilhados explicitamente configurados. Usa o acesso de leitura disponibilizado pelo compartilhamento OneDrive e a API de pastas/arquivos REST documentada pela Microsoft. Se o compartilhamento expirar ou passar a exigir login, o painel conserva o último resultado e mostra a falha. Não altera permissões para restabelecer acesso.

Há limites de tamanho, arquivos, páginas, caminhos de pasta e destinos HTTP, inclusive nos redirecionamentos. Os links compartilhados ficam na tabela de configuração e só são expostos no endpoint administrativo; não devem ir para o código-fonte ou logs. Os bytes XLSX são processados em memória. O banco guarda resumos, lançamentos reconhecidos, referências de células, versões e estado de leitura. Não guarda cópias dos arquivos ou fórmulas. Nome de cliente só é extraído de coluna explicitamente identificada como cliente; notas sem cabeçalho não viram cadastros nem são interpretadas como dados pessoais.

Tabelas isoladas: `sales_bi_config`, `sales_bi_workbooks`. Migração: `x4y5z6a7b8c9`. Nenhuma alteração nas tabelas de vendas, pedidos ou clientes.

## Verificação

```sh
cd backend
DATABASE_URL=sqlite:// PYTHONPATH=. venv/bin/python -m pytest tests/test_sales_bi.py -q
```

Os testes geram arquivos fictícios com resultados salvos e usam SQLite. Cobrem correções, ausência de cache, formatos antigos, duplicação, filtros, proteção por função, URLs, retenção do último resultado, repetição da sincronização e migração.

## Lançamentos individuais e movimento diário

O parser v3 acrescenta `entries` ao snapshot JSON existente. O endpoint autenticado
`GET /api/sales-bi/entries` e a aba **Lançamentos** consultam esse snapshot. Não criam
registros `Venda`, pedidos ou clientes e não alteram planilhas. Os arquivos antigos
ganham detalhamento na próxima sincronização manual ou diária; abrir a aba não
inicia uma leitura do OneDrive.

- No layout conhecido, B contém moeda, C bruto, D vendedor, E pagamento e F líquido.
  Linhas com moeda reconhecida, mas sem valor numérico salvo ou vendedor, são
  sinalizadas como incompletas. O resultado de fórmula sem cache não vira zero.
- Na planilha antiga sem coluna de líquido preenchida/identificada, o valor bruto
  é a única base disponível. No modelo com líquido, a ausência desse resultado
  permanece ausente. Totais de moedas diferentes nunca são somados entre si.
- Cada linha mantém aba, número da linha, célula, semana conciliada quando houver,
  arquivo e mês de origem. Dois pagamentos iguais em linhas diferentes continuam
  distintos. A cópia completa da aba corrente para uma aba semanal é excluída pela
  regra do parser; datas e agrupadores participam da identidade dessa cópia.
- A contagem representa **lançamentos**, pois um pedido pode ter pagamentos
  separados. Não é uma contagem garantida de pedidos ou clientes únicos.
- Datas completas ou dia/mês explícito do mês da planilha podem ser lidos de A ou
  de coluna `Data`; horário e cliente exigem cabeçalhos claros (`Hora`, `Cliente`).
  `Data e hora` também é reconhecido. `SEG`, `TER` e `SAB/DOM` permanecem agrupadores
  de dia da semana, sem receber uma data presumida. Data sem ano de outro mês não
  ganha um ano por suposição. Horários não são herdados de linhas anteriores.
- Intraday usa somente linhas com data **e** horário registrados. O instante da
  sincronização não representa o horário da venda. Cópias locais examinadas dos
  modelos de 2021, 2023 e 2026 não tinham esse detalhamento; a tela mostra a ausência
  e oferece movimento por dia da semana quando esse agrupador existe na origem.
- Ao filtrar um dia explícito, o site e o bot procuram essa data nos snapshots
  escolhidos de todos os meses. Uma venda de 01/10 registrada na última semana
  de `Setembro.xlsx` continua visível, inclusive em semanas que atravessam o ano.
  A prioridade entre arquivos do mesmo período permanece; linhas sem data não
  são atribuídas ao dia consultado. A cobertura informa os arquivos examinados.
- O fechamento corrigido continua oficial. A conferência dos valores líquidos
  contra os resumos salvos identifica diferenças por moeda, sem redistribuir
  correções nem expor as fórmulas. Filtros de dia/busca não redefinem o fechamento:
  ele e a reconciliação continuam restritos ao ano/mês selecionados, mesmo quando
  a consulta diária encontra linhas em um arquivo de outro mês.
- Escopo `own` impõe o vendedor da conta no servidor antes de tabelas, totais,
  datas, horas e reconciliação. Um `seller` enviado pela URL é ignorado nesse caso;
  conta sem vínculo recebe 403. A exportação contém somente a página já autorizada.

Validação adicional: `tests/test_sales_bi_entries.py`, com planilhas sintéticas,
datas/horários, cópias completas, pagamentos iguais, paginação, fontes antigas e
tentativas de consultar outro vendedor. Nenhuma migração adicional é necessária.
`test_sales_bi_day_boundary.py` verifica datas na fronteira de mês/ano no bot e
na API, preservando o escopo pessoal e o fechamento mensal.

O painel, seu card do dashboard e o detalhamento usam catálogos locais PT/ES/EN em
`frontend/src/components/sales/`. Mês, número, moeda, gráfico, navegação e CSV
acompanham o idioma selecionado; nomes de arquivos, vendedores e rótulos escritos
pelo usuário na planilha permanecem como na origem. O teste `salesBi.test.ts`
confere paridade das traduções, troca de idioma e a apresentação pessoal sem
posição de ranking global para contas com escopo próprio.

Referência da Microsoft: https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-folders-and-files-with-rest

## Card do dashboard

O dashboard mostra o último mês disponível, o acumulado do respectivo ano e os três
maiores resultados por vendedor naquele mês. Período, US$ e data de leitura ficam
visíveis. Os atalhos abrem vendedor, comparação, semanas do ano ou fontes com filtros.
Recarregar o card lê o snapshot do ERP e não aciona sincronização OneDrive.


## Consultas das planilhas pelo bot

Telegram e WhatsApp usam a ferramenta `consultar_vendas_planilhas` para perguntas
naturais sobre o desempenho da loja: “Quanto vendeu Junior neste mês?”, “Compare
setembro de 2024, 2025 e 2026”, “Qual semana vendeu mais neste ano?” ou “Mostre meus
lançamentos em reais de ontem”. A ferramenta reaproveita `build_overview`,
`private_workbooks` e `build_entries`; não tem acesso a SQL livre nem ao conector
OneDrive. `consultar_vendas` continua disponível para vendas operacionais e PDV
explicitamente solicitados, sem consolidar esses módulos com o Excel.

- Resumo por mês/ano, comparação do mesmo mês entre anos, ranking de vendedores e
  semanas usam os resultados corrigidos salvos. As somas observadas de linhas
  mostram bruto/líquido por moeda, separadas do fechamento corrigido em USD.
- Sem período, consulta o último mês disponível e informa o critério; mês sem ano
  usa o ano atual da loja. `este_ano` cobre os meses disponíveis do ano corrente.
  `hoje` e `ontem` usam o fuso configurado da loja, não a hora do download.
- Lançamentos, grupos por dia/hora e rankings têm paginação de até 20 resultados.
  Busca textual de lançamentos não redefine os totais do fechamento. A conferência
  mensal continua identificada como comparação de todo o mês, sem filtros de dia
  ou busca. Linhas sem data são contadas na cobertura, sem inventar intradiário.
- A resposta identifica a origem BI/Excel, o período efetivo, as sincronizações do
  snapshot e pendências sem revelar URLs privadas, fórmulas ou mensagens internas.
  Consulta nenhuma altera o agendamento diário de 18h ou dispara sincronização.
  Snapshots antigos sem detalhamento aguardam a próxima leitura diária ou manual.
- ADMIN/GERENTE ativo e identidade correspondente ao autor/canal são obrigatórios.
  Modo observação de grupo não inicia consulta financeira. Escopo pessoal é aplicado
  **antes** da descoberta de vendedores e de qualquer soma, ranking, comparação ou
  busca; o filtro de outro vendedor não amplia a permissão. Sem vendedor vinculado,
  o acesso pessoal falha fechado. A consulta não modifica o snapshot armazenado.
- Perguntas financeiras detectadas exigem uma consulta nova nesta solicitação.
  Resumos antigos da conversa não bastam como resposta. O histórico do autor segue
  o corte de permissão vigente quando o acesso foi reduzido para vendas pessoais.

Testes adicionais em `tests/test_assistant_sales_bi.py`: SQLite com dados sintéticos,
fonte corrente duplicada, fechamento corrigido, permissões/identidade, comparação,
paginação, datas reais, snapshots antigos e respostas simuladas da IA. Não há
sincronização, envio de mensagens ou acesso a planilhas reais nesses testes.

## Ficha do vendedor

Em `/vendors`, **Vendas e folgas** reúne os resultados mensais corrigidos, moedas,
melhor semana e calendário do vendedor, com filtro de ano/mês e acesso à Visão de
vendas. A fonte continua sendo o snapshot sincronizado; abrir a ficha não solicita
sync nem duplica vendas operacionais/PDV.

`Vendedor.sales_seller` guarda o nome canônico usado no BI. A conciliação administrativa
`app.customer_reconciliation` usa primeiro `Usuario.vendedor_id` + `sales_seller` e,
na ausência, um nome/alias único reconhecido no BI (`Wiss` → `Wissam`, `Juninho` →
`Junior`). Ambiguidades não são atribuídas e nomes históricos sem vendedor continuam
apenas no BI. Novos vínculos podem ser conciliados pelo mesmo comando após o cadastro.
As folgas já pertencem ao vendedor por `Folga.vendedor_id`; nenhuma folga é recriada.

`GET /api/vendedores/{id}/atividade?ano=2026&mes=9` valida a visibilidade financeira
no backend e projeta o snapshot para esse vendedor antes de agregar. Contas com escopo
pessoal só recebem vendas quando vendedor e identidade BI coincidem com sua conta.
Podem consultar o calendário operacional de outros vendedores, mas não seus valores,
rankings ou diagnósticos financeiros. Ausência de dados aparece como “—”, nunca zero
inventado. A data de sincronização e o estado em andamento contextualizam os resultados.

As planilhas atualmente sincronizadas não identificam clientes nas linhas individuais.
Por isso, o histórico do cliente reúne pedidos e logística, sem atribuir compras do
Excel por suposição. `Venda` operacional também não contém identidade de cliente;
não é somada a pedidos ou ao BI no histórico.
