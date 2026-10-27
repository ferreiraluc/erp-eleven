import i18n from '@/i18n'

const copy = {
  title: ['Revisão diária do sistema', 'Revisión diaria del sistema', 'Daily system review'],
  intro: [
    'Confira pendências de cadastros, vendas, filas e processos. As análises preservam os dados da operação.',
    'Revise pendientes de registros, ventas, colas y procesos. El análisis conserva los datos operativos.',
    'Review catalog, sales, queues and processes. Analysis preserves operational data.',
  ],
  enabled: ['Revisão diária ativa', 'Revisión diaria activa', 'Daily review enabled'],
  time: ['Horário de Brasília', 'Hora de Brasilia', 'Brasília time'],
  aiEnabled: ['Incluir resumo com IA', 'Incluir resumen con IA', 'Include an AI summary'],
  aiHelp: [
    'A IA recebe somente contagens anônimas. Não altera produtos, saldos, vendas ou impressões.',
    'La IA recibe solo conteos anónimos. No modifica productos, saldos, ventas ni impresiones.',
    'AI receives anonymous counts only. It does not change products, balances, sales or printing.',
  ],
  limits: [
    'Até {manual} revisões manuais e {calls} consultas à IA por dia. Novas revisões continuam pelas regras do sistema após o limite da IA.',
    'Hasta {manual} revisiones manuales y {calls} consultas a IA por día. Después del límite de IA, las nuevas revisiones siguen con reglas del sistema.',
    'Up to {manual} manual reviews and {calls} AI calls per day. Further reviews use system checks after the AI limit.',
  ],
  scheduleHelp: [
    'Alterar o horário agenda a próxima ocorrência; salvar não inicia uma análise.',
    'Cambiar la hora programa la próxima revisión; guardar no inicia un análisis.',
    'Changing the time schedules the next occurrence; saving does not start an analysis.',
  ],
  firstRun: [
    'Primeira data programada: {date}.',
    'Primera fecha programada: {date}.',
    'First scheduled date: {date}.',
  ],
  save: ['Salvar configuração', 'Guardar configuración', 'Save settings'],
  refresh: ['Atualizar', 'Actualizar', 'Refresh'],
  scan: ['Analisar agora', 'Analizar ahora', 'Analyze now'],
  queuedHelp: [
    'Análise solicitada. Ela continua em segundo plano; você pode seguir usando o sistema.',
    'Análisis solicitado. Continúa en segundo plano; puede seguir usando el sistema.',
    'Review requested. It continues in the background while you use the app.',
  ],
  paused: [
    'Ative a revisão diária e salve para solicitar uma nova análise.',
    'Active la revisión diaria y guarde para solicitar un nuevo análisis.',
    'Enable the daily review and save before requesting a new analysis.',
  ],
  loading: ['Carregando revisão…', 'Cargando revisión…', 'Loading review…'],
  error: [
    'Não foi possível carregar a revisão. Tente novamente.',
    'No se pudo cargar la revisión. Inténtelo de nuevo.',
    'Unable to load the review. Please try again.',
  ],
  saveError: [
    'Não foi possível salvar. Confira a conexão e tente novamente.',
    'No se pudo guardar. Revise la conexión e inténtelo de nuevo.',
    'Unable to save. Check the connection and try again.',
  ],
  scanError: [
    'Não foi possível confirmar a solicitação. Tente novamente; o mesmo pedido será reutilizado.',
    'No se pudo confirmar la solicitud. Inténtelo de nuevo; se reutilizará el mismo pedido.',
    'Unable to confirm the request. Retry to reuse the same request.',
  ],
  conflict: [
    'Esta configuração mudou. Atualize e confira antes de salvar novamente.',
    'Esta configuración cambió. Actualice y revise antes de guardar de nuevo.',
    'Settings changed. Refresh and review before saving again.',
  ],
  activeConflict: [
    'Já há uma análise pendente ou a revisão foi pausada. Atualize para conferir.',
    'Ya hay un análisis pendiente o se pausó la revisión. Actualice para comprobar.',
    'A review is already pending or reviews were paused. Refresh to check.',
  ],
  dailyLimit: [
    'O limite de revisões manuais do dia foi atingido. A revisão programada continua disponível.',
    'Se alcanzó el límite diario de revisiones manuales. La revisión programada sigue disponible.',
    'Today’s manual review limit has been reached. Scheduled review remains available.',
  ],
  invalidTime: ['Escolha um horário válido.', 'Elija una hora válida.', 'Choose a valid time.'],
  saved: ['Configuração salva.', 'Configuración guardada.', 'Settings saved.'],
  latest: ['Relatório mais recente', 'Informe más reciente', 'Latest report'],
  selected: ['Relatório selecionado', 'Informe seleccionado', 'Selected report'],
  empty: [
    'Ainda não há relatórios. A revisão será feita no horário programado, ou você pode solicitar uma análise.',
    'Aún no hay informes. La revisión se realizará a la hora programada o puede solicitar un análisis.',
    'No reports yet. Review will run at its scheduled time, or you can request one.',
  ],
  queued: ['Na fila', 'En cola', 'Queued'],
  running: ['Em análise', 'En análisis', 'Analyzing'],
  completed: ['Concluído', 'Completado', 'Completed'],
  partial: ['Cobertura parcial', 'Cobertura parcial', 'Partial coverage'],
  failed: ['Análise indisponível', 'Análisis no disponible', 'Review unavailable'],
  daily: ['Programado', 'Programado', 'Scheduled'],
  manual: ['Solicitado por Lucas', 'Solicitado por Lucas', 'Requested by Lucas'],
  deterministic: [
    'Resumo das verificações do sistema',
    'Resumen de las verificaciones del sistema',
    'System check summary',
  ],
  aiSummary: ['Interpretação com IA', 'Interpretación con IA', 'AI interpretation'],
  aiUnavailable: [
    'Resumo com IA indisponível. As verificações do sistema continuam válidas para a cobertura informada.',
    'Resumen con IA no disponible. Las verificaciones siguen siendo válidas para la cobertura indicada.',
    'AI summary unavailable. System checks remain valid for the stated coverage.',
  ],
  aiSkipped: [
    'Esta revisão usou somente as verificações do sistema.',
    'Esta revisión usó solo verificaciones del sistema.',
    'This review used system checks only.',
  ],
  aiPending: [
    'A interpretação com IA está pendente.',
    'La interpretación con IA está pendiente.',
    'AI interpretation is pending.',
  ],
  bounded: [
    'A cobertura é limitada à janela e aos registros indicados abaixo. Um relatório sem alertas não comprova todo o inventário.',
    'La cobertura se limita a la ventana y a los registros indicados abajo. Un informe sin alertas no comprueba todo el inventario.',
    'Coverage is limited to the windows and records below. A report with no alerts does not verify the entire inventory.',
  ],
  incomplete: [
    'Há verificações incompletas. Confira a cobertura antes de concluir que não existem pendências.',
    'Hay verificaciones incompletas. Revise la cobertura antes de concluir que no hay pendientes.',
    'Some checks are incomplete. Review coverage before concluding there are no pending issues.',
  ],
  coverage: ['Cobertura da análise', 'Cobertura del análisis', 'Review coverage'],
  checked: [
    '{count} registros conferidos',
    '{count} registros revisados',
    '{count} records checked',
  ],
  withinWindow: [
    'Conferido dentro desta janela',
    'Revisado dentro de esta ventana',
    'Checked within this window',
  ],
  incompleteCheck: ['Verificação incompleta', 'Verificación incompleta', 'Incomplete check'],
  changedCohort: [
    'Comparação limitada aos cadastros recentes ou alterados.',
    'Comparación limitada a registros recientes o modificados.',
    'Comparison limited to recent or changed records.',
  ],
  last_24_hours: ['Últimas 24 horas', 'Últimas 24 horas', 'Last 24 hours'],
  active_jobs_last_7_days: [
    'Filas ativas dos últimos 7 dias',
    'Colas activas de los últimos 7 días',
    'Active queues from the last 7 days',
  ],
  active_devices: ['Impressoras ativas', 'Impresoras activas', 'Active printers'],
  current_state: ['Situação atual', 'Situación actual', 'Current state'],
  current_process: ['Processo atual', 'Proceso actual', 'Current process'],
  run_query_budget: [
    'Limite de consultas desta análise atingido.',
    'Se alcanzó el límite de consultas de este análisis.',
    'This review’s query limit was reached.',
  ],
  check_unavailable: [
    'Esta verificação não ficou disponível.',
    'Esta verificación no estuvo disponible.',
    'This check was unavailable.',
  ],
  inventory: ['Estoque', 'Inventario', 'Inventory'],
  sales: ['Vendas', 'Ventas', 'Sales'],
  prints: ['Fila de impressão', 'Cola de impresión', 'Print queue'],
  printers: ['Impressoras', 'Impresoras', 'Printers'],
  bi: ['Vendas de planilhas', 'Ventas de planillas', 'Spreadsheet sales'],
  workers: ['Processos do sistema', 'Procesos del sistema', 'System processes'],
  customers: ['Clientes', 'Clientes', 'Customers'],
  addresses: ['Endereços', 'Direcciones', 'Addresses'],
  findings: ['Pendências para conferência', 'Pendientes para revisión', 'Items to review'],
  countSummary: ['Contagens da análise', 'Conteos del análisis', 'Review counts'],
  noFindings: [
    'Nenhuma referência de pendência nesta página. Confira também as contagens e a cobertura.',
    'No hay referencias pendientes en esta página. Revise también los conteos y la cobertura.',
    'No pending references on this page. Check counts and coverage too.',
  ],
  findingLimit: [
    'As referências exibidas são uma amostra limitada; as contagens podem ser maiores.',
    'Las referencias son una muestra limitada; los conteos pueden ser mayores.',
    'Displayed references are a bounded sample; counts may be higher.',
  ],
  reference: ['Referência', 'Referencia', 'Reference'],
  related: ['Relacionado', 'Relacionado', 'Related'],
  open: ['Abrir módulo', 'Abrir módulo', 'Open module'],
  openSale: ['Abrir venda', 'Abrir venta', 'Open sale'],
  history: ['Histórico de revisões', 'Historial de revisiones', 'Review history'],
  view: ['Ver relatório', 'Ver informe', 'View report'],
  previous: ['Anterior', 'Anterior', 'Previous'],
  next: ['Próxima', 'Siguiente', 'Next'],
  historyEmpty: [
    'Nenhuma revisão neste período.',
    'No hay revisiones en este período.',
    'No reviews in this period.',
  ],
  inventory_missing_metadata: [
    'Produto com informações a conferir',
    'Producto con información por revisar',
    'Product information to review',
  ],
  inventory_balance: [
    'Saldo diferente da soma por local',
    'Saldo distinto de la suma por ubicación',
    'Balance differs from location totals',
  ],
  inventory_limits: [
    'Limites de estoque a conferir',
    'Límites de inventario por revisar',
    'Stock limits to review',
  ],
  sale_avulso_without_reason: [
    'Venda com avulso sem motivo informado',
    'Venta con artículo manual sin motivo',
    'Sale with unexplained manual item',
  ],
  print_uncertain: [
    'Impressão com envio incerto',
    'Impresión con envío incierto',
    'Print submission uncertain',
  ],
  print_failed: ['Impressão com falha', 'Error de impresión', 'Print failed'],
  print_stale: [
    'Impressão aguardando conferência',
    'Impresión pendiente de revisión',
    'Print waiting for review',
  ],
  printer_offline: [
    'Impressora sem contato recente',
    'Impresora sin contacto reciente',
    'Printer has no recent contact',
  ],
  bi_sync_problem: [
    'Sincronização de planilhas a conferir',
    'Sincronización de planillas por revisar',
    'Spreadsheet sync to review',
  ],
  worker_problem: [
    'Processo sem progresso recente',
    'Proceso sin progreso reciente',
    'Process has no recent progress',
  ],
  customer_duplicate_candidate: [
    'Possíveis clientes duplicados',
    'Posibles clientes duplicados',
    'Possible duplicate customers',
  ],
  address_duplicate_candidate: [
    'Possíveis endereços duplicados',
    'Posibles direcciones duplicadas',
    'Possible duplicate addresses',
  ],
  address_link_review: [
    'Vínculo de endereço a conferir',
    'Vínculo de dirección por revisar',
    'Address link to review',
  ],
  offline: [
    'Sem conexão. Atualize quando a internet voltar.',
    'Sin conexión. Actualice cuando vuelva internet.',
    'Offline. Refresh when internet returns.',
  ],
} as const
export type QualityCopyKey = keyof typeof copy
export function qualityText(key: QualityCopyKey, params?: Record<string, string | number>): string {
  const index = i18n.global.locale.value === 'es' ? 1 : i18n.global.locale.value === 'en' ? 2 : 0
  const text: string = copy[key]?.[index] ?? String(key)
  return params
    ? text.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
        name in params ? String(params[name]) : placeholder,
      )
    : text
}
