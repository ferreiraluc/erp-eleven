# Interface e interação da Eleven

O ERP conserva marca, navegação, densidade do estoque e regras de negócio. Este
padrão evolui os componentes existentes; não introduz uma segunda biblioteca de UI.

## Referências e decisões

- [Apple: princípios](https://developer.apple.com/design/human-interface-guidelines/design-principles),
  [sheets](https://developer.apple.com/design/human-interface-guidelines/sheets),
  [carregamento](https://developer.apple.com/design/human-interface-guidelines/loading)
  e [movimento](https://developer.apple.com/design/human-interface-guidelines/motion):
  hierarquia clara, tarefa delimitada, conteúdo disponível cedo e movimento opcional.
- [Meta: WhatsApp moderno, simples e acessível](https://about.fb.com/br/news/2024/05/mantendo-o-whatsapp-moderno-simples-e-acessivel/)
  e [filtros rápidos](https://about.fb.com/news/2024/04/whatsapp-chat-filters/):
  contexto preservado, organização próxima à lista e opções secundárias em superfícies
  compactas. São princípios de interação, não cópia da identidade visual da Meta.
- [Zoho Inventory: grupos e variantes](https://www.zoho.com/us/inventory/item-groups-and-composite-items/)
  e [gestão de itens](https://www.zoho.com/inventory/help/items/additional-features.html):
  atributos compartilhados, identidade por variante, ações em lote e filtros claros.
  Similaridade não autoriza fundir SKUs, baixar estoque nem substituir histórico.

Na Eleven, isso se traduz em dropdowns ancorados em lugar do seletor nativo de
telefone, formulário em lote com conferência por item, relacionados no contexto do
QR e busca local provisória enquanto o servidor confirma. Não há IA, animação ou
consulta de rede adicional obrigatória antes de um clique operacional.

## Fontes compartilhadas

| Responsabilidade | Fonte |
| --- | --- |
| Cores, espaçamento, raios, elevação e duração | `frontend/src/assets/main.css` |
| Botões primário/secundário/perigo/ícone/compacto | `frontend/src/assets/buttons.css` |
| Estrutura, cabeçalho, corpo rolável e rodapé de modal | `frontend/src/assets/dialogs.css` |
| Dropdown, teclado e opções | `components/ui/ErpDropdown.vue`, `ErpSelect.vue`, `dropdown.css` |
| Foco, Escape, camadas e restauração da rolagem | `directives/erpDialog.ts` |
| Indicador com prévia de conteúdo acessível | `components/ui/ErpLoadingState.vue` |
| Evitar zoom involuntário de campos no Safari | `frontend/src/assets/ios.css` |
| Contratos estáticos de toda a interface | `frontend/scripts/audit-ui.mjs` |

Controles têm raio 10 px, popovers 14 px, cards conservam os tamanhos existentes e
modais usam 20 px (16 px no celular). Sombras distinguem camadas sem desfoque de
tela inteira. O azul continua sendo a ação principal; vermelho identifica ações
destrutivas e verde continua associado a valores/estados positivos. Cor não é a
única indicação: manter texto, ícones, rótulos e estados selecionados.

## Regras de interação

1. Usar `erp-button` com variante explícita. Dentro de formulário, declarar
   `type="button"` ou `type="submit"`; seleção, edição ou remoção de uma linha não
   pode enviar o formulário por acidente. Não criar interceptador global de submit.
2. Uma ação principal clara por etapa; ações secundárias continuam discretas.
   Nomear ícones com `aria-label`, `aria-labelledby` ou título. Rótulos e campos
   acessíveis usam os tradutores existentes, incluindo português/espanhol/inglês.
3. Modais usam `v-erp-dialog`, `erp-dialog-backdrop`, cabeçalho, corpo e rodapé
   comuns. Abrir não posiciona o teclado do celular automaticamente. Tab permanece
   na tarefa, Escape usa somente o controle de fechar permitido, e fechar restaura
   foco/rolagem. Não remover confirmação, identidade, idempotência ou bloqueio de
   operação em andamento para simplificar a aparência.
4. O balão do sino é **não modal**, com `aria-modal="false"`: não bloqueia a página
   nem assume o ciclo de foco de um formulário. Menus usam o vínculo de portal do
   dropdown para permanecer acima do modal que os abriu.
5. Preservar área de rolagem e ações finais acessíveis no celular, safe area e
   fonte de campo adequada ao Safari. Controles compactos do estoque mantêm a
   densidade solicitada. Um menu não pode empurrar os botões para fora da tela.
6. Transições de entrada têm 130–160 ms, com deslocamento de poucos pixels e sem
   reordenar conteúdo. Respeitar `prefers-reduced-motion` e cores forçadas. Evitar
   zoom, animação de layout, shimmer pesado, efeitos de vidro ou filtros de tela
   inteira em operações frequentes.
7. Exibir conteúdo confirmado assim que disponível. `ErpLoadingState` apresenta
   texto real em `role="status"`, placeholders ocultos de leitores de tela e versão
   sem movimento. Com resultados presentes, usar progresso discreto; não trocar
   a lista por um esqueleto a cada consulta. Erros precisam oferecer recuperação.
8. `aria-busy` identifica gravações em andamento; o indicador não substitui o
   bloqueio efetivo do botão nem as validações do backend. Não fazer gravação
   otimista de saldo, pagamento, venda ou impressão para aparentar velocidade.

## Auditoria e evolução

Em 28/10/2026, a auditoria percorreu **119 componentes Vue, 54 superfícies de
diálogo e 768 botões**: sem seletor nativo, modal sem ciclo comum (exceto o balão
explicitamente não modal), ícone sem nome acessível ou submit implícito nos forms.
A verificação analisa todos os templates com o parser DOM do Vue e falha também em
erro de sintaxe; não ignora componentes que não conseguiu analisar.

Executar `npm --prefix frontend run audit:ui`. A etapa faz parte da verificação
frontend da PR. Ela não substitui testes de comportamento ou inspeção visual:
validar teclado, modal sobre modal, dropdown dentro de modal, rolagem e retorno
à tela anterior em viewport desktop e mobile. Os testes de sessão, estoque,
confirmação e impressão continuam obrigatórios.

A validação visual desta revisão usou o **modal real de edição massiva** com dados
sintéticos, desktop e viewport de 412×915, sem API operacional habilitada; confirmou
abertura, seleção do dropdown, foco, rolagem e controles finais acessíveis. Não é
uma declaração de teste físico em todos os modelos de telefone, nem uma simulação
de venda ou impressão.

Próximas alterações devem começar pelo componente compartilhado e pelo fluxo
observado, mantendo guias atualizados. Preferir reduzir passos, repetição e tempo
de espera a adicionar ornamentação. Novos campos/variantes precisam passar pelo
mesmo padrão, sem introduzir um seletor ou uma rotina de confirmação paralela.
