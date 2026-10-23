<template>
  <section class="design-editor labels-panel">
    <div class="design-heading">
      <div>
        <h2>{{ tr('Editor de etiquetas') }}</h2>
        <p>
          {{
            tr(
              'Arraste os campos ou ajuste as medidas. A prévia usa o mesmo desenho enviado à Zebra.',
            )
          }}
        </p>
      </div>
      <span class="design-paper">60 × 30 mm · {{ tr('Preto e branco') }}</span>
    </div>
    <div class="design-models">
      <ErpDropdown
        :model-value="editingId"
        :options="layouts.map((l) => ({ value: l.id, label: l.builtin ? tr(l.name) : l.name }))"
        :label="tr('Modelo de etiqueta')"
        :disabled="working || disabled"
        @update:model-value="requestLayout"
      />
      <input
        v-model="name"
        :aria-label="tr('Nome do modelo')"
        :placeholder="tr('Ex.: Roupas, calçados, acessórios')"
        maxlength="100"
        :disabled="working || disabled"
      />
      <button
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        :disabled="!canSave || editingId === 'standard' || !dirty || remoteChanged"
        @click="save(false)"
      >
        {{ tr('Salvar alterações') }}
      </button>
      <button
        type="button"
        class="erp-button erp-button--primary erp-button--sm"
        :disabled="!canSave"
        @click="save(true)"
      >
        {{ tr('Salvar como novo') }}
      </button>
      <button
        type="button"
        class="erp-button erp-button--ghost erp-button--sm"
        :disabled="working || disabled"
        @click="emit('refresh')"
      >
        {{ tr('Atualizar modelos') }}
      </button>
    </div>
    <div v-if="remoteChanged" class="design-notice" role="status">
      <p>
        {{
          tr(
            'Este modelo foi alterado ou removido em outro aparelho. Você pode salvar sua edição como novo modelo.',
          )
        }}
      </p>
      <button
        v-if="layouts.some((l) => l.id === editingId)"
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        @click="loadLayout(editingId)"
      >
        {{ tr('Descartar alterações e atualizar') }}
      </button>
    </div>
    <div v-if="pendingId" class="design-notice" role="status">
      <p>{{ tr('Há alterações não salvas neste modelo.') }}</p>
      <button
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        @click="loadLayout(pendingId)"
      >
        {{ tr('Descartar e abrir') }}
      </button>
      <button
        type="button"
        class="erp-button erp-button--ghost erp-button--sm"
        @click="pendingId = ''"
      >
        {{ tr('Continuar editando') }}
      </button>
    </div>
    <p v-if="message" class="design-success" role="status">{{ message }}</p>
    <p v-if="error || localIssue || previewError" class="design-error" role="alert">
      {{ tr(error || localIssue || previewError) }}
    </p>
    <p v-if="disabled" class="design-notice">
      {{ tr('Conclua a confirmação pendente antes de alterar o modelo deste envio.') }}
    </p>
    <div class="design-workspace">
      <div class="design-board">
        <div class="design-tools">
          <ErpDropdown
            v-model="sampleId"
            :options="sampleOptions"
            :label="tr('Produto da prévia')"
            :disabled="working"
          />
          <ErpDropdown
            v-model="zoom"
            :options="[
              { value: 1, label: '100%' },
              { value: 1.5, label: '150%' },
              { value: 2, label: '200%' },
            ]"
            :label="tr('Zoom da prévia')"
            compact
          />
          <button
            type="button"
            class="erp-button erp-button--ghost erp-button--sm"
            :disabled="!undoStack.length || disabled || working"
            @click="undo"
          >
            {{ tr('Desfazer') }}
          </button>
          <button
            type="button"
            class="erp-button erp-button--ghost erp-button--sm"
            :disabled="!redoStack.length || disabled || working"
            @click="redo"
          >
            {{ tr('Refazer') }}
          </button>
        </div>
        <div class="design-scroll">
          <div
            ref="canvas"
            class="design-canvas"
            :style="{ width: `${zoom * 100}%` }"
            :aria-label="tr('Área da etiqueta')"
          >
            <img
              v-if="previewUrl"
              :src="previewUrl"
              alt=""
              class="design-raster"
              draggable="false"
            />
            <span v-else class="design-placeholder">{{ tr('Preparando prévia...') }}</span>
            <button
              v-for="element in visibleElements"
              :key="element.id"
              type="button"
              class="design-object erp-control"
              :class="{ selected: selectedId === element.id, 'design-qr': element.type === 'qr' }"
              :style="elementStyle(element)"
              :aria-label="`${tr('Mover campo')}: ${elementLabel(element)}`"
              :aria-pressed="selectedId === element.id"
              :disabled="disabled || working"
              @click="selectedId = element.id"
              @pointerdown="startDrag($event, element)"
              @pointermove="moveDrag"
              @pointerup="endDrag"
              @pointercancel="endDrag"
              @lostpointercapture="endDrag"
              @keydown="moveWithKeys($event, element)"
            >
              <span v-if="selectedId === element.id" class="design-object-caption">{{
                elementLabel(element)
              }}</span>
            </button>
          </div>
        </div>
        <div class="design-caption">
          <span>{{
            tr('QR e código interno identificam o produto e permanecem na etiqueta.')
          }}</span
          ><span v-if="previewBusy" role="status">{{ tr('Atualizando prévia...') }}</span>
        </div>
        <div class="design-add">
          <ErpDropdown
            v-model="fieldToAdd"
            :options="addOptions"
            :label="tr('Adicionar campo')"
            :disabled="disabled || working"
          />
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="disabled || working || config.elements.length >= 16"
            @click="addElement"
          >
            + {{ tr('Adicionar campo') }}
          </button>
          <button
            type="button"
            class="erp-button erp-button--ghost erp-button--sm"
            :disabled="disabled || working"
            @click="restore"
          >
            {{ tr('Restaurar padrão') }}
          </button>
        </div>
        <p class="design-help">
          {{
            tr(
              'Use as setas do teclado para mover o campo selecionado. Shift move 1 mm. O contorno do QR inclui a margem branca necessária para leitura.',
            )
          }}
        </p>
      </div>
      <aside class="design-properties">
        <ErpDropdown
          :model-value="selectedId"
          :options="config.elements.map((e) => ({ value: e.id, label: elementLabel(e) }))"
          :label="tr('Campo selecionado')"
          @update:model-value="selectedId = $event"
        />
        <fieldset v-if="current" :disabled="disabled || working">
          <div class="design-measures">
            <label
              >X (mm)<input
                type="number"
                :value="current.x / 8"
                min="0"
                max="60"
                step="0.25"
                inputmode="decimal"
                @change="geometry('x', $event)"
            /></label>
            <label
              >Y (mm)<input
                type="number"
                :value="current.y / 8"
                min="0"
                max="30"
                step="0.25"
                inputmode="decimal"
                @change="geometry('y', $event)"
            /></label>
            <template v-if="current.type !== 'qr'">
              <label
                >{{ tr('Largura (mm)')
                }}<input
                  type="number"
                  :value="current.width / 8"
                  :min="current.type === 'text' ? (current.field === 'code' ? 11.25 : 2) : 0.125"
                  max="60"
                  step="0.25"
                  inputmode="decimal"
                  @change="geometry('width', $event)"
              /></label>
              <label
                >{{ tr('Altura (mm)')
                }}<input
                  type="number"
                  :value="current.height / 8"
                  :min="current.type === 'text' ? (current.field === 'code' ? 1.5 : 1) : 0.125"
                  :max="current.type === 'line' ? 1 : 30"
                  step="0.25"
                  inputmode="decimal"
                  @change="geometry('height', $event)"
              /></label>
            </template>
          </div>
          <template v-if="current.type === 'text'">
            <label v-if="current.field === 'text' || current.field === 'title'"
              >{{ tr('Texto')
              }}<input
                :value="current.text"
                maxlength="100"
                @input="textPatch({ text: ($event.target as HTMLInputElement).value })"
            /></label>
            <label
              >{{ tr('Fonte')
              }}<ErpDropdown
                :model-value="current.font"
                :options="[
                  { value: 'arimo', label: 'Arimo' },
                  { value: 'barlow', label: 'Barlow Semi Condensed' },
                ]"
                :label="tr('Fonte')"
                @update:model-value="textPatch({ font: $event as LabelTextElement['font'] })"
            /></label>
            <div class="design-measures">
              <label
                >{{ tr('Tamanho (pt)')
                }}<input
                  type="number"
                  :value="Math.round(((current.font_size * 72) / 203) * 10) / 10"
                  min="3.6"
                  max="25.5"
                  step="0.5"
                  inputmode="decimal"
                  @change="fontSize($event)"
              /></label>
              <label
                >{{ tr('Linhas')
                }}<input
                  type="number"
                  :value="current.lines"
                  min="1"
                  :max="current.field === 'code' ? 1 : 4"
                  step="1"
                  @change="
                    textPatch({
                      lines: Math.max(
                        1,
                        Math.min(
                          current.field === 'code' ? 1 : 4,
                          Number(($event.target as HTMLInputElement).value) || 1,
                        ),
                      ),
                    })
                  "
              /></label>
            </div>
            <label
              >{{ tr('Alinhamento')
              }}<ErpDropdown
                :model-value="current.align"
                :options="alignOptions"
                :label="tr('Alinhamento')"
                @update:model-value="textPatch({ align: $event as LabelTextElement['align'] })"
            /></label>
            <label class="design-check"
              ><input
                type="checkbox"
                :checked="current.bold"
                @change="textPatch({ bold: ($event.target as HTMLInputElement).checked })"
              />{{ tr('Negrito') }}</label
            >
            <label class="design-check"
              ><input
                type="checkbox"
                :checked="current.uppercase"
                @change="textPatch({ uppercase: ($event.target as HTMLInputElement).checked })"
              />{{ tr('Maiúsculas') }}</label
            >
          </template>
          <label v-if="current.type === 'qr'"
            >{{ tr('Tamanho do QR')
            }}<ErpDropdown
              :model-value="current.module_size"
              :options="qrOptions"
              :label="tr('Tamanho do QR')"
              @update:model-value="qrSize"
          /></label>
          <label
            v-if="current.type !== 'qr' && !(current.type === 'text' && current.field === 'code')"
            class="design-check"
            ><input
              type="checkbox"
              :checked="current.visible"
              @change="visibility(($event.target as HTMLInputElement).checked)"
            />{{ tr('Exibir na etiqueta') }}</label
          >
          <button
            type="button"
            class="erp-button erp-button--danger erp-button--sm"
            :disabled="
              current.type === 'qr' || (current.type === 'text' && current.field === 'code')
            "
            @click="removeElement"
          >
            {{ tr('Remover campo') }}
          </button>
        </fieldset>
        <p class="design-help">
          {{
            tr(
              'Textos longos são reduzidos para caber no espaço. O cadastro do produto permanece igual.',
            )
          }}
        </p>
      </aside>
    </div>
    <footer class="design-footer">
      <span>{{
          dirty
            ? tr('Alterações não salvas')
            : editingId === 'standard'
              ? tr('Cópia do padrão — salve para usar este desenho.')
              : tr('Modelo salvo')
      }}</span>
      <button
        type="button"
        class="erp-button erp-button--primary erp-button--sm"
        :disabled="editingId === 'standard' || dirty || disabled || working || remoteChanged"
        @click="emit('use', editingId)"
      >
        {{ tr('Usar este modelo') }}
      </button>
      <button
        v-if="editingId !== 'standard'"
        type="button"
        class="erp-button erp-button--ghost erp-button--sm"
        :disabled="disabled || working"
        @click="deleteConfirmed = !deleteConfirmed"
      >
        {{ tr('Excluir modelo') }}
      </button>
      <div v-if="deleteConfirmed" class="design-delete">
        <span>{{
          tr('Excluir somente este modelo salvo? Impressões anteriores serão preservadas.')
        }}</span
        ><button
          type="button"
          class="erp-button erp-button--danger erp-button--sm"
          :disabled="working || disabled"
          @click="removeLayout"
        >
          {{ tr('Confirmar exclusão') }}
        </button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import { useInventoryI18n } from './i18n'
import { productLabels as api, type LabelProduct } from '@/services/productLabels'
import {
  cloneDesign,
  designIssue,
  elementSize,
  moveLabelElement,
  type LabelDesign,
  type LabelElement,
  type LabelField,
  type LabelTextElement,
  type ProductLabelLayout,
} from '@/services/productLabelDesign'

const props = defineProps<{
  layouts: ProductLabelLayout[]
  products: LabelProduct[]
  activeId: string
  disabled: boolean
}>()
const emit = defineEmits<{
  saved: [layout: ProductLabelLayout]
  deleted: [id: string]
  use: [id: string]
  refresh: []
}>()
const { tr } = useInventoryI18n()
const initial = props.layouts.find((l) => l.id === props.activeId) || props.layouts[0]!
const editingId = ref(initial.id),
  name = ref(initial.builtin ? `${tr(initial.name)} — ${tr('Cópia')}` : initial.name)
const config = ref<LabelDesign>(cloneDesign(initial.config)),
  version = ref(initial.version)
const baseline = ref(JSON.stringify({ name: name.value, config: config.value }))
const dirty = computed(
  () => JSON.stringify({ name: name.value, config: config.value }) !== baseline.value,
)
const remoteChanged = computed(
  () =>
    editingId.value !== 'standard' &&
    props.layouts.find((l) => l.id === editingId.value)?.version !== version.value,
)
const selectedId = ref(config.value.elements[0]?.id || ''),
  pendingId = ref(''),
  fieldToAdd = ref<LabelField | 'line'>('text')
const sampleId = ref(props.products[0]?.id || ''),
  zoom = ref(1),
  canvas = ref<HTMLElement>()
const working = ref(false),
  previewBusy = ref(false),
  error = ref(''),
  message = ref(''),
  previewError = ref(''),
  previewUrl = ref(''),
  deleteConfirmed = ref(false)
const undoStack = ref<string[]>([]),
  redoStack = ref<string[]>([])
const current = computed(() => config.value.elements.find((e) => e.id === selectedId.value))
const visibleElements = computed(() =>
  config.value.elements.filter((e) => e.type === 'qr' || e.visible),
)
const localIssue = computed(() => designIssue(config.value))
const canSave = computed(
  () =>
    !props.disabled &&
    !working.value &&
    !previewBusy.value &&
    !localIssue.value &&
    !previewError.value &&
    !!previewUrl.value &&
    !!name.value.trim(),
)
const fieldNames: Record<LabelField | 'qr' | 'line', string> = {
  title: 'Título ELEVEN',
  name: 'Nome do produto',
  size: 'Tamanho',
  color: 'Cor',
  code: 'Código interno',
  price: 'Preço de venda',
  barcode: 'Código do fabricante',
  text: 'Texto livre',
  qr: 'QR do produto',
  line: 'Linha divisória',
}
const addOptions = computed(() =>
  (['text', 'name', 'size', 'color', 'price', 'barcode', 'line'] as const).map((value) => ({
    value,
    label: tr(fieldNames[value]),
  })),
)
const alignOptions = computed(() =>
  (['left', 'center', 'right'] as const).map((value, i) => ({
    value,
    label: tr(['Esquerda', 'Centro', 'Direita'][i]!),
  })),
)
const qrOptions = [2, 3, 4, 5].map((value) => ({ value, label: `${(37 * value) / 8} mm` }))
const sampleOptions = computed(() => [
  { value: '', label: tr('Exemplo fictício') },
  ...props.products.map((p) => ({ value: p.id, label: p.name })),
])
function elementLabel(element: LabelElement) {
  return tr(fieldNames[element.type === 'text' ? element.field : element.type])
}
function elementStyle(element: LabelElement) {
  const size = elementSize(element)
  return {
    left: `${(element.x / 480) * 100}%`,
    top: `${(element.y / 240) * 100}%`,
    width: `${(size.width / 480) * 100}%`,
    height: `${(size.height / 240) * 100}%`,
  }
}
function remember(before: string) {
  if (before === JSON.stringify(config.value)) return
  undoStack.value = [...undoStack.value.slice(-39), before]
  redoStack.value = []
  error.value = ''
  message.value = ''
}
function mutate(change: () => void) {
  const before = JSON.stringify(config.value)
  change()
  remember(before)
}
function undo() {
  const before = undoStack.value.pop()
  if (!before) return
  redoStack.value.push(JSON.stringify(config.value))
  config.value = JSON.parse(before)
}
function redo() {
  const after = redoStack.value.pop()
  if (!after) return
  undoStack.value.push(JSON.stringify(config.value))
  config.value = JSON.parse(after)
}
function textPatch(patch: Partial<LabelTextElement>) {
  if (current.value?.type === 'text') mutate(() => Object.assign(current.value!, patch))
}
function geometry(key: 'x' | 'y' | 'width' | 'height', event: Event) {
  const value = Number((event.target as HTMLInputElement).value)
  if (!current.value || !Number.isFinite(value)) return
  mutate(() => {
    const e = current.value!,
      dots = Math.round(value * 8)
    if (key === 'x' || key === 'y') e[key] = dots
    else if (e.type !== 'qr') {
      const min =
        key === 'width'
          ? e.type === 'text'
            ? e.field === 'code'
              ? 90
              : 16
            : 1
          : e.type === 'text'
            ? e.field === 'code'
              ? 12
              : 8
            : 1
      e[key] = Math.max(min, Math.min(key === 'width' ? 480 : e.type === 'line' ? 8 : 240, dots))
    }
    moveLabelElement(e, e.x, e.y)
  })
}
function fontSize(event: Event) {
  const value = Number((event.target as HTMLInputElement).value)
  if (Number.isFinite(value))
    textPatch({ font_size: Math.max(10, Math.min(72, Math.round((value * 203) / 72))) })
}
function qrSize(value: number) {
  if (current.value?.type === 'qr')
    mutate(() => {
      const e = current.value!
      if (e.type === 'qr') e.module_size = value
      moveLabelElement(e, e.x, e.y)
    })
}
function visibility(value: boolean) {
  if (current.value && current.value.type !== 'qr')
    mutate(() => {
      if (current.value && current.value.type !== 'qr') current.value.visible = value
    })
}
function addElement() {
  if (config.value.elements.length >= 16) return
  const id = `field-${crypto.randomUUID().slice(0, 8)}`
  mutate(() =>
    config.value.elements.push(
      fieldToAdd.value === 'line'
        ? { id, type: 'line', x: 32, y: 176, width: 270, height: 2, visible: true }
        : {
            id,
            type: 'text',
            field: fieldToAdd.value,
            x: 32,
            y: 176,
            width: 270,
            height: 20,
            font_size: 16,
            font: 'arimo',
            bold: false,
            align: 'left',
            uppercase: false,
            lines: 1,
            text: tr('Seu texto'),
            visible: true,
          },
    ),
  )
  selectedId.value = id
}
function removeElement() {
  if (
    current.value?.type === 'qr' ||
    (current.value?.type === 'text' && current.value.field === 'code')
  )
    return
  mutate(() => {
    config.value.elements = config.value.elements.filter((e) => e.id !== selectedId.value)
  })
  selectedId.value = config.value.elements[0]?.id || ''
}
function restore() {
  const standard = props.layouts.find((l) => l.builtin)
  if (standard)
    mutate(() => {
      config.value = cloneDesign(standard.config)
      selectedId.value = config.value.elements[0]?.id || ''
    })
}
function loadLayout(id: string) {
  const layout = props.layouts.find((l) => l.id === id)
  if (!layout) return
  editingId.value = id
  version.value = layout.version
  config.value = cloneDesign(layout.config)
  name.value = layout.builtin ? `${tr(layout.name)} — ${tr('Cópia')}` : layout.name
  baseline.value = JSON.stringify({ name: name.value, config: config.value })
  selectedId.value = config.value.elements[0]?.id || ''
  undoStack.value = []
  redoStack.value = []
  pendingId.value = ''
  deleteConfirmed.value = false
  error.value = ''
  message.value = ''
}
function requestLayout(id: string) {
  if (id === editingId.value) return
  if (dirty.value) pendingId.value = id
  else loadLayout(id)
}

let drag: {
  id: string
  pointer: number
  x: number
  y: number
  startX: number
  startY: number
  before: string
  width: number
  height: number
} | null = null
function startDrag(event: PointerEvent, element: LabelElement) {
  if (event.button !== 0 || props.disabled || working.value) return
  event.preventDefault()
  selectedId.value = element.id
  ;(event.currentTarget as HTMLElement).focus({ preventScroll: true })
  const rect = canvas.value!.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  drag = {
    id: element.id,
    pointer: event.pointerId,
    x: element.x,
    y: element.y,
    startX: event.clientX,
    startY: event.clientY,
    before: JSON.stringify(config.value),
    width: rect.width,
    height: rect.height,
  }
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}
function moveDrag(event: PointerEvent) {
  if (!drag || drag.pointer !== event.pointerId) return
  const element = config.value.elements.find((e) => e.id === drag!.id)
  if (element)
    moveLabelElement(
      element,
      drag.x + ((event.clientX - drag.startX) / drag.width) * 480,
      drag.y + ((event.clientY - drag.startY) / drag.height) * 240,
    )
}
function endDrag() {
  if (!drag) return
  const before = drag.before
  drag = null
  remember(before)
  schedulePreview()
}
function moveWithKeys(event: KeyboardEvent, element: LabelElement) {
  const directions: Record<string, [number, number]> = {
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
    ArrowUp: [0, -1],
    ArrowDown: [0, 1],
  }
  const direction = directions[event.key]
  if (!direction || props.disabled || working.value) return
  event.preventDefault()
  mutate(() =>
    moveLabelElement(
      element,
      element.x + direction[0] * (event.shiftKey ? 8 : 1),
      element.y + direction[1] * (event.shiftKey ? 8 : 1),
    ),
  )
}

async function errorMessage(e: unknown) {
  let detail = (e as { response?: { data?: { detail?: unknown } | Blob } }).response?.data
  if (detail instanceof Blob) {
    try {
      detail = JSON.parse(await detail.text())
    } catch {
      detail = undefined
    }
  }
  const value = detail && !(detail instanceof Blob) ? detail.detail : undefined
  if (typeof value === 'string') return tr(value)
  if (Array.isArray(value))
    return value.map((v) => tr(String(v.msg).replace(/^Value error, /, ''))).join('; ')
  return tr(e instanceof Error ? e.message : 'Não foi possível concluir. Tente novamente.')
}
async function save(copy: boolean) {
  if (!canSave.value) return
  working.value = true
  error.value = ''
  message.value = ''
  try {
    const id = copy
      ? `product-${crypto.randomUUID().replaceAll('-', '').slice(0, 20)}`
      : editingId.value
    const layout = await api.saveLayout(id, {
      name: name.value.trim(),
      version: copy ? 0 : version.value,
      config: cloneDesign(config.value),
    })
    emit('saved', layout)
    editingId.value = layout.id
    version.value = layout.version
    name.value = layout.name
    config.value = cloneDesign(layout.config)
    baseline.value = JSON.stringify({ name: name.value, config: config.value })
    message.value = tr('Modelo salvo. Ele está disponível nos outros aparelhos.')
  } catch (e) {
    error.value = await errorMessage(e)
  } finally {
    working.value = false
  }
}
async function removeLayout() {
  if (!deleteConfirmed.value || props.disabled) return
  working.value = true
  error.value = ''
  try {
    await api.deleteLayout(editingId.value, version.value)
    emit('deleted', editingId.value)
    loadLayout('standard')
  } catch (e) {
    error.value = await errorMessage(e)
  } finally {
    working.value = false
  }
}
let timer: ReturnType<typeof setTimeout> | undefined,
  generation = 0,
  disposed = false
function schedulePreview() {
  if (timer) clearTimeout(timer)
  const request = ++generation
  previewError.value = ''
  previewBusy.value = !localIssue.value
  if (localIssue.value) return
  timer = setTimeout(async () => {
    try {
      const blob = await api.designPreview(cloneDesign(config.value), sampleId.value || undefined)
      if (disposed || request !== generation) return
      if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
      previewUrl.value = URL.createObjectURL(blob)
    } catch (e) {
      const detail = await errorMessage(e)
      if (!disposed && request === generation) previewError.value = detail
    } finally {
      if (!disposed && request === generation) previewBusy.value = false
    }
  }, 180)
}
watch(
  config,
  () => {
    if (!drag) schedulePreview()
  },
  { deep: true },
)
watch(sampleId, schedulePreview)
watch(
  () => props.activeId,
  (id) => {
    if (!dirty.value) loadLayout(id)
  },
)
watch(
  () => props.products,
  (products) => {
    if (sampleId.value && !products.some((p) => p.id === sampleId.value)) sampleId.value = ''
  },
)
schedulePreview()
onUnmounted(() => {
  disposed = true
  generation++
  if (timer) clearTimeout(timer)
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>

<style scoped>
.design-editor {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 20px;
  margin: 14px 0;
  color: #1e293b;
}
.design-heading,
.design-models,
.design-tools,
.design-add,
.design-footer,
.design-caption {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.design-heading {
  justify-content: space-between;
  margin-bottom: 16px;
}
.design-heading h2 {
  font-size: 18px;
  margin: 0 0 6px;
}
.design-heading p,
.design-help,
.design-caption {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
}
.design-paper {
  background: #f1f5f9;
  padding: 7px 10px;
  border-radius: 20px;
  font-size: 12px;
  white-space: nowrap;
}
.design-models {
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
}
.design-models > .erp-dropdown,
.design-models > input {
  flex: 1;
  min-width: 180px;
}
.design-editor input:not([type='checkbox']) {
  border: 1px solid #cbd5e1;
  border-radius: 9px;
  padding: 8px;
  font-size: 16px;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  color: #1e293b;
  background: #fff;
}
.design-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 20px;
  padding: 18px 0;
}
.design-board {
  min-width: 0;
}
.design-tools > .erp-dropdown:first-child {
  flex: 1;
  min-width: 140px;
}
.design-tools > .erp-dropdown:nth-child(2) {
  width: 96px;
}
.design-scroll {
  overflow: auto;
  padding: 24px 12px 12px;
  margin-top: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background:
    repeating-linear-gradient(0deg, transparent, transparent 19px, #e2e8f0 20px),
    repeating-linear-gradient(90deg, #f1f5f9, #f1f5f9 19px, #e2e8f0 20px);
}
.design-canvas {
  position: relative;
  aspect-ratio: 2;
  background: #fff;
  box-shadow: 0 3px 14px #0f172a20;
  min-width: 0;
}
.design-raster {
  display: block;
  width: 100%;
  height: 100%;
  image-rendering: pixelated;
  pointer-events: none;
}
.design-placeholder {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #94a3b8;
  font-size: 13px;
}
.design-object {
  position: absolute;
  border: 1px solid transparent;
  border-radius: 1px;
  padding: 0;
  background: transparent;
  cursor: move;
  touch-action: none;
}
.design-object:hover {
  border-color: #93c5fd;
}
.design-object.selected {
  border: 1px dashed #2563eb;
  outline: 2px solid #2563eb20;
  background: #2563eb08;
}
.design-object:focus-visible {
  outline: 3px solid #60a5fa;
}
.design-object-caption {
  position: absolute;
  left: -1px;
  bottom: 100%;
  background: #2563eb;
  color: white;
  padding: 2px 5px;
  font-size: 10px;
  white-space: nowrap;
  pointer-events: none;
}
.design-caption {
  justify-content: space-between;
  margin: 8px 0 16px;
}
.design-add > .erp-dropdown {
  flex: 1;
  min-width: 130px;
}
.design-help {
  margin-top: 12px;
}
.design-properties {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  min-width: 0;
}
.design-properties fieldset {
  border: 0;
  margin: 14px 0 0;
  padding: 0;
  min-width: 0;
}
.design-properties label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  margin: 0 0 12px;
}
.design-properties label > input:not([type='checkbox']),
.design-properties label > .erp-dropdown {
  margin-top: 5px;
}
.design-measures {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.design-properties .design-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 400;
}
.design-check input {
  width: 17px;
  height: 17px;
}
.design-footer {
  border-top: 1px solid #e2e8f0;
  padding-top: 15px;
}
.design-footer > span {
  font-size: 12px;
  color: #64748b;
  margin-right: auto;
}
.design-notice,
.design-error,
.design-success {
  padding: 10px 12px;
  border-radius: 9px;
  font-size: 13px;
  line-height: 1.5;
  margin: 12px 0;
}
.design-notice {
  background: #fffbeb;
  color: #92400e;
}
.design-notice p {
  margin: 0 0 8px;
}
.design-error {
  background: #fff1f2;
  color: #b91c1c;
}
.design-success {
  background: #ecfdf5;
  color: #047857;
}
.design-delete {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  width: 100%;
  font-size: 13px;
  color: #b91c1c;
}
@media (max-width: 760px) {
  .design-workspace {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .design-properties {
    display: block;
  }
  .design-properties fieldset {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 14px;
  }
  .design-properties .design-measures {
    grid-column: 1 / -1;
  }
  .design-properties label {
    margin-bottom: 4px;
  }
  .design-editor {
    padding: 12px;
  }
  .design-tools {
    gap: 6px;
  }
  .design-tools > .erp-dropdown:first-child {
    flex-basis: calc(100% - 110px);
  }
  .design-tools > .erp-button {
    flex: 1;
  }
  .design-models > .erp-dropdown,
  .design-models > input {
    flex-basis: 100%;
    min-width: 0;
  }
  .design-models > .erp-button {
    flex: 1;
  }
  .design-add {
    gap: 6px;
  }
}
</style>
