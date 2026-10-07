# Conciliação de vendas: PDV, caderno e planilhas

Status: **plano de implementação**, definido em 07/10/2026. Não existe associação
financeira automática nesta versão. O histórico por produto já consulta os
vínculos PDV existentes; este documento define a etapa seguinte.

## Operação confirmada pela loja

O caderno continua obrigatório na rotina e seus valores são digitados no Excel.
O ERP complementa esse processo. Uma linha do caderno/planilha pode reunir várias
vendas do PDV para o mesmo cliente, porque ele pode comprar mais peças depois.

| Origem | Registros | Total a conferir |
| --- | --- | --- |
| PDV | Cliente A: USD 600 + USD 400 | USD 1.000 |
| Caderno → planilha | Uma linha: Cliente A, USD 1.000 | USD 1.000 |
| Conciliação | Duas vendas associadas à mesma linha | Diferença zero |

Associar significa registrar que são representações da mesma operação. Não criar
uma terceira venda, fundir as duas vendas PDV, copiar receita para outro módulo,
alterar a planilha ou movimentar o estoque novamente. Caderno só é consultável
depois de transcrito; fotografia/OCR do caderno não faz parte desta etapa.

## Primeira entrega proposta

Uma tela de **Conciliação de vendas** com filtro por período, vendedor, moeda,
pagamento, cliente e situação. De um lado, vendas e pagamentos PDV; do outro,
linhas da planilha com arquivo, aba, linha/célula, data ou intervalo e última leitura.
Um grupo permite escolher várias vendas e uma linha, mostrar a soma e a diferença,
confirmar a associação ou rejeitar uma sugestão. Situações: pendente, sugerida,
conciliada, divergente e precisa de nova conferência.

- Sugerir automaticamente combinações compatíveis, incluindo USD 600 + USD 400.
  Buscar grupos pequenos e limitados por cliente/vendedor/período/moeda, sem
  enumerar combinações de toda a base. Ao atingir o limite, pedir seleção manual.
- Igualdade do valor isolado não vincula registros. Vendas diferentes podem ter o
  mesmo valor. Quando houver duas combinações possíveis, manter ambas como
  candidatas e aguardar conferência; não consumir a primeira arbitrariamente.
- A primeira versão confirma os vínculos pelo usuário. Automação de confirmação
  deve vir depois de um piloto revisado, com taxa de acerto conhecida e critério
  explícito. Não delegar cálculos de dinheiro ou decisão de identidade à IA.
- Exibir separadamente total PDV, total da planilha e total conciliado. Nunca somar
  as duas fontes para calcular faturamento da loja. Mostrar divergências e origens.
- Não exigir coluna nova na planilha. Uma referência de caderno opcional no PDV
  pode melhorar a identificação, mas não será requisito para lançar ou conferir.

## Critérios e limites dos dados atuais

1. **Identidade:** usar usuário/vendedor mapeado, cliente identificado quando
   disponível e IDs das vendas. Nomes parecidos são indícios, não equivalência
   automática. Sem cliente, a sugestão exige mais evidência ou revisão manual.
2. **Datas:** comparar datas reais primeiro. Linhas do BI podem ter dia inferido,
   SAB/DOM ou semana inteira. A venda PDV deve estar dentro do intervalo conhecido;
   não atribuir uma hora ou dia exato inexistente. Mostrar a precisão da origem.
3. **Moedas e valores:** usar Decimal e pagamentos originais do PDV por moeda,
   considerando descontos, diferenças de pagamento e pagamentos mistos. O total
   PDV em G$ não equivale diretamente ao valor USD/BRL da planilha. Nunca usar o
   câmbio de hoje para explicar uma venda passada. Se faltar cotação histórica ou
   houver pagamento incoerente, marcar divergência e manter revisão pendente.
4. **Bruto versus líquido:** comparação da venda usa bruto após descontos da
   operação; líquido após taxa do recebimento é outra conferência. Maq/Máquina,
   Crédito, Débito, Thais e Dinheiro precisam de mapa explícito para métodos PDV.
   Não considerar um recebimento de fiado como nova venda de produtos.
5. **Validade:** vendas canceladas não compõem propostas de receitas ativas.
   Cancelamento ou edição de origem posterior invalida a conciliação afetada para
   revisão, sem apagar evidência anterior. Produto retirado do catálogo não
   cancela a venda e não elimina sua receita da conferência.

O cadastro financeiro de **Nova venda** (`Venda`), o PDV (`PdvSale`) e os snapshots
BI são fontes distintas. O primeiro piloto relaciona **PDV ↔ linha BI**. Incluir
lançamentos de `Venda` demanda uma origem explícita e as mesmas regras contra
contagem dupla; não inferir produtos pela descrição livre de uma venda financeira.

## Persistência e sincronização propostas

Criar grupo de conciliação, vínculos de vendas/pagamentos e referência à observação
BI com valores congelados para revisão. Guardar responsável, data, critérios,
valor alocado, moeda, estado e motivo de desfazer/revisar. Bloquear dupla alocação
com transação, locks e unicidade no PostgreSQL, inclusive entre dois operadores.

O ID atual da observação BI deriva de arquivo/aba/linha; ele não basta como
identidade durável, pois as linhas podem mudar e Planilha1 migra para semanaN ou
para o arquivo mensal. Conservar impressão digital dos campos e referência da
versão, detectar alterações e propor remapeamento. Valores iguais não justificam
mover um vínculo silenciosamente. Correspondência ambígua gera pendência.

Gerar sugestões após uma sincronização bem-sucedida e ao solicitar conferência dos
snapshots existentes. Preservar sincronização OneDrive às **18h Brasília** ou botão
manual. Abrir dashboard, histórico ou conciliação não inicia leitura no OneDrive.
Falha de sincronização conserva a última origem e sinaliza desatualização; não
marca registros ausentes como removidos a partir de uma leitura incompleta.

## Permissões e validação antes de lançar

- Lucas/Wissam consultam o geral; contas com escopo pessoal veem e conciliam apenas
  suas vendas e linhas BI. Aplicar isso antes de candidatos, totais e paginação.
- Somente mutações de conciliação geram auditoria; consultas continuam sem eventos.
- Testar combinações 600+400, duas combinações iguais, moedas mistas, descontos,
  taxas, fiado, cancelamentos, semana sem dia exato, virada de mês, cópia de abas,
  mudança de linha, sync parcial e confirmação concorrente no PostgreSQL.
- Validar o piloto com casos conferidos pelo responsável da loja antes de habilitar
  confirmação automática. Não alterar planilhas nem vendas para testar a tela.
