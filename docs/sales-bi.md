# Visão de vendas — OneDrive

O painel `/bi-vendas`, acessível pelo dashboard a administradores e gerentes, lê planilhas externas sem criar vendas no ERP e sem editar o Excel. A configuração das fontes é restrita ao administrador.

## Resultados e cobertura

- O leitor usa `openpyxl` com `data_only=True`, `read_only=True` e `keep_links=False`. Consome os resultados calculados e salvos pelo Excel, incluindo correções já incorporadas. Não executa fórmulas, não remove constantes das fórmulas e não as envia à API do frontend.
- Na planilha **atual**, soma os resultados salvos de semanas únicas e da aba corrente. Isso acompanha novos lançamentos mesmo quando o resumo mensal lateral, preenchido manualmente, ainda não foi atualizado. A identidade dos lançamentos evita contar a aba corrente novamente quando já foi copiada para uma semana.
- Nos arquivos **mensais**, o total vem do fechamento mensal salvo. O resultado mensal por vendedor tem prioridade quando publicado. Quando ele não existe, só é derivado de semanas cujo detalhamento foi identificado. Uma divergência entre um resumo de semana e a aba impede atribuir esse detalhamento a um período por suposição.
- Os formatos observados incluem `Planilha1`, `Vendas`, `Plhanilha1`, `semana1` e `semana 1`, total semanal na linha 7 ou 8 e diferentes posições do fechamento mensal. Modelos desconhecidos geram uma pendência visível, preservando a última leitura válida.
- Ano e mês dos arquivos históricos vêm da pasta de ano e do nome do mês no arquivo. Na planilha atual, vêm do ano informado no resumo e das datas semanais; podem ser definidos explicitamente na configuração.
- Um arquivo mensal arquivado tem prioridade sobre a planilha atual do mesmo mês. Dois arquivos históricos do mesmo período também produzem apenas um resultado (prioridade à versão mais recentemente modificada no OneDrive).
- Ausência de dado é `null`, não zero. Os rankings e as moedas indicam quantos meses têm detalhamento. O mês atual aparece como em andamento. Os acumulados anuais somam apenas os meses disponíveis; não reutilizam os acumulados anuais repetidos em cada arquivo.
- Os valores por moeda vêm dos resumos salvos, sem nova cotação. Não são misturados diretamente entre moedas. As datas dos rankings semanais preservam os períodos definidos pelo usuário, que não precisam coincidir com semanas ISO.

## Sincronização

`app.services.sales_bi_sync` roda em uma thread independente do assistente e da impressão. Uma concessão temporária no banco impede execuções simultâneas durante deploys. A primeira leitura descobre as pastas anuais e arquivos XLSX. As seguintes baixam a planilha atual e apenas os históricos cuja versão mudou, a cada 15 minutos. Falhas voltam a ser tentadas após dois minutos.

O conector só possui operações **GET**, com links compartilhados explicitamente configurados. Usa o acesso de leitura disponibilizado pelo compartilhamento OneDrive e a API de pastas/arquivos REST documentada pela Microsoft. Se o compartilhamento expirar ou passar a exigir login, o painel conserva o último resultado e mostra a falha. Não altera permissões para restabelecer acesso.

Há limites de tamanho, arquivos, páginas, caminhos de pasta e destinos HTTP, inclusive nos redirecionamentos. Os links compartilhados ficam na tabela de configuração e só são expostos no endpoint administrativo; não devem ir para o código-fonte ou logs. Os bytes XLSX são processados em memória. O banco guarda resumos, referências de células, versões e estado de leitura, não cópias dos arquivos nem linhas com informações de clientes.

Tabelas isoladas: `sales_bi_config`, `sales_bi_workbooks`. Migração: `x4y5z6a7b8c9`. Nenhuma alteração nas tabelas de vendas, pedidos ou clientes.

## Verificação

```sh
cd backend
DATABASE_URL=sqlite:// PYTHONPATH=. venv/bin/python -m pytest tests/test_sales_bi.py -q
```

Os testes geram arquivos fictícios com resultados salvos e usam SQLite. Cobrem correções, ausência de cache, formatos antigos, duplicação, filtros, proteção por função, URLs, retenção do último resultado, repetição da sincronização e migração.

Referência da Microsoft: https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-folders-and-files-with-rest
