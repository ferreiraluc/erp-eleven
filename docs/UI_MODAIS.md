# Modais e formulários do ERP

Revisão de 07/10/2026. O padrão atende formulários curtos, cadastros em etapas,
confirmações, históricos e ferramentas de captura sem adicionar uma biblioteca de UI.

## Referências e decisões

- [Zoho Forms](https://www.zoho.com/forms/forms-designer.html): campos relacionados
  agrupados, rótulos consistentes e informações opcionais reveladas conforme a necessidade.
- [Microsoft Fluent 2](https://fluent2.microsoft.design/components/web/react/core/dialog/usage):
  título e ações persistentes, conteúdo com rolagem própria e ações claras.
- [W3C APG](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/): nome acessível,
  foco dentro da janela, ciclo de Tab e retorno ao controle que abriu o diálogo.
- [Engineering at Meta](https://engineering.fb.com/2020/05/08/web/facebook-redesign/):
  estilos compartilhados e custo de manutenção previsível. Essa publicação explica
  decisões de engenharia do Facebook; não é uma especificação pública de modais.
  A aplicação ao Vue do ERP é uma decisão deste projeto, não uma reprodução do FDS.

Compactar significa reduzir espaços e escolhas concorrentes, preservando legibilidade,
alvos de toque e informações necessárias à decisão. O cadastro de produto conserva
as etapas foto/etiqueta → conferência → estoque.

## Implementação

`frontend/src/assets/dialogs.css` é importado em `main.ts`. As classes são explícitas;
não alteram qualquer elemento só por conter “modal” no nome.

| Classe | Uso |
| --- | --- |
| `erp-dialog-backdrop` | Fundo e margens da janela |
| `erp-dialog` | Superfície flexível, largura padrão de 680px |
| `erp-dialog--sm` | Confirmações e formulários curtos: 480px |
| `erp-dialog--lg` | Pedidos, históricos e formulários detalhados: 840px |
| `erp-dialog--xl`, `erp-dialog--media` | Calendários e captura/prévia: até 1040px |
| `erp-dialog__header` | Título e fechamento, fora da área rolável |
| `erp-dialog__body` | Área principal rolável |
| `erp-dialog__form` | Formulário flexível que contém corpo e rodapé |
| `erp-dialog__footer` | Ações de conclusão, fora da rolagem |
| `erp-dialog__tabs` | Etapas/abas com rolagem horizontal própria se necessária |
| `erp-dialog__section` | Grupo opcional, também utilizável em `details` |

Até 600px, a janela usa a largura disponível, margens de 8px, altura limitada por
`100dvh` e área segura inferior. Campos usam texto de 16px para evitar zoom de foco
no iOS; ações do rodapé têm pelo menos 44px. Tabelas, fotos e câmera conservam suas
estruturas específicas. Os estilos centrais só atuam em `@media screen`, preservando
o CSS do recibo impresso.

A diretiva local `v-erp-dialog` (`frontend/src/directives/erpDialog.ts`) controla:

- Foco inicial na superfície, sem acionar um campo ou confirmar uma operação.
- Tab/Shift+Tab na janela superior, excluindo controles ocultos e desabilitados.
- Restauração de foco e bloqueio de rolagem da página enquanto houver janelas ativas.
- Empilhamento de janelas existentes, inclusive captura aberta sobre um cadastro.
- `role`, `aria-modal` e associação ao título quando ainda não informados.
- Escape usando somente o botão marcado `data-dialog-close`, se habilitado.
  Eventos consumidos por um campo (como cancelar a nova cor) e handlers próprios
  continuam prioritários. `alertdialog` não recebe fechamento genérico por Escape.

Janelas mantidas com `v-show` devem passar a condição de visibilidade à diretiva.
As regras de negócio continuam nos handlers da tela: a diretiva não envia formulários,
não confirma compra, impressão ou exclusão e não altera permissões.

## Inventário revisado

São **43 superfícies em 36 componentes/telas**; uma superfície pode atender vários
estados (por exemplo, endereço, remetente, impressão e frete).

| Área | Superfícies |
| --- | --- |
| Estoque | Novo/editar item, movimentação, edição em lote, transferência, sugestão de agrupamento, importação, agrupamento manual, exclusão, histórico do produto, histórico de excluídos |
| Foto e OCR | Assistente de foto, leitura de etiqueta, leitor de código, exemplos salvos, confirmação de exclusão de exemplo |
| Clientes/pedidos | Cliente, pedido, detalhes do pedido, gerenciador de tags e edição de tag, câmera de anexos |
| Logística | Rastreamento no card e na página; endereço/remetente/frete/histórico de uso; revisão de remetente gerado |
| Equipe/acesso | Calendário ampliado, detalhes do dia, criar/editar folga, excluir folga, vendedor, usuário, redefinição de senha |
| Financeiro | Câmbio no dashboard, gestão de câmbio e exclusão, câmbio do PDV, produto avulso, recibo, gestor de venda, consulta e cadastro de pagador, importação de vendas e janela da página de vendas |

Seletores de cor e ampliadores de imagem são superfícies especializadas e mantêm
seus controles próprios; não foram transformados em formulários. Ações contextuais
dentro de listas (excluir uma linha, adicionar uma tag, escolher uma cotação) continuam
próximas aos dados, fora do rodapé de conclusão do formulário.

## Mudanças específicas de uso

- **Novo item:** descrição, localização, fornecedor e limites ficam em “Organização
  e limites (opcional)”. Erro de estoque mínimo abre essa seção para correção.
- **Modelos e cores da grade:** “+” abre o editor compacto, com botão explícito
  para adicionar e suporte a Enter. Modelo recebe nome + lista de tamanhos com
  prévia, sem precisar confirmar cada tamanho. Escape cancela somente o editor
  e retorna foco ao “+”. Opções ficam salvas no navegador para novos cadastros;
  falha de armazenamento é informada sem perder o texto. Cores repetidas são reaproveitadas.
  **Editar opções** revela os controles de remover botões personalizados de modelos
  e cores; **Concluir edição** os recolhe. Excluir uma cor salva também a retira da
  seleção atual; excluir um modelo conserva os tamanhos da grade em edição.
- **Paraguai:** nome, telefone, cidade e RUC/C.I ficam à vista. Os complementos
  opcionais ficam em uma seção expansível, aberta quando há dados preenchidos.
  Alternar o país ou recolher a seção conserva todos os valores.
- **Estoque:** a visualização em cards se chama **Quadrados**; **Ver grades** continua
  identificando os grupos/variantes de estoque.
- **Clientes, vendedores, folgas, usuários e endereços:** formulários com rodapé
  interno foram reorganizados para manter as ações visíveis, sem separar os botões
  da validação nativa do formulário.
- **Remetente gerado:** o botão persistente aponta para o formulário de revisão;
  o aceite manual obrigatório permanece no formulário e não é contornado.

## Validação e manutenção

1. Rodar `npm --prefix frontend test`, `run type-check` e `run build`.
2. Conferir larguras de 360/412px, 768px e desktop; títulos longos, erros, muitos
   itens e rodapé devem caber. Verificar também tela baixa/teclado virtual.
3. Abrir/fechar pelo teclado, testar Tab e Shift+Tab, janela filha e retorno de foco.
4. Validar PT/ES/EN, estados desabilitados e preservação das informações digitadas.
5. Conferir impressão por preview/CSS, sem enviar impressão ou pagamento para testar UI.

Os testes da diretiva cobrem foco, empilhamento, v-show, restauração da rolagem e
fechamento seguro. Os testes dos módulos verificam seus fluxos e contratos. A revisão
visual local usa dados sintéticos e bloqueia gravações. Isso não equivale a certificação
WCAG nem a validação em cada aparelho físico; câmera, teclado virtual e leitores de
tela ainda devem ser conferidos nos dispositivos usados pela loja.
