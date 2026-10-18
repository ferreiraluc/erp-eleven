<template>
  <div
    ref="root"
    class="erp-dropdown"
    :class="{ 'erp-dropdown--compact': compact, 'erp-dropdown--pill': pill }"
    @focusout="focusOut"
  >
    <div class="erp-dropdown__control" :class="{ 'is-open': open, 'is-invalid': invalid }">
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
        :required="required"
        :maxlength="maxlength"
        :name="name"
        autocomplete="off"
        @input="type"
        @keydown.down.prevent="show(true)"
        @keydown.esc.stop.prevent="close(true)"
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
        :aria-invalid="invalid || undefined"
        aria-haspopup="listbox"
        @click="toggle"
        @keydown.down.prevent="show(true)"
        @keydown.up.prevent="show(true)"
        @keydown="triggerKeys"
      >
        <span v-if="selected?.icon" class="erp-dropdown__icon" aria-hidden="true">{{
          selected.icon
        }}</span>
        <span class="erp-dropdown__text">{{
          displayLabel ?? selected?.triggerLabel ?? selected?.label ?? placeholder ?? label ?? '—'
        }}</span>
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
        aria-haspopup="listbox"
        @click="toggle"
        @keydown.down.prevent="show(true)"
        @keydown.esc.stop.prevent="close(true)"
      >
        <ChevronDown aria-hidden="true" />
      </button>
      <ChevronDown
        v-else
        class="erp-dropdown__chevron"
        :class="{ rotated: open }"
        aria-hidden="true"
      />
    </div>
    <input
      v-if="!editable && required"
      ref="validity"
      class="erp-dropdown__validity"
      tabindex="-1"
      aria-hidden="true"
      :disabled="disabled"
      required
      :value="hasSelection ? 'selected' : ''"
      @invalid.prevent="onInvalid"
    />
    <input
      v-if="!editable && name"
      type="hidden"
      :name="name"
      :disabled="disabled"
      :value="String(modelValue ?? '')"
    />
    <span v-if="invalid" class="erp-dropdown__error" role="alert">{{
      uiText('Selecione uma opção')
    }}</span>
    <Teleport to="body">
      <div
        v-if="open"
        ref="menu"
        class="erp-dropdown__menu"
        :style="position"
        :data-erp-dialog-owner="dialogId || undefined"
        @focusout="focusOut"
        @keydown.esc.stop.prevent="close(true)"
        @keydown="navigate"
      >
        <div v-if="canSearch && !editable" class="erp-dropdown__search">
          <Search aria-hidden="true" />
          <input
            v-model="query"
            type="search"
            :aria-label="searchLabel"
            :placeholder="searchLabel"
            autocomplete="off"
            @keydown.enter.stop.prevent="chooseFirst()"
            @keydown.down.prevent="focusOption(0)"
          />
        </div>
        <div :id="menuId" role="listbox" :aria-label="label" class="erp-dropdown__options">
          <button
            v-for="(option, index) in filtered"
            :key="`${index}:${String(option.value)}`"
            type="button"
            role="option"
            tabindex="-1"
            :value="String(option.value ?? '')"
            :aria-selected="Object.is(option.value, modelValue)"
            :disabled="option.disabled"
            :class="{ active: Object.is(option.value, modelValue) }"
            @click="choose(option.value)"
          >
            <span v-if="option.icon" class="erp-dropdown__icon" aria-hidden="true">{{
              option.icon
            }}</span>
            <span class="erp-dropdown__option-text"
              ><span>{{ option.label }}</span
              ><small v-if="option.description">{{ option.description }}</small></span
            >
            <Check
              v-if="Object.is(option.value, modelValue)"
              class="erp-dropdown__check"
              aria-hidden="true"
            />
          </button>
          <button
            v-if="
              editable &&
              query.trim() &&
              !options.some((o) => key(String(o.value ?? '')) === key(query))
            "
            type="button"
            role="option"
            tabindex="-1"
            :aria-selected="false"
            @click="choose(query.trim() as T)"
          >
            <span>{{ query.trim() }}</span
            ><span aria-hidden="true">↵</span>
          </button>
          <span v-if="!filtered.length && !editable" class="erp-dropdown__empty">{{
            uiText('Nenhuma opção encontrada')
          }}</span>
          <span v-else-if="!filtered.length && !query.trim()" class="erp-dropdown__empty">—</span>
        </div>
      </div>
    </Teleport>
  </div>
</template>
<script setup lang="ts" generic="T extends DropdownValue = string">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { Check, ChevronDown, Search } from 'lucide-vue-next'
import { uiText } from '@/i18n/uiText'
import { trapDialogTab } from '@/directives/erpDialog'
import type { DropdownOption, DropdownValue } from './dropdownOptions'
const props = withDefaults(
  defineProps<{
    modelValue?: T
    options: DropdownOption<T>[]
    label?: string
    id?: string
    name?: string
    placeholder?: string
    displayLabel?: string
    editable?: boolean
    disabled?: boolean
    required?: boolean
    maxlength?: number
    searchable?: boolean
    searchPlaceholder?: string
    compact?: boolean
    pill?: boolean
    align?: 'start' | 'end'
    menuWidth?: number
  }>(),
  { maxlength: 100, align: 'start', searchable: undefined },
)
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
const root = ref<HTMLElement>(),
  input = ref<HTMLInputElement>(),
  trigger = ref<HTMLButtonElement>(),
  menu = ref<HTMLElement>(),
  validity = ref<HTMLInputElement>()
const open = ref(false),
  query = ref(''),
  invalid = ref(false),
  dialogId = ref('')
const menuId = `erp-options-${useId()}`
const position = ref<Record<string, string>>({})
const key = (text: string) => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase().trim()
const filtered = computed(() =>
  props.options.filter(
    (o) => !query.value || key(`${o.label} ${o.description || ''}`).includes(key(query.value)),
  ),
)
const selected = computed(() => props.options.find((o) => Object.is(o.value, props.modelValue)))
const hasSelection = computed(
  () =>
    !!selected.value &&
    !selected.value.disabled &&
    props.modelValue !== '' &&
    props.modelValue != null,
)
const canSearch = computed(() => props.searchable ?? props.options.length > 8)
const searchLabel = computed(() => props.searchPlaceholder || uiText('Buscar opções...'))
let observer: ResizeObserver | undefined
let typeahead = '',
  typeaheadAt = 0

function owns(target: EventTarget | null) {
  return target instanceof Node && (root.value?.contains(target) || menu.value?.contains(target))
}
function place() {
  if (!open.value || !root.value) return
  const rect = root.value.getBoundingClientRect(),
    viewport = window.visualViewport
  const height = viewport?.height || window.innerHeight,
    width = viewport?.width || window.innerWidth
  const top = viewport?.offsetTop || 0,
    left = viewport?.offsetLeft || 0
  if (rect.bottom < top || rect.top > top + height) {
    close()
    return
  }
  const below = height + top - rect.bottom - 8,
    above = rect.top - top - 8
  const up = below < 180 && above > below
  const popupWidth = Math.min(Math.max(rect.width, props.menuWidth || 200), width - 16)
  const anchor = props.align === 'end' ? rect.right - popupWidth : rect.left
  const backdrop = root.value.closest<HTMLElement>('.erp-dialog-backdrop')
  const layer = backdrop ? Number(getComputedStyle(backdrop).zIndex) || 2000 : 2000
  position.value = {
    left: `${Math.max(left + 8, Math.min(anchor, left + width - popupWidth - 8))}px`,
    width: `${popupWidth}px`,
    maxHeight: `${Math.max(44, Math.min(320, up ? above : below))}px`,
    zIndex: String(layer + 5),
    ...(up
      ? { bottom: `${window.innerHeight - rect.top + 5}px` }
      : { top: `${rect.bottom + 5}px` }),
  }
}
function optionButtons() {
  return Array.from(
    menu.value?.querySelectorAll<HTMLButtonElement>('[role=option]:not(:disabled)') || [],
  )
}
function focusOption(index: number) {
  const node = optionButtons()[index]
  node?.focus({ preventScroll: true })
  node?.scrollIntoView?.({ block: 'nearest' })
}
function blocked() {
  return props.disabled || !!root.value?.closest('[inert], [hidden], fieldset:disabled')
}
async function show(keyboard = false) {
  if (blocked()) return
  document.dispatchEvent(new CustomEvent('erp:dropdown-open', { detail: menuId }))
  const dialog = root.value?.closest<HTMLElement>('[role=dialog],[role=alertdialog]')
  if (dialog) dialog.id ||= `erp-owner-${menuId}`
  dialogId.value = dialog?.id || ''
  query.value = ''
  open.value = true
  await nextTick()
  place()
  if (keyboard)
    focusOption(
      Math.max(
        0,
        optionButtons().findIndex((o) => o.getAttribute('aria-selected') === 'true'),
      ),
    )
}
function toggle() {
  if (open.value) close()
  else void show()
}
function close(restore = false) {
  open.value = false
  if (restore) trigger.value?.focus({ preventScroll: true })
}
function choose(value: T) {
  if (blocked()) {
    close()
    return
  }
  invalid.value = false
  emit('update:modelValue', value)
  close(true)
}
function chooseFirst() {
  const first = filtered.value.find((o) => !o.disabled)
  if (first) choose(first.value)
  else if (props.editable && query.value.trim()) choose(query.value.trim() as T)
}
function type(event: Event) {
  const value = (event.target as HTMLInputElement).value
  if (!open.value) void show()
  query.value = value
  invalid.value = false
  emit('update:modelValue', value as T)
  void nextTick(place)
}
function onInvalid() {
  invalid.value = true
  trigger.value?.focus({ preventScroll: true })
}
function outside(event: Event) {
  if (!owns(event.target)) close()
}
function another(event: Event) {
  if ((event as CustomEvent).detail !== menuId) close()
}
function focusOut(event: FocusEvent) {
  if (event.relatedTarget instanceof Node && !owns(event.relatedTarget)) close()
}
function triggerKeys(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) {
    event.stopPropagation()
    event.preventDefault()
    close(true)
  } else if (
    event.key.length === 1 &&
    /\S/.test(event.key) &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey
  ) {
    event.preventDefault()
    void show(true).then(() => typeToOption(event.key))
  }
}
function typeToOption(char: string) {
  const now = Date.now()
  typeahead = now - typeaheadAt < 700 ? typeahead + char : char
  typeaheadAt = now
  const index = optionButtons().findIndex((o) =>
    key(o.textContent || '').startsWith(key(typeahead)),
  )
  if (index >= 0) focusOption(index)
}
function navigate(event: KeyboardEvent) {
  if (event.key === 'Tab') {
    close(true)
    trapDialogTab(event, trigger.value || null)
    return
  }
  if (event.target instanceof HTMLInputElement) return
  if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    const buttons = optionButtons()
    if (!buttons.length) return
    event.preventDefault()
    event.stopPropagation()
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
    focusOption(
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? buttons.length - 1
          : (index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length,
    )
  } else if (
    event.key.length === 1 &&
    /\S/.test(event.key) &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey
  ) {
    event.preventDefault()
    typeToOption(event.key)
  }
}
function listen(enabled: boolean) {
  const action = enabled ? 'addEventListener' : 'removeEventListener'
  document[action]('pointerdown', outside)
  document[action]('erp:dropdown-open', another)
  window[action]('resize', place)
  window[action]('scroll', place, true)
  window.visualViewport?.[action]('resize', place)
  window.visualViewport?.[action]('scroll', place)
  observer?.disconnect()
  if (enabled && typeof ResizeObserver !== 'undefined' && root.value) {
    observer = new ResizeObserver(place)
    observer.observe(root.value)
  }
}
watch(open, listen)
watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) close()
  },
)
watch(
  () => props.modelValue,
  () => {
    invalid.value = false
  },
)
onBeforeUnmount(() => listen(false))
</script>
<style src="./dropdown.css"></style>
