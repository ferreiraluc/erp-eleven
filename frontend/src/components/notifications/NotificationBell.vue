<template>
  <div
    v-if="auth?.isAuthenticated && !auth.user?.must_change_password"
    ref="root"
    class="notification-control"
  >
    <button
      ref="trigger"
      type="button"
      class="notification-bell"
      :aria-label="label"
      :title="label"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="toggle"
      @keydown.down.prevent="show(true)"
    >
      <Bell :size="16" aria-hidden="true" />
      <span v-if="center && center.unread > 0" class="notification-bell__count">{{
        center.unread > 99 ? '99+' : center.unread
      }}</span>
    </button>
    <Teleport to="body">
      <section
        v-if="mounted && center"
        v-show="open"
        :id="panelId"
        ref="panel"
        class="notification-dropdown"
        :style="position"
        role="dialog"
        :aria-labelledby="`${panelId}-title`"
      >
        <header class="notification-dropdown__header">
          <div>
            <h2 :id="`${panelId}-title`">{{ n('title') }}</h2>
            <span>{{ n('recent') }}</span>
          </div>
          <div class="notification-dropdown__tools">
            <button
              type="button"
              class="notification-dropdown__icon"
              :disabled="center.loading"
              :aria-label="n('refresh')"
              :title="n('refresh')"
              @click="center.load()"
            >
              <RefreshCw :size="15" aria-hidden="true" />
            </button>
            <button
              ref="dismiss"
              type="button"
              class="notification-dropdown__icon"
              :aria-label="n('close')"
              :title="n('close')"
              @click="close(true)"
            >
              <X :size="17" aria-hidden="true" />
            </button>
          </div>
        </header>
        <div class="notification-dropdown__scroll">
          <NotificationInbox compact @navigate="close()" />
        </div>
        <RouterLink to="/notificacoes" class="notification-dropdown__history" @click="close()"
          >{{ n('history') }} <ArrowRight :size="15" aria-hidden="true"
        /></RouterLink>
      </section>
    </Teleport>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { getActivePinia } from 'pinia'
import { RouterLink, useRoute } from 'vue-router'
import { ArrowRight, Bell, RefreshCw, X } from 'lucide-vue-next'
import NotificationInbox from './NotificationInbox.vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationCenter } from '@/stores/notificationCenter'
import { notificationText as n } from '@/services/notificationText'
const auth = getActivePinia() ? useAuthStore() : null
const center = auth ? useNotificationCenter() : null
const route = useRoute()
const root = ref<HTMLElement>(),
  trigger = ref<HTMLButtonElement>(),
  panel = ref<HTMLElement>(),
  dismiss = ref<HTMLButtonElement>()
const open = ref(false),
  mounted = ref(false),
  position = ref<Record<string, string>>({})
const panelId = `notification-dropdown-${useId()}`
const owner = computed(() =>
  auth?.isAuthenticated && !auth.user?.must_change_password ? `${auth.user?.id}:${auth.token}` : '',
)
const label = computed(
  () => `${n('title')}${center?.unread ? ` · ${n('unread', { count: center.unread })}` : ''}`,
)
let observer: ResizeObserver | undefined
function owns(target: EventTarget | null) {
  return target instanceof Node && (root.value?.contains(target) || panel.value?.contains(target))
}
function place() {
  if (!open.value || !trigger.value) return
  const rect = trigger.value.getBoundingClientRect(),
    viewport = window.visualViewport
  const width = viewport?.width || window.innerWidth,
    height = viewport?.height || window.innerHeight
  const left = viewport?.offsetLeft || 0,
    top = viewport?.offsetTop || 0
  if (rect.bottom < top || rect.top > top + height) {
    close()
    return
  }
  const below = top + height - rect.bottom - 12,
    above = rect.top - top - 12
  const up = below < 220 && above > below,
    popupWidth = Math.min(440, width * 0.7, width - 16)
  position.value = {
    left: `${Math.max(left + 8, Math.min(rect.right - popupWidth, left + width - popupWidth - 8))}px`,
    width: `${popupWidth}px`,
    maxHeight: `${Math.max(80, Math.min(660, up ? above : below))}px`,
    ...(up
      ? { bottom: `${window.innerHeight - rect.top + 6}px` }
      : { top: `${rect.bottom + 6}px` }),
  }
}
async function show(keyboard = false) {
  if (!owner.value || auth?.user?.must_change_password) return
  document.dispatchEvent(new CustomEvent('erp:dropdown-open', { detail: panelId }))
  mounted.value = true
  open.value = true
  if (!center?.loading) void center?.load()
  await nextTick()
  if (!open.value) return
  place()
  if (keyboard) dismiss.value?.focus({ preventScroll: true })
}
function toggle(event: MouseEvent) {
  if (open.value) close()
  else void show(event.detail === 0)
}
function close(restore = false) {
  open.value = false
  if (restore) trigger.value?.focus({ preventScroll: true })
}
function outside(event: Event) {
  if (!owns(event.target)) close()
}
function another(event: Event) {
  if ((event as CustomEvent).detail !== panelId) close()
}
function focusOut(event: Event) {
  const focus = event as FocusEvent
  if (focus.relatedTarget instanceof Node && !owns(focus.relatedTarget)) close()
}
function keys(event: Event) {
  const key = event as KeyboardEvent
  if (open.value && key.key === 'Escape' && !event.defaultPrevented) {
    event.preventDefault()
    event.stopPropagation()
    close(true)
  }
}
function listen(enabled: boolean) {
  const action = enabled ? 'addEventListener' : 'removeEventListener'
  document[action]('pointerdown', outside)
  document[action]('erp:dropdown-open', another)
  document[action]('focusout', focusOut)
  document[action]('keydown', keys)
  window[action]('resize', place)
  window[action]('scroll', place, true)
  window.visualViewport?.[action]('resize', place)
  window.visualViewport?.[action]('scroll', place)
  observer?.disconnect()
  observer = undefined
  if (enabled && typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(place)
    if (trigger.value) observer.observe(trigger.value)
  }
}
watch(open, listen, { flush: 'sync' })
watch(owner, () => {
  close()
  mounted.value = false
})
watch(
  () => route.fullPath,
  () => close(),
)
onBeforeUnmount(() => {
  listen(false)
})
</script>
<style scoped>
.notification-control {
  display: inline-flex;
  flex: 0 0 32px;
  width: 32px;
  height: 32px;
}
.notification-bell {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  min-width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid #dbe4ef;
  border-radius: 50%;
  color: #475569;
  background: #fff;
  cursor: pointer;
}
.notification-bell:hover,
.notification-bell[aria-expanded='true'] {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #bfdbfe;
}
.notification-bell:focus-visible,
.notification-dropdown :is(button, a):focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
.notification-bell__count {
  position: absolute;
  right: -4px;
  top: -4px;
  min-width: 16px;
  height: 16px;
  padding: 0 3px;
  display: grid;
  place-items: center;
  border: 2px solid #fff;
  border-radius: 12px;
  background: #dc2626;
  color: white;
  font:
    800 9px/1 system-ui,
    sans-serif;
}
.notification-dropdown {
  position: fixed;
  z-index: 2005;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #d6dee8;
  border-radius: 16px;
  background: #fff;
  box-shadow:
    0 16px 44px #0f172a26,
    0 2px 8px #0f172a12;
  color: #0f172a;
}
.notification-dropdown__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px 12px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.notification-dropdown__header h2 {
  margin: 0;
  font-size: 17px;
  line-height: 1.3;
  font-weight: 750;
}
.notification-dropdown__header span {
  display: block;
  margin-top: 3px;
  font-size: 11px;
  color: #64748b;
}
.notification-dropdown__tools {
  display: flex;
  gap: 4px;
}
.notification-dropdown__icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: #f1f5f9;
  color: #64748b;
  cursor: pointer;
}
.notification-dropdown__icon:hover {
  background: #e2e8f0;
  color: #1d4ed8;
}
.notification-dropdown__icon:disabled {
  opacity: 0.5;
  cursor: wait;
}
.notification-dropdown__scroll {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}
.notification-dropdown__history {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  padding: 13px 16px;
  color: #1d4ed8;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  font-size: 13px;
  font-weight: 650;
  text-decoration: none;
  flex-shrink: 0;
}
.notification-dropdown__history:hover {
  background: #eff6ff;
}
</style>
