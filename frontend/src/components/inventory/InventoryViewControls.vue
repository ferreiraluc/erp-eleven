<template>
  <div ref="root" class="view-controls" @keydown.esc.stop.prevent="closeZoom(true)" @focusout="onFocusOut">
    <div class="view-options" role="group" :aria-label="tr('Visualização:')">
      <span class="view-label" aria-hidden="true">{{ tr('Visualização:') }}</span>
      <button v-for="option in options" :key="option.value" type="button" class="view-button erp-control"
        :class="{ active: mode === option.value }" :aria-label="tr(option.label)" :title="tr(option.label)" :aria-pressed="mode === option.value"
        :data-view="option.value" :aria-expanded="option.value === 'grid' && zoomAvailable ? zoomOpen : undefined"
        :aria-controls="option.value === 'grid' && zoomAvailable ? zoomId : undefined"
        @click="selectView(option.value)" @keydown="onViewKey($event, option.value)">
        <component :is="option.icon" aria-hidden="true" /><span class="view-name">{{ tr(option.label) }}</span>
      </button>
    </div>
    <div class="selection-results">
      <button type="button" class="view-button erp-control" :class="{ active: selectionMode }" :aria-pressed="selectionMode" @click="emit('toggle-selection')">
        {{ tr('Selecionar') }}
      </button>
      <span class="result-count search-result-count" role="status" aria-live="polite" aria-atomic="true">
        <span v-if="busy" class="spinner" aria-hidden="true" />
        {{ busy ? tr('Buscando...') : ready ? resultText : tr('Total não confirmado') }}
      </span>
    </div>
    <div v-if="zoomOpen && zoomAvailable" :id="zoomId" ref="zoomMenu" class="grid-zoom-menu" :style="zoomPosition">
      <InventoryGridZoom :model-value="gridZoom" @update:model-value="emit('update:gridZoom', $event)" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Grid2X2, List, Rows3 } from 'lucide-vue-next'
import { computed, nextTick, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import InventoryGridZoom from './InventoryGridZoom.vue'
import { useInventoryI18n } from '@/components/inventory/i18n'

export type InventoryViewMode = 'list' | 'compact' | 'grid'
const props = withDefaults(defineProps<{ mode: InventoryViewMode; selectionMode: boolean; busy: boolean; ready: boolean; resultText: string; gridZoom?: number; zoomEnabled?: boolean }>(), { gridZoom: 2, zoomEnabled: false })
const emit = defineEmits<{ mode: [value: InventoryViewMode]; 'toggle-selection': []; 'update:gridZoom': [value: number] }>()
const { tr } = useInventoryI18n()
const root = ref<HTMLElement>(), zoomMenu = ref<HTMLElement>()
const zoomOpen = ref(false), mobile = ref(false), zoomPosition = ref<Record<string, string>>({})
const zoomAvailable = computed(() => mobile.value && props.zoomEnabled)
const zoomId = `inventory-zoom-${useId()}`
const gridTrigger = () => root.value?.querySelector<HTMLButtonElement>('[data-view="grid"]')
function closeZoom(restoreFocus = false) {
  const wasOpen = zoomOpen.value
  zoomOpen.value = false
  if (wasOpen && restoreFocus) gridTrigger()?.focus({ preventScroll: true })
}
function placeZoom() {
  if (!zoomOpen.value) return
  const rect = gridTrigger()?.getBoundingClientRect()
  if (!rect?.width) { closeZoom(); return }
  const width = Math.min(296, window.innerWidth - 24)
  zoomPosition.value = { width: `${width}px`, left: `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`, top: `${rect.bottom + 8}px` }
}
async function selectView(value: InventoryViewMode, keyboard = false) {
  emit('mode', value)
  if (value !== 'grid' || !zoomAvailable.value) { closeZoom(); return }
  zoomOpen.value = keyboard || !zoomOpen.value
  if (zoomOpen.value) {
    await nextTick()
    placeZoom()
    if (keyboard) zoomMenu.value?.querySelector<HTMLInputElement>('input')?.focus()
  }
}
function onViewKey(event: KeyboardEvent, value: InventoryViewMode) {
  if (value === 'grid' && zoomAvailable.value && event.key === 'ArrowDown') {
    event.preventDefault()
    void selectView(value, true)
  }
}
function onOutside(event: PointerEvent) {
  if (event.target instanceof Node && !insideZoom(event.target)) closeZoom()
}
function onFocusOut(event: FocusEvent) {
  if (event.relatedTarget instanceof Node && !insideZoom(event.relatedTarget)) closeZoom()
}
const insideZoom = (node: Node) => gridTrigger()?.contains(node) || zoomMenu.value?.contains(node)
function onResize() {
  mobile.value = window.matchMedia?.('(max-width:600px)').matches ?? window.innerWidth <= 600
  closeZoom()
}
watch(() => [props.mode, zoomAvailable.value], () => { if (props.mode !== 'grid' || !zoomAvailable.value) closeZoom() })
onMounted(() => {
  onResize()
  document.addEventListener('pointerdown', onOutside)
  window.addEventListener('resize', onResize)
  window.addEventListener('scroll', placeZoom, true)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', onOutside)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('scroll', placeZoom, true)
})
const options = [
  { value: 'list' as const, label: 'Lista', icon: List },
  { value: 'compact' as const, label: 'Compacto', icon: Rows3 },
  { value: 'grid' as const, label: 'Quadrados', icon: Grid2X2 },
]
</script>

<style scoped>
.grid-zoom-menu { position:fixed; z-index:50; padding:6px; border:1px solid #e2e8f0; border-radius:14px; background:#fff; box-shadow:0 8px 24px #0f172a18; }
.view-controls,.view-options,.selection-results{display:flex;align-items:center;gap:6px;min-width:0}.view-controls{justify-content:space-between;flex-wrap:wrap}.view-options{flex-wrap:wrap}.view-label{margin-right:2px;color:#64748b;font-size:.75rem}.view-button{display:inline-flex;align-items:center;gap:5px;min-height:34px;padding:6px 10px;border:1px solid var(--color-border);border-radius:999px;background:#fff;color:#556277;cursor:pointer;font:inherit;font-size:.75rem;white-space:nowrap;transition:background-color var(--motion-fast),border-color var(--motion-fast),color var(--motion-fast)}.view-button:hover{border-color:#94a3b8;color:#334155}.view-button.active{border-color:var(--color-brand-600);background:var(--color-brand-100);color:var(--color-brand-700)}.view-button :deep(svg){width:16px;height:16px}.result-count{display:inline-flex;align-items:center;gap:6px;padding:5px 8px;border-radius:999px;background:var(--color-brand-50);color:var(--color-brand-700);font-size:.75rem;font-weight:600}.spinner{width:12px;height:12px;flex:none;border:2px solid var(--color-brand-100);border-top-color:var(--color-brand-600);border-radius:50%;animation:inventory-spin .8s linear infinite}@keyframes inventory-spin{to{transform:rotate(360deg)}}@media(max-width:600px){.view-label{display:none}.view-button{min-height:30px;padding:5px 8px}.view-controls{gap:6px;flex-wrap:nowrap}.view-options{flex-wrap:nowrap;gap:4px}.view-name{display:none}.selection-results{flex:1;justify-content:flex-end;gap:5px}.result-count{padding:5px;font-size:.7rem;white-space:nowrap}}
</style>
