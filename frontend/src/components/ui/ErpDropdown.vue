<template>
  <div ref="root" class="erp-dropdown" @focusout="focusOut" @keydown.esc.stop.prevent="close(true)">
    <div class="erp-dropdown__control" :class="{ 'is-open': open }">
      <input
        v-if="editable"
        ref="input"
        :id="id"
        role="combobox"
        :aria-label="label"
        :aria-expanded="open"
        :aria-controls="menuId"
        aria-autocomplete="list"
        :value="modelValue"
        :placeholder="placeholder || label"
        :disabled="disabled"
        :maxlength="maxlength"
        autocomplete="off"
        @input="type"
        @keydown.down.prevent="show(true)"
        @keydown.enter.stop.prevent="open && chooseFirst()"
      />
      <button
        v-else
        ref="trigger"
        :id="id"
        type="button"
        class="erp-dropdown__value"
        :disabled="disabled"
        :aria-label="label"
        :aria-expanded="open"
        :aria-controls="menuId"
        aria-haspopup="listbox"
        @click="toggle"
        @keydown.down.prevent="show(true)"
      >
        {{ selectedLabel || placeholder || label }}
      </button>
      <button
        v-if="editable"
        ref="trigger"
        type="button"
        class="erp-dropdown__arrow"
        :disabled="disabled"
        :aria-label="label"
        :aria-expanded="open"
        :aria-controls="menuId"
        @click="toggle"
        @keydown.down.prevent="show(true)"
      >
        <ChevronDown aria-hidden="true" />
      </button>
      <ChevronDown v-else class="erp-dropdown__chevron" aria-hidden="true" />
    </div>
    <div
      v-if="open"
      :id="menuId"
      ref="menu"
      class="erp-dropdown__menu"
      :style="position"
      role="listbox"
      :aria-label="label"
      @keydown="navigate"
    >
      <button
        v-for="option in filtered"
        :key="option.value"
        type="button"
        role="option"
        :aria-selected="option.value === modelValue"
        :class="{ active: option.value === modelValue }"
        @click="choose(option.value)"
      >
        <span>{{ option.label }}</span
        ><span v-if="option.value === modelValue" aria-hidden="true">✓</span>
      </button>
      <button
        v-if="editable && query.trim() && !options.some((o) => key(o.value) === key(query))"
        type="button"
        role="option"
        :aria-selected="false"
        @click="choose(query.trim())"
      >
        {{ query.trim() }} <span>↵</span>
      </button>
      <span v-if="!filtered.length && !query.trim()" class="erp-dropdown__empty">—</span>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
const props = withDefaults(
  defineProps<{
    modelValue: string
    options: Array<{ value: string; label: string }>
    label: string
    id?: string
    placeholder?: string
    editable?: boolean
    disabled?: boolean
    maxlength?: number
  }>(),
  { maxlength: 100 },
)
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const root = ref<HTMLElement>(),
  input = ref<HTMLInputElement>(),
  trigger = ref<HTMLButtonElement>(),
  menu = ref<HTMLElement>()
const open = ref(false),
  query = ref(''),
  menuId = `erp-options-${useId()}`
const position = ref<Record<string, string>>({})
const key = (text: string) => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().trim()
const filtered = computed(() =>
  props.options.filter((o) => !query.value || key(o.label).includes(key(query.value))),
)
const selectedLabel = computed(() => props.options.find((o) => o.value === props.modelValue)?.label)
function place() {
  if (!open.value || !root.value) return
  const rect = root.value.getBoundingClientRect(),
    viewport = window.visualViewport
  const height = viewport?.height || window.innerHeight,
    offset = viewport?.offsetTop || 0
  const below = height + offset - rect.bottom - 12,
    above = rect.top - offset - 12
  const up = below < 180 && above > below
  position.value = {
    left: `${Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8))}px`,
    width: `${Math.min(rect.width, window.innerWidth - 16)}px`,
    maxHeight: `${Math.max(80, Math.min(280, up ? above : below))}px`,
    ...(up
      ? { bottom: `${window.innerHeight - rect.top + 5}px` }
      : { top: `${rect.bottom + 5}px` }),
  }
}
async function show(keyboard = false) {
  if (props.disabled) return
  query.value = ''
  open.value = true
  await nextTick()
  place()
  if (keyboard)
    menu.value?.querySelector<HTMLButtonElement>('[aria-selected="true"],button')?.focus()
}
function toggle() {
  if (open.value) close()
  else void show()
}
function close(restore = false) {
  open.value = false
  if (restore) trigger.value?.focus({ preventScroll: true })
}
function choose(value: string) {
  emit('update:modelValue', value)
  close(true)
}
function chooseFirst() {
  const first = filtered.value[0]
  choose(first?.value || query.value.trim())
}
function type(event: Event) {
  const value = (event.target as HTMLInputElement).value
  emit('update:modelValue', value)
  query.value = value
  open.value = true
  void nextTick(place)
}
function outside(event: PointerEvent) {
  if (event.target instanceof Node && !root.value?.contains(event.target)) close()
}
function focusOut(event: FocusEvent) {
  if (event.relatedTarget instanceof Node && !root.value?.contains(event.relatedTarget)) close()
}
function navigate(event: KeyboardEvent) {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
  const buttons = Array.from(menu.value?.querySelectorAll<HTMLButtonElement>('button') || [])
  if (!buttons.length) return
  event.preventDefault()
  const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
  const next =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? buttons.length - 1
        : (index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length
  buttons[next]?.focus()
}
watch(
  () => props.disabled,
  (value) => {
    if (value) close()
  },
)
onMounted(() => {
  document.addEventListener('pointerdown', outside)
  window.addEventListener('resize', place)
  window.addEventListener('scroll', place, true)
  window.visualViewport?.addEventListener('resize', place)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', outside)
  window.removeEventListener('resize', place)
  window.removeEventListener('scroll', place, true)
  window.visualViewport?.removeEventListener('resize', place)
})
</script>
<style scoped>
.erp-dropdown {
  min-width: 0;
  width: 100%;
}
.erp-dropdown__control {
  display: flex;
  align-items: center;
  position: relative;
  min-height: 40px;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  background: #f8fafc;
  color: #475569;
  transition: border-color 0.15s;
}
.erp-dropdown__control:focus-within,
.erp-dropdown__control.is-open {
  border-color: #6388d2;
  box-shadow: 0 0 0 2px #2563eb14;
}
.erp-dropdown__control input,
.erp-dropdown__value {
  border: 0 !important;
  background: transparent !important;
  min-width: 0;
  width: 100%;
  padding: 9px 12px !important;
  font: inherit;
  font-size: 0.875rem;
  color: inherit;
  box-shadow: none !important;
  outline: none;
}
.erp-dropdown__value {
  text-align: left;
  padding-right: 32px !important;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-height: 40px !important;
}
.erp-dropdown__arrow {
  border: 0;
  background: transparent;
  display: grid;
  place-items: center;
  flex: 0 0 38px;
  min-height: 40px;
  padding: 6px;
  color: inherit;
}
.erp-dropdown svg {
  width: 16px;
  height: 16px;
}
.erp-dropdown__chevron {
  position: absolute;
  right: 10px;
  pointer-events: none;
}
.erp-dropdown__menu {
  position: fixed;
  z-index: 2000;
  overflow: auto;
  overscroll-behavior: contain;
  padding: 5px;
  box-sizing: border-box;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 12px 32px #0f172a24;
}
.erp-dropdown__menu button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-height: 42px;
  padding: 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font: inherit;
  font-size: 0.875rem;
  text-align: left;
  color: #475569;
  cursor: pointer;
}
.erp-dropdown__menu button:hover,
.erp-dropdown__menu button:focus-visible,
.erp-dropdown__menu button.active {
  background: #eff6ff;
  color: #1d4ed8;
  outline: none;
}
.erp-dropdown__empty {
  display: block;
  padding: 8px;
}
@media (pointer: coarse) {
  .erp-dropdown__control input {
    font-size: 16px;
  }
  .erp-dropdown__menu button {
    min-height: 44px;
  }
}
</style>
