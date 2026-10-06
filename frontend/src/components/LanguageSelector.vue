<template>
  <div ref="root" :class="['locale-control', { 'locale-control-compact': compact, 'locale-align-end': align === 'end' }]" @keydown.esc.stop.prevent="close(true)" @focusout="onFocusOut">
    <Globe v-if="!compact" aria-hidden="true" />
    <span v-if="!compact && !hideLabel">{{ $t('access.language') }}</span>
    <div class="locale-dropdown">
      <button
        ref="trigger"
        type="button"
        class="locale-trigger"
        :aria-label="$t('access.language')"
        :title="currentLanguage.name"
        :aria-expanded="open"
        :aria-controls="menuId"
        @click="open = !open"
        @keydown.down.prevent="openWithKeyboard"
      >
        <span aria-hidden="true">{{ currentLanguage.flag }}</span>
        <span>{{ compact ? currentLanguage.code.toUpperCase() : currentLanguage.name }}</span>
        <ChevronDown :class="['locale-chevron', { rotate: open }]" aria-hidden="true" />
      </button>
      <div v-if="open" :id="menuId" ref="menu" class="locale-menu" :aria-label="$t('access.language')" @keydown="navigateOptions">
        <button
          v-for="lang in availableLocales"
          :key="lang.code"
          type="button"
          class="locale-option"
          :class="{ active: lang.code === locale }"
          :aria-label="lang.name"
          :aria-pressed="lang.code === locale"
          @click="choose(lang.code)"
        >
          <span aria-hidden="true">{{ lang.flag }}</span>
          <span class="locale-info">
            <span class="locale-code">{{ lang.code.toUpperCase() }}</span>
            <span class="locale-name">{{ lang.name }}</span>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, Globe } from 'lucide-vue-next'
import { availableLocales, setLocale } from '@/i18n'

defineProps<{ compact?: boolean; hideLabel?: boolean; align?: 'start' | 'end' }>()
const { locale } = useI18n()
const currentLanguage = computed(() => availableLocales.find(lang => lang.code === locale.value) ?? availableLocales[2]!)
const open = ref(false)
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const menu = ref<HTMLElement | null>(null)
const menuId = `language-menu-${useId()}`

function close(restoreFocus = false) {
  open.value = false
  if (restoreFocus) trigger.value?.focus()
}
function choose(code: string) {
  setLocale(code)
  close(true)
}
function onOutsideClick(event: MouseEvent) {
  if (event.target instanceof Node && !root.value?.contains(event.target)) close()
}
function onFocusOut(event: FocusEvent) {
  if (!(event.relatedTarget instanceof Node) || !root.value?.contains(event.relatedTarget)) close()
}
async function openWithKeyboard() {
  open.value = true
  await nextTick()
  menu.value?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')?.focus()
}
function navigateOptions(event: KeyboardEvent) {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
  const options = Array.from(menu.value?.querySelectorAll<HTMLButtonElement>('button') ?? [])
  if (!options.length) return
  event.preventDefault()
  const current = options.indexOf(document.activeElement as HTMLButtonElement)
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1
    : (current + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length
  options[next]?.focus()
}
onMounted(() => document.addEventListener('click', onOutsideClick))
onUnmounted(() => document.removeEventListener('click', onOutsideClick))
</script>

<style scoped>
.locale-control { display: inline-flex; align-items: center; gap: .45rem; margin-left: auto; }
.locale-control svg { width: 15px; height: 15px; flex: 0 0 15px; }
.locale-dropdown { position: relative; }
.locale-trigger { display: inline-flex; align-items: center; justify-content: center; gap: .35rem; min-height: 36px; max-width: 100%; border: 1px solid #d1d5db; border-radius: 8px; padding: .4rem .5rem; background: #f9fafb; color: #475569; font: inherit; cursor: pointer; white-space: nowrap; }
.locale-trigger:focus-visible, .locale-option:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.locale-trigger:hover { background: #f3f4f6; border-color: #9ca3af; }
.locale-control .locale-chevron { width: 12px; height: 12px; flex: 0 0 12px; transition: transform .2s; }
.locale-chevron.rotate { transform: rotate(180deg); }
.locale-menu { position: absolute; top: 100%; right: 0; z-index: 50; width: 200px; max-width: calc(100vw - 24px); margin-top: .25rem; max-height: 200px; overflow-y: auto; background: #fff; border: 1px solid #d1d5db; border-radius: .5rem; box-shadow: 0 4px 6px -1px rgb(0 0 0 / .1); }
.locale-option { display: flex; align-items: center; gap: .75rem; width: 100%; padding: .75rem; background: none; border: none; cursor: pointer; font-family: inherit; font-size: .875rem; color: #475569; text-align: left; }
.locale-option:hover { background: #f9fafb; }
.locale-option.active { background: #eff6ff; color: #2563eb; }
.locale-info { display: flex; flex-direction: column; gap: .125rem; }
.locale-code { font-weight: 500; line-height: 1; }
.locale-name { font-size: .75rem; color: #6b7280; line-height: 1; }
.locale-control-compact { flex: 0 0 auto; margin-left: 0; }
.locale-control-compact .locale-trigger { height: 32px; min-height: 32px; width: 78px; padding: .25rem .5rem; font-size: .75rem; font-weight: 500; }
.locale-control-compact .locale-menu { left: 0; right: auto; }
.locale-align-end .locale-menu { left: auto; right: 0; }
@media (max-width: 768px) {
  .locale-menu { width: 150px; }
}
@media (max-width: 600px) {
  .locale-control:not(.locale-control-compact) .locale-trigger { min-height: 40px; }
}
@media (max-width: 360px) {
  .locale-control-compact .locale-trigger { width: 72px; }
}
</style>
