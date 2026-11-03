import { useI18n } from 'vue-i18n'
const copy = {
  title: ['Grades com IA', 'Variantes con IA', 'AI product groups'],
  intro: [
    'Compare nomes, categorias e fotos dos itens selecionados. Confira as evidências e prepare uma grade antes de confirmar.',
    'Compara nombres, categorías y fotos de los productos seleccionados. Revisa las evidencias y prepara un grupo antes de confirmar.',
    'Compare selected product names, categories and photos. Review the evidence and prepare a group before confirming.',
  ],
  selection: [
    '{count} produtos selecionados',
    '{count} productos seleccionados',
    '{count} selected products',
  ],
  limit: [
    'Selecione de 2 a 24 produtos para cada análise.',
    'Selecciona de 2 a 24 productos por análisis.',
    'Select 2 to 24 products for each analysis.',
  ],
  photos: [
    'Comparar também as fotos disponíveis',
    'Comparar también las fotos disponibles',
    'Compare available photos too',
  ],
  analyze: ['Analisar selecionados', 'Analizar seleccionados', 'Analyze selected products'],
  analyzing: ['Comparando os produtos…', 'Comparando los productos…', 'Comparing products…'],
  analyzed: [
    '{count} produtos · {photos} fotos analisadas',
    '{count} productos · {photos} fotos analizadas',
    '{count} products · {photos} photos analyzed',
  ],
  empty: [
    'A IA não encontrou uma associação suficiente entre estes itens. Você pode continuar pelo gerenciamento manual de grades.',
    'La IA no encontró una relación suficiente entre estos productos. Puedes continuar con la gestión manual.',
    'AI did not find enough evidence to group these products. You can continue with manual group management.',
  ],
  suggestion: [
    'Sugestão {number} · {count} itens',
    'Sugerencia {number} · {count} productos',
    'Suggestion {number} · {count} products',
  ],
  high: ['Indicação forte', 'Indicación fuerte', 'Strong indication'],
  medium: ['Indicação moderada', 'Indicación moderada', 'Moderate indication'],
  low: ['Indicação fraca', 'Indicación débil', 'Weak indication'],
  selected: ['Conferir esta sugestão', 'Revisar esta sugerencia', 'Review this suggestion'],
  newGroup: ['Nova grade', 'Nuevo grupo', 'New group'],
  existingGroup: ['Grade existente', 'Grupo existente', 'Existing group'],
  destination: ['Destino dos itens', 'Destino de los productos', 'Product destination'],
  name: ['Nome da nova grade', 'Nombre del nuevo grupo', 'New group name'],
  choose: ['Escolha a grade de destino', 'Elige el grupo de destino', 'Choose destination group'],
  review: ['Preparar conferência', 'Preparar revisión', 'Prepare review'],
  preparing: ['Conferindo vínculos…', 'Revisando vínculos…', 'Checking memberships…'],
  destinationLabel: [
    'Grade de destino: {name}',
    'Grupo de destino: {name}',
    'Destination group: {name}',
  ],
  existing: [
    '{count} itens já estão nesta grade',
    '{count} productos ya pertenecen a este grupo',
    '{count} products already belong to this group',
  ],
  remaining: [
    '{moving} itens saem de “{name}”; {remaining} permanecem.',
    '{moving} productos salen de “{name}”; {remaining} permanecen.',
    '{moving} products leave “{name}”; {remaining} remain.',
  ],
  unaffected: [
    'Os códigos, fotos, saldos e históricos dos produtos são preservados.',
    'Se conservan códigos, fotos, stock e historial de los productos.',
    'Product codes, photos, stock and history are preserved.',
  ],
  consent: [
    'Conferi os produtos, tamanhos, cores e a grade de destino.',
    'Revisé productos, talles, colores y grupo de destino.',
    'I reviewed the products, sizes, colors and destination group.',
  ],
  apply: ['Confirmar vínculos', 'Confirmar vínculos', 'Confirm memberships'],
  applying: ['Salvando vínculos…', 'Guardando vínculos…', 'Saving memberships…'],
  back: ['Voltar', 'Volver', 'Back'],
  close: ['Fechar', 'Cerrar', 'Close'],
  selectItem: ['Incluir {name}', 'Incluir {name}', 'Include {name}'],
  pending: [
    'A confirmação não foi recebida. Confira novamente a mesma alteração antes de iniciar outra.',
    'No se recibió la confirmación. Revisa el mismo cambio antes de iniciar otro.',
    'Confirmation was not received. Check the same change again before starting another.',
  ],
  recovered: [
    'Há uma confirmação anterior para esta conta. Confira os itens abaixo e consulte o resultado.',
    'Hay una confirmación anterior para esta cuenta. Revisa los productos y consulta el resultado.',
    'A previous confirmation exists for this account. Review the products and check its result.',
  ],
  retry: ['Conferir resultado', 'Consultar resultado', 'Check result'],
  analyzeError: [
    'Não foi possível concluir a análise agora. Tente novamente.',
    'No se pudo completar el análisis. Inténtalo de nuevo.',
    'Analysis could not be completed. Try again.',
  ],
  previewError: [
    'Não foi possível preparar a grade. Confira os produtos e tente novamente.',
    'No se pudo preparar el grupo. Revisa los productos e inténtalo de nuevo.',
    'The group could not be prepared. Review the products and try again.',
  ],
  saveError: [
    'Não foi possível confirmar os vínculos. Atualize a seleção e confira novamente.',
    'No se pudieron confirmar los vínculos. Actualiza la selección y revisa de nuevo.',
    'Memberships could not be confirmed. Refresh the selection and review again.',
  ],
  storageError: [
    'Não foi possível guardar a confirmação neste aparelho. Habilite o armazenamento antes de salvar.',
    'No se pudo guardar la confirmación en este dispositivo. Habilita el almacenamiento antes de guardar.',
    'This device could not preserve the confirmation. Enable storage before saving.',
  ],
  recoveryError: [
    'A confirmação guardada não pôde ser lida. Confira as grades atuais antes de iniciar outra alteração.',
    'No se pudo leer la confirmación guardada. Revisa los grupos actuales antes de iniciar otro cambio.',
    'The saved confirmation could not be read. Check current groups before starting another change.',
  ],
  reset: ['Conferir seleção novamente', 'Revisar selección de nuevo', 'Review selection again'],
} as const
export function useGradeAiText() {
  const { locale } = useI18n({ useScope: 'global' })
  return (key: keyof typeof copy, params: Record<string, string | number> = {}) =>
    copy[key][locale.value.startsWith('es') ? 1 : locale.value.startsWith('en') ? 2 : 0].replace(
      /\{(\w+)\}/g,
      (original, name) => String(params[name] ?? original),
    )
}
