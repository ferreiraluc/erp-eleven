<template>
  <div class="labels-view">
    <ModuleHeader :title="tr('Etiquetas de produtos')">
      <button
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        @click="$router.push('/inventory')"
      >
        {{ tr('Estoque') }}
      </button>
      <button
        v-if="auth.isOwner"
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        @click="setupOpen = !setupOpen"
      >
        {{ tr('Impressora') }}
      </button>
    </ModuleHeader>
    <main class="labels-main">
      <p class="labels-intro">
        {{
          tr(
            'Confira os produtos, escolha as quantidades e imprima as etiquetas para colar nas peças.',
          )
        }}
      </p>
      <p v-if="error" role="alert" class="labels-error">{{ error }}</p>
      <section v-if="setupOpen && auth.isOwner" class="labels-panel setup-panel">
        <h2>{{ tr('Zebra · etiquetas 60 × 30 mm') }}</h2>
        <p>
          {{
            tr(
              'Use a Zebra no Windows com etiquetas de 60 mm de largura e 30 mm de altura, uma por fileira. Os tickets continuam na 3nStar.',
            )
          }}
        </p>
        <p>
          {{
            tr(
              'Feche o antigo Eleven Tickets da Zebra. A configuração preserva o histórico e substitui a credencial antiga. Trabalhos pendentes devem ser concluídos antes da troca.',
            )
          }}
        </p>
        <label class="confirm-line"
          ><input v-model="setupConfirmed" type="checkbox" />{{
            tr('Confirmo a Zebra exclusiva para etiquetas de produtos.')
          }}</label
        >
        <div class="labels-actions">
          <button
            type="button"
            class="erp-button erp-button--primary erp-button--sm"
            :disabled="busy || !setupConfirmed"
            @click="configure(false)"
          >
            {{ tr(device ? 'Conferir configuração' : 'Configurar Zebra para etiquetas') }}
          </button>
          <button
            v-if="device"
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="busy || !setupConfirmed"
            @click="configure(true)"
          >
            {{ tr('Gerar nova credencial') }}
          </button>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="busy"
            @click="downloadInstaller"
          >
            {{ tr('Baixar agente Windows') }}
          </button>
        </div>
        <template v-if="token">
          <label
            >{{ tr('Credencial exclusiva do agente')
            }}<input
              :value="token"
              readonly
              autocomplete="off"
              spellcheck="false"
              @focus="($event.target as HTMLInputElement).select()"
          /></label>
          <p>
            {{
              tr(
                'Copie esta credencial no instalador. Ela aparece somente agora; não compartilhe com clientes.',
              )
            }}
          </p>
        </template>
        <p>
          {{
            tr(
              'Extraia o ZIP, abra Instalar.cmd e selecione a fila USB da Zebra. Depois abra Eleven Etiquetas na Área de Trabalho. Este perfil não usa Sumatra.',
            )
          }}
        </p>
      </section>
      <div class="device-strip">
        <span
          ><strong>{{ device?.name || tr('Impressora ainda não configurada') }}</strong> · 60 × 30
          mm</span
        ><small>{{ tr('O Windows e o agente precisam estar ligados para imprimir.') }}</small>
      </div>
      <nav class="labels-tabs" :aria-label="tr('Etiquetas de produtos')">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          type="button"
          class="erp-control"
          :class="{ active: panel === tab.value }"
          :aria-pressed="panel === tab.value"
          @click="panel = tab.value"
        >
          {{ tab.label }}<span v-if="tab.value === 'selection'"> {{ selected.length }}</span>
        </button>
      </nav>
      <section v-if="panel === 'catalog'" class="labels-panel">
        <div class="labels-search">
          <ErpDropdown v-model="mode" :options="modes" :label="tr('Selecionar por')" />
          <form class="labels-search-form" @submit.prevent="search">
            <input
              v-model="query"
              type="search"
              :placeholder="tr('Produto, código, grade ou lote...')"
              :aria-label="tr('Buscar')"
            />
            <button type="submit" class="erp-button erp-button--secondary erp-button--sm">
              {{ tr('Buscar') }}
            </button>
          </form>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--icon"
            :aria-label="tr('Escanear Código')"
            @click="scannerOpen = true"
          >
            <Camera :size="18" />
          </button>
        </div>
        <p v-if="loading" role="status">{{ tr('Carregando...') }}</p>
        <p v-else-if="!catalog.length">{{ tr('Nenhum resultado encontrado.') }}</p>
        <div class="labels-actions">
          <span>{{ tr('{count} resultados', { count: total }) }}</span
          ><button
            v-if="catalog.length"
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="locked || busy || loading"
            @click="addPage"
          >
            {{ tr('Selecionar esta página') }}
          </button>
        </div>
        <div v-for="entry in catalog" :key="entryKey(entry)" class="catalog-row">
          <div class="label-identity">
            <strong>{{ entry.name }}</strong
            ><small v-if="mode === 'products'"
              >{{ (entry as LabelProduct).color }} · {{ (entry as LabelProduct).size }} ·
              {{ (entry as LabelProduct).inventory_code }}</small
            ><small v-if="mode === 'products'"
              >{{ tr('Preço de venda') }}:
              {{
                formatLabelSalePrice(
                  (entry as LabelProduct).sale_price,
                  (entry as LabelProduct).sale_currency,
                  numberLocale(),
                )
              }}</small
            ><small v-else-if="mode === 'grades'">{{ (entry as LabelCollection).group_key }}</small
            ><small v-else
              >{{ (entry as LabelCollection).received_on }} ·
              {{ (entry as LabelCollection).notes }}</small
            >
          </div>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="locked || busy || loading || isSelected(entry)"
            :aria-label="`${tr('Selecionar')} ${entry.name}`"
            @click="add([entry])"
          >
            {{
              tr(
                isSelected(entry)
                  ? 'Selecionado'
                  : mode === 'products'
                    ? 'Selecionar'
                    : 'Adicionar todos',
              )
            }}
          </button>
        </div>
        <div class="pagination">
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="loading || page === 1"
            @click="changePage(-1)"
          >
            ← {{ tr('Anterior') }}</button
          ><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 30)) }}</span
          ><button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="loading || page * 30 >= total"
            @click="changePage(1)"
          >
            {{ tr('Próxima') }} →
          </button>
        </div>
      </section>
      <section v-else-if="panel === 'selection'" class="labels-panel">
        <h2>
          {{ tr('Conferir etiquetas') }}
          <small
            >{{ selected.length }} {{ tr('produtos') }} · {{ copies }} {{ tr('etiquetas') }}</small
          >
        </h2>
        <p>
          {{
            tr(
              'A quantidade representa etiquetas, sem alterar o estoque. Cada tamanho e cor mantém seu código interno.',
            )
          }}
        </p>
        <p v-if="attempt" role="alert" class="labels-warning">
          {{
            tr(
              'Confirmação pendente. Consulte novamente com o mesmo pedido para evitar impressão duplicada.',
            )
          }}
        </p>
        <div class="label-layout-choice">
          <ErpDropdown
            v-if="layouts.length"
            v-model="selectedLayoutId"
            :options="
              layouts.map((layout) => ({
                value: layout.id,
                label: layout.builtin ? tr(layout.name) : layout.name,
              }))
            "
            :label="tr('Modelo deste envio')"
            :disabled="locked || busy"
          />
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="locked || busy"
            @click="panel = 'layout'"
          >
            {{ tr('Editar layout') }}
          </button>
          <button
            type="button"
            class="erp-button erp-button--ghost erp-button--sm"
            :disabled="locked || busy"
            @click="loadLayouts"
          >
            {{ tr('Atualizar modelos') }}
          </button>
        </div>
        <div v-if="attempt" class="labels-actions">
          <button
            type="button"
            class="erp-button erp-button--primary"
            :disabled="busy"
            @click="submit"
          >
            {{ tr('Recuperar confirmação') }}
          </button>
        </div>
        <fieldset :disabled="locked || busy">
          <div v-if="selected.length" class="quantity-toolbar">
            <ErpDropdown v-model="scope" :options="scopes" :label="tr('Aplicar quantidade a')" />
            <ErpDropdown
              v-model="quantityMode"
              :options="quantityModes"
              :label="tr('Quantidade de etiquetas')"
            />
            <input
              v-if="quantityMode === 'manual'"
              v-model.number="bulkQuantity"
              type="number"
              min="1"
              max="100"
              inputmode="numeric"
              :aria-label="tr('Quantidade')"
            />
            <button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              @click="applyQuantity"
            >
              {{ tr('Aplicar') }}
            </button>
          </div>
          <p v-if="!selected.length">
            {{ tr('Selecione produtos, grades ou lotes para começar.') }}
          </p>
          <div v-for="item in selected" :key="item.id" class="selected-row">
            <div class="label-identity">
              <strong>{{ item.name }}</strong
              ><small>{{ item.color }} · {{ item.size }} · {{ item.inventory_code }}</small
              ><small
                >{{ tr('Loja') }}: {{ item.stock_loja ?? '—' }} · {{ tr('Depósito') }}:
                {{ item.stock_deposito ?? '—' }}</small
              ><small
                >{{ tr('Preço de venda') }}:
                {{
                  formatLabelSalePrice(item.sale_price, item.sale_currency, numberLocale())
                }}</small
              >
            </div>
            <div class="row-actions">
              <div class="stepper">
                <button
                  type="button"
                  class="erp-button erp-button--secondary erp-button--icon"
                  :disabled="item.copies <= 1"
                  :aria-label="`${tr('Diminuir')} ${item.name}`"
                  @click="item.copies--"
                >
                  −</button
                ><input
                  v-model.number="item.copies"
                  type="number"
                  min="1"
                  max="100"
                  inputmode="numeric"
                  :aria-label="`${tr('Quantidade')} ${item.name}`"
                /><button
                  type="button"
                  class="erp-button erp-button--secondary erp-button--icon"
                  :disabled="item.copies >= 100"
                  :aria-label="`${tr('Aumentar')} ${item.name}`"
                  @click="item.copies++"
                >
                  +
                </button>
              </div>
              <button
                type="button"
                class="erp-button erp-button--ghost erp-button--icon"
                :aria-label="`${tr('Prévia')} ${item.name}`"
                @click="showPreview(item)"
              >
                <Eye :size="18" /></button
              ><button
                type="button"
                class="erp-button erp-button--ghost erp-button--icon"
                :aria-label="`${tr('Remover')} ${item.name}`"
                @click="selected = selected.filter((p) => p.id !== item.id)"
              >
                ×
              </button>
            </div>
          </div>
        </fieldset>
        <p v-if="selected.length && !validSelection" role="status" class="labels-warning">
          {{
            tr(
              'Confira os códigos e quantidades: até 500 produtos, 100 cópias por produto e 2.000 etiquetas por envio.',
            )
          }}
        </p>
        <div v-if="selected.length" class="labels-confirm">
          <label class="confirm-line"
            ><input v-model="confirmed" type="checkbox" :disabled="locked || busy" />{{
              tr('Conferi os produtos, as quantidades e o papel 60 × 30 mm na Zebra.')
            }}</label
          >
          <button
            type="button"
            class="erp-button erp-button--primary"
            :disabled="busy || locked || !confirmed || !device || !validSelection"
            @click="submit"
          >
            <Printer :size="18" />{{ tr('Imprimir {count} etiquetas', { count: copies }) }}
          </button>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="locked || busy"
            @click="clearSelection"
          >
            {{ tr('Limpar seleção') }}
          </button>
        </div>
      </section>
      <section v-else-if="panel === 'queue'" class="labels-panel">
        <div class="labels-actions">
          <h2>{{ tr('Fila de etiquetas') }}</h2>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="busy"
            @click="refreshQueue"
          >
            {{ tr('Atualizar') }}
          </button>
        </div>
        <p>
          {{
            tr(
              'Enviado significa aceito pelo spooler. Confira o papel antes de solicitar novas cópias.',
            )
          }}
        </p>
        <ErpDropdown
          v-if="history.length"
          v-model="batchId"
          :options="
            history.map((b) => ({
              value: b.id,
              label: `${new Date(b.created_at).toLocaleString()} · ${b.name}`,
            }))
          "
          :label="tr('Impressões recentes')"
        />
        <p v-if="!history.length && !batch">{{ tr('Nenhuma impressão solicitada.') }}</p>
        <template v-if="batch">
          <p>
            <strong>{{ batch.total }} {{ tr('etiquetas') }}</strong> · {{ batch.jobs.length }}
            {{ tr('produtos') }}
          </p>
          <article v-for="job in batch.jobs" :key="job.id" class="job-row">
            <div class="label-identity">
              <strong>{{ job.name }}</strong
              ><small
                >{{ job.color }} · {{ job.size }} · {{ job.code }} · {{ job.copies }}
                {{ tr('etiquetas') }}</small
              >
              <p v-if="job.diagnostic_message">{{ tr(job.diagnostic_message) }}</p>
            </div>
            <span class="job-status" :class="job.status">{{ statusText(job.status) }}</span>
          </article>
          <template v-if="batch.jobs.some((j) => j.status === 'pending')"
            ><label class="confirm-line"
              ><input v-model="cancelConfirmed" type="checkbox" />{{
                tr('Cancelar somente as etiquetas ainda não recolhidas pelo agente.')
              }}</label
            ><button
              type="button"
              class="erp-button erp-button--danger erp-button--sm"
              :disabled="busy || !cancelConfirmed"
              @click="cancelBatch"
            >
              {{ tr('Cancelar pendentes') }}
            </button></template
          >
        </template>
      </section>
      <ProductLabelLayoutEditor
        v-if="editorOpened && layouts.length"
        v-show="panel === 'layout'"
        :layouts="layouts"
        :products="selected"
        :active-id="selectedLayoutId"
        :disabled="locked || busy"
        @saved="layoutSaved"
        @deleted="layoutDeleted"
        @use="useLayout"
        @refresh="loadLayouts"
      />
      <section v-else-if="panel === 'layout'" class="labels-panel">
        <p>{{ tr('Carregando modelos...') }}</p>
        <button
          type="button"
          class="erp-button erp-button--secondary erp-button--sm"
          @click="loadLayouts"
        >
          {{ tr('Tentar novamente') }}
        </button>
      </section>
    </main>
    <BarcodeScanner v-if="scannerOpen" @close="scannerOpen = false" @barcode-detected="scan" />
    <Teleport to="body"
      ><div v-if="previewOpen" class="erp-dialog-backdrop" @click.self="closePreview">
        <section v-erp-dialog class="erp-dialog erp-dialog--sm">
          <header class="erp-dialog__header">
            <h2>{{ tr('Prévia da etiqueta') }}</h2>
            <button
              data-dialog-close
              type="button"
              class="erp-button erp-button--ghost erp-button--icon"
              :aria-label="tr('Fechar')"
              @click="closePreview"
            >
              ×
            </button>
          </header>
          <div class="erp-dialog__body">
            <img
              v-if="previewUrl"
              :src="previewUrl"
              :alt="tr('Etiqueta ELEVEN de 60 × 30 mm')"
              class="label-preview"
            />
            <p v-else>{{ tr('Carregando...') }}</p>
            <p>
              {{
                tr(
                  '60 mm × 30 mm. Confira a primeira etiqueta impressa antes de enviar um lote grande.',
                )
              }}
            </p>
          </div>
        </section>
      </div></Teleport
    >
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue'
import { Camera, Eye, Printer } from 'lucide-vue-next'
import ModuleHeader from '@/components/ModuleHeader.vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import { vErpDialog } from '@/directives/erpDialog'
import { useInventoryI18n } from '@/components/inventory/i18n'
import { useAuthStore } from '@/stores/auth'
import { labelLayoutReference, type ProductLabelLayout } from '@/services/productLabelDesign'
const ProductLabelLayoutEditor = defineAsyncComponent(
  () => import('@/components/inventory/ProductLabelLayoutEditor.vue'),
)
import {
  productLabels as api,
  formatLabelSalePrice,
  labelRequest,
  mergeLabelSelection,
  type LabelProduct,
  type LabelCollection,
  type LabelDevice,
  type LabelRequest,
  type LabelBatch,
  type LabelSelection,
} from '@/services/productLabels'
const { tr, numberLocale } = useInventoryI18n()
const auth = useAuthStore()
const panel = ref('catalog'),
  mode = ref<'products' | 'grades' | 'lots'>('products'),
  query = ref(''),
  page = ref(1),
  total = ref(0)
const catalog = ref<(LabelProduct | LabelCollection)[]>([]),
  selected = ref<(LabelProduct & { copies: number })[]>([])
const device = ref<LabelDevice | null>(null),
  error = ref(''),
  loading = ref(false),
  busy = ref(false),
  confirmed = ref(false)
const scope = ref('all'),
  quantityMode = ref('manual'),
  bulkQuantity = ref(1)
const setupOpen = ref(false),
  setupConfirmed = ref(false),
  token = ref(''),
  scannerOpen = ref(false)
const previewOpen = ref(false),
  previewUrl = ref(''),
  batch = ref<LabelBatch | null>(null),
  batchId = ref(''),
  cancelConfirmed = ref(false)
const history = ref<{ id: string; name: string; created_at: string }[]>([]),
  attempt = ref<LabelRequest | null>(null)
const storageKey = `eleven-label-confirmation:${auth.user?.id || ''}`
const layoutStorageKey = `eleven-label-layout:${auth.user?.id || ''}`
const layouts = ref<ProductLabelLayout[]>([]),
  selectedLayoutId = ref('standard'),
  editorOpened = ref(false)
const activeLayout = computed(() =>
  layouts.value.find((layout) => layout.id === selectedLayoutId.value),
)
let generation = 0,
  disposed = false,
  previewGeneration = 0,
  layoutsGeneration = 0
const locked = computed(() => !!attempt.value)
const copies = computed(() => selected.value.reduce((n, p) => n + (Number(p.copies) || 0), 0))
const validSelection = computed(() => {
  try {
    if (selectedLayoutId.value !== 'standard' && !activeLayout.value) return false
    labelRequest(selected.value, 'preview', activeLayout.value)
    return true
  } catch {
    return false
  }
})
const tabs = computed(() => [
  { value: 'catalog', label: tr('Selecionar') },
  { value: 'selection', label: tr('Conferir') },
  { value: 'layout', label: tr('Layout') },
  { value: 'queue', label: tr('Fila') },
])
const modes = computed(() => [
  { value: 'products', label: tr('Produtos') },
  { value: 'grades', label: tr('Grades') },
  { value: 'lots', label: tr('Lotes de recebimento') },
])
const quantityModes = computed(() => [
  { value: 'manual', label: tr('Quantidade definida') },
  { value: 'stock_loja', label: tr('Saldo da loja') },
  { value: 'stock_deposito', label: tr('Saldo do depósito') },
  { value: 'current_stock', label: tr('Saldo total') },
])
const scopes = computed(() => [
  { value: 'all', label: tr('Todos os selecionados') },
  ...[...new Set(selected.value.map((p) => p.color).filter(Boolean))].map((c) => ({
    value: `color:${c}`,
    label: `${tr('Cor')}: ${c}`,
  })),
  ...[...new Set(selected.value.map((p) => p.size).filter(Boolean))].map((s) => ({
    value: `size:${s}`,
    label: `${tr('Tamanho')}: ${s}`,
  })),
])
function failure(e: unknown) {
  const detail = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  error.value = tr(
    typeof detail === 'string'
      ? detail
      : e instanceof Error
        ? e.message
        : 'Não foi possível concluir. Tente novamente.',
  )
}
async function loadLayouts() {
  const request = ++layoutsGeneration
  try {
    const result = await api.layouts()
    if (disposed || request !== layoutsGeneration) return
    layouts.value = result
    if (!attempt.value && !layouts.value.some((layout) => layout.id === selectedLayoutId.value)) {
      selectedLayoutId.value = 'standard'
      error.value = tr('Modelo indisponível. Padrão ELEVEN selecionado; confira a prévia.')
    }
  } catch (e) {
    if (!disposed && request === layoutsGeneration) failure(e)
  }
}
function layoutSaved(layout: ProductLabelLayout) {
  layoutsGeneration++
  layouts.value = [...layouts.value.filter((entry) => entry.id !== layout.id), layout]
  if (!locked.value) selectedLayoutId.value = layout.id
  confirmed.value = false
}
function layoutDeleted(id: string) {
  layoutsGeneration++
  layouts.value = layouts.value.filter((layout) => layout.id !== id)
  if (!locked.value && selectedLayoutId.value === id) selectedLayoutId.value = 'standard'
}
function useLayout(id: string) {
  selectedLayoutId.value = id
  confirmed.value = false
  panel.value = 'selection'
}
watch(
  () => `${selectedLayoutId.value}:${activeLayout.value?.version}`,
  () => {
    confirmed.value = false
    if (!attempt.value) {
      try {
        localStorage.setItem(layoutStorageKey, selectedLayoutId.value)
      } catch {
        /* Preference only. */
      }
    }
  },
)
async function loadCatalog() {
  const request = ++generation
  loading.value = true
  try {
    const data = await api.catalog(mode.value, query.value, page.value)
    if (!disposed && request === generation) {
      catalog.value = data.items
      total.value = data.total
    }
  } catch (e) {
    if (request === generation) failure(e)
  } finally {
    if (!disposed && request === generation) loading.value = false
  }
}
function clearSelection() {
  selected.value = []
  confirmed.value = false
}
function search() {
  page.value = 1
  void loadCatalog()
}
function changePage(delta: number) {
  page.value += delta
  void loadCatalog()
}
watch(mode, search)
watch(
  selected,
  () => {
    confirmed.value = false
  },
  { deep: true },
)
function entryKey(entry: LabelProduct | LabelCollection) {
  return entry.id || entry.group_key || entry.name
}
function isSelected(entry: LabelProduct | LabelCollection) {
  return mode.value === 'products' && selected.value.some((p) => p.id === entry.id)
}
async function add(entries: (LabelProduct | LabelCollection)[]) {
  const body: LabelSelection =
    mode.value === 'products'
      ? { item_ids: entries.map((e) => e.id!) }
      : mode.value === 'grades'
        ? { group_keys: entries.map((e) => e.group_key!) }
        : { lot_ids: entries.map((e) => e.id!) }
  await addSelection(body)
}
async function addSelection(body: LabelSelection) {
  if (locked.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const incoming = await api.selection(body)
    const merged = mergeLabelSelection(selected.value, incoming)
    if (merged.length > 500) throw new Error('Selecione até 500 produtos por vez.')
    selected.value = merged
    if (!incoming.length) throw new Error('Nenhum produto ativo nesta seleção.')
  } catch (e) {
    failure(e)
  } finally {
    busy.value = false
  }
}
function addPage() {
  void add(catalog.value)
}
function applyQuantity() {
  error.value = ''
  const targets = selected.value.filter(
    (p) =>
      scope.value === 'all' ||
      scope.value === `color:${p.color}` ||
      scope.value === `size:${p.size}`,
  )
  const values = targets.map((p) =>
    quantityMode.value === 'manual'
      ? bulkQuantity.value
      : p[quantityMode.value as 'stock_loja' | 'stock_deposito' | 'current_stock'],
  )
  if (values.some((v) => v === null || !Number.isInteger(v) || v < 1 || v > 100)) {
    error.value = tr(
      'Use quantidades de 1 a 100. Produtos sem saldo conhecido ou com saldo zero devem ser ajustados ou removidos da seleção.',
    )
    return
  }
  targets.forEach((p, i) => {
    p.copies = values[i]!
  })
}
async function submit() {
  if (busy.value || (!attempt.value && (!confirmed.value || !device.value))) return
  busy.value = true
  error.value = ''
  try {
    if (!attempt.value) {
      const body = labelRequest(selected.value, crypto.randomUUID(), activeLayout.value)
      sessionStorage.setItem(storageKey, JSON.stringify(body))
      attempt.value = body
    }
    const result = await api.enqueue(attempt.value)
    sessionStorage.removeItem(storageKey)
    attempt.value = null
    selected.value = []
    confirmed.value = false
    batch.value = result
    batchId.value = result.id
    panel.value = 'queue'
    history.value = await api.history()
  } catch (e) {
    const status = (e as { response?: { status?: number } }).response?.status
    if (status && (status === 409 || status === 422)) {
      sessionStorage.removeItem(storageKey)
      attempt.value = null
    }
    failure(e)
  } finally {
    busy.value = false
  }
}
async function refreshQueue() {
  busy.value = true
  try {
    history.value = await api.history()
    if (batchId.value) batch.value = await api.batch(batchId.value)
  } catch (e) {
    failure(e)
  } finally {
    busy.value = false
  }
}
watch(panel, (value) => {
  if (value === 'queue') void refreshQueue()
  if (value === 'layout') editorOpened.value = true
})
watch(batchId, async (value) => {
  if (!value) return
  cancelConfirmed.value = false
  try {
    batch.value = await api.batch(value)
  } catch (e) {
    failure(e)
  }
})
async function cancelBatch() {
  if (!batch.value || !cancelConfirmed.value || busy.value) return
  busy.value = true
  try {
    batch.value = await api.cancel(batch.value.id)
    cancelConfirmed.value = false
  } catch (e) {
    failure(e)
  } finally {
    busy.value = false
  }
}
function statusText(value: string) {
  return tr(
    (
      {
        pending: 'Na fila',
        claimed: 'Em processamento',
        submitted: 'Enviado',
        uncertain: 'Conferir impressão',
        failed: 'Falhou',
        cancelled: 'Cancelado',
      } as Record<string, string>
    )[value] || value,
  )
}
async function configure(rotate: boolean) {
  if (!setupConfirmed.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await api.configure(rotate)
    device.value = result.device
    token.value = result.token || token.value
    setupConfirmed.value = false
  } catch (e) {
    failure(e)
  } finally {
    busy.value = false
  }
}
async function downloadInstaller() {
  busy.value = true
  try {
    const blob = await api.installer()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'Eleven-Etiquetas-Windows.zip'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) {
    failure(e)
  } finally {
    busy.value = false
  }
}
async function showPreview(item: LabelProduct) {
  closePreview()
  previewOpen.value = true
  const request = ++previewGeneration
  try {
    const blob = await api.preview(item.id, labelLayoutReference(activeLayout.value))
    if (previewOpen.value && request === previewGeneration && !disposed)
      previewUrl.value = URL.createObjectURL(blob)
  } catch (e) {
    closePreview()
    failure(e)
  }
}
function closePreview() {
  previewGeneration++
  previewOpen.value = false
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}
function scan(code: string) {
  scannerOpen.value = false
  query.value = code
  mode.value = 'products'
  search()
}
onMounted(async () => {
  try {
    try {
      selectedLayoutId.value = localStorage.getItem(layoutStorageKey) || 'standard'
    } catch {
      /* Preference only. */
    }
    const saved = sessionStorage.getItem(storageKey)
    if (saved) {
      const recovered: LabelRequest = JSON.parse(saved)
      attempt.value = recovered
      selectedLayoutId.value = recovered.layout_id || 'standard'
      selected.value = recovered.items.map((p) => ({
        id: p.item_id,
        name: p.name,
        inventory_code: p.code,
        color: p.color,
        size: p.size,
        copies: p.copies,
        sale_price: p.sale_price ?? null,
        sale_currency: p.sale_currency ?? null,
        group_key: null,
        stock_loja: null,
        stock_deposito: null,
        current_stock: null,
      }))
      panel.value = 'selection'
    }
    const state = window.history.state?.labelItemIds
    if (Array.isArray(state) && state.length && !attempt.value) {
      await addSelection({ item_ids: state })
      panel.value = 'selection'
      window.history.replaceState({ ...window.history.state, labelItemIds: undefined }, '')
    }
    device.value = (await api.device()).device
    await loadLayouts()
    await loadCatalog()
  } catch (e) {
    failure(e)
  }
})
onUnmounted(() => {
  disposed = true
  generation++
  closePreview()
  token.value = ''
})
</script>

<style scoped>
.labels-view {
  min-height: 100dvh;
  background: #f6f8fb;
  color: #1e293b;
}
.labels-main {
  max-width: 1100px;
  margin: auto;
  padding: 0 16px 30px;
}
.labels-intro,
.labels-panel p,
.device-strip small {
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.labels-panel {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 18px;
  margin: 14px 0;
  min-width: 0;
}
.labels-panel h2 {
  font-size: 17px;
  margin: 0 0 10px;
}
.labels-panel h2 small {
  font-size: 12px;
  color: #64748b;
  font-weight: 400;
}
.device-strip {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 13px;
  padding: 12px;
  background: #eaf3ff;
  border-radius: 12px;
}
.labels-tabs {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}
.labels-tabs button {
  border: 1px solid #dbe3ef;
  border-radius: 999px;
  padding: 8px 18px;
  background: white;
}
.labels-tabs span {
  margin-left: 6px;
  font-size: 12px;
}
.labels-tabs .active {
  background: #eaf1ff;
  border-color: #2563eb;
  color: #1d4ed8;
}
.labels-search,
.label-layout-choice,
.labels-actions,
.quantity-toolbar,
.pagination {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.label-layout-choice {
  margin: 14px 0;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}
.label-layout-choice > .erp-dropdown {
  flex: 1;
  min-width: 180px;
}
.labels-search {
  margin-bottom: 14px;
}
.labels-search > :first-child {
  width: 170px;
}
.labels-search-form {
  display: flex;
  flex: 1;
  gap: 8px;
  min-width: 180px;
}
.labels-view input:not([type='checkbox']) {
  min-width: 0;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 8px;
  font-size: 16px;
  line-height: 1.25;
  box-sizing: border-box;
}
.labels-search input {
  flex: 1;
  width: 100%;
}
.catalog-row,
.selected-row,
.job-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid #edf0f5;
}
.label-identity {
  min-width: 0;
  flex: 1;
}
.label-identity strong {
  display: block;
  font-size: 14px;
  overflow-wrap: anywhere;
}
.label-identity small {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
  overflow-wrap: anywhere;
}
.label-identity p {
  margin: 4px 0;
}
.pagination {
  justify-content: center;
  margin-top: 18px;
  font-size: 13px;
}
.quantity-toolbar {
  padding: 12px 0;
  border-bottom: 1px solid #e2e8f0;
}
.quantity-toolbar .erp-dropdown {
  flex: 1;
  min-width: 150px;
}
.quantity-toolbar > input {
  width: 65px;
}
.labels-view fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.row-actions,
.stepper {
  display: flex;
  align-items: center;
  gap: 5px;
}
.stepper input {
  width: 56px;
  text-align: center;
  appearance: textfield;
}
.stepper input::-webkit-inner-spin-button {
  appearance: none;
}
.labels-view .erp-button--icon {
  width: 34px;
  min-width: 34px;
  height: 36px;
  min-height: 36px;
  padding: 4px;
}
.labels-confirm {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding-top: 16px;
}
.confirm-line {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
  line-height: 1.45;
  margin: 12px 0;
  width: 100%;
}
.confirm-line input {
  flex: none;
  width: 18px;
  height: 18px;
  margin: 0;
}
.labels-error {
  color: #b91c1c !important;
  background: #fff1f2;
  padding: 12px;
  border-radius: 10px;
}
.labels-warning {
  color: #92400e !important;
  background: #fffbeb;
  padding: 12px;
  border-radius: 10px;
}
.job-status {
  font-size: 12px;
  white-space: nowrap;
  background: #eaf1ff;
  border-radius: 999px;
  padding: 6px 10px;
}
.job-status.uncertain,
.job-status.failed {
  background: #fff1d6;
  color: #92400e;
}
.job-status.submitted {
  background: #dcfce7;
  color: #166534;
}
.setup-panel input:not([type='checkbox']) {
  display: block;
  width: 100%;
  margin-top: 8px;
}
.label-preview {
  width: 100%;
  height: auto;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
}
.labels-view button:disabled {
  opacity: 0.5;
}
@media (max-width: 600px) {
  .labels-main {
    padding: 0 10px 20px;
  }
  .labels-panel {
    padding: 12px;
    border-radius: 14px;
  }
  .selected-row {
    flex-wrap: wrap;
    gap: 8px;
  }
  .selected-row .label-identity {
    flex-basis: 100%;
  }
  .selected-row .row-actions {
    margin-left: auto;
  }
  .labels-search > :first-child {
    width: calc(100% - 44px);
    order: 0;
  }
  .labels-search-form {
    order: 2;
    flex-basis: 100%;
  }
  .labels-search > .erp-button {
    order: 1;
  }
  .labels-confirm > .erp-button--primary {
    width: 100%;
  }
  .quantity-toolbar .erp-dropdown {
    min-width: calc(50% - 8px);
  }
  .job-row {
    align-items: flex-start;
  }
  .job-status {
    font-size: 11px;
  }
  .labels-tabs button {
    flex: 1;
    padding: 8px 12px;
  }
}
</style>
