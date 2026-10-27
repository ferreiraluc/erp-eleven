import { computed, onScopeDispose, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from './auth'
import {
  notificationsAPI,
  type NotificationItem,
  type NotificationPreferences,
} from '@/services/notifications'
import { notificationText as n } from '@/services/notificationText'
import {
  allowNotificationSound,
  clearNotificationDevice,
  disableNotificationDevice,
  enableNotificationDevice,
  playNotificationSound,
  pushSupport,
  restoreNotificationDevice,
} from '@/services/notificationPush'

export const useNotificationCenter = defineStore('notification-center', () => {
  const auth = useAuthStore()
  const items = ref<NotificationItem[]>([]),
    total = ref(0),
    unread = ref(0),
    loading = ref(false),
    error = ref('')
  const prefs = ref<NotificationPreferences>({
    push_enabled: true,
    sound_enabled: false,
    categories: ['manual', 'sales', 'tracking', 'reminder', 'greeting'],
  })
  const pending = ref<string[]>([]),
    unreadOnly = ref(false),
    pushActive = ref(false),
    pushBusy = ref(false),
    pushError = ref(''),
    invitation = ref(false)
  const support = ref(pushSupport()),
    online = ref(navigator.onLine),
    preferencesBusy = ref(false)
  const owner = computed(() =>
    auth.isAuthenticated && !auth.user?.must_change_password
      ? `${auth.user?.id}:${auth.token}`
      : '',
  )
  let generation = 0,
    request = 0,
    interval: ReturnType<typeof setInterval> | undefined
  let seen = new Set<string>(),
    initialized = false,
    prefsReady = false
  function current(id: number) {
    return id === generation && !!owner.value
  }
  function invitationKey() {
    return `eleven-push-invite-v1:${auth.user?.id}`
  }
  function showInvitation() {
    if (!owner.value || pushActive.value) return
    try {
      invitation.value = Number(localStorage.getItem(invitationKey()) || 0) <= Date.now()
    } catch {
      invitation.value = true
    }
  }
  function deferInvitation() {
    invitation.value = false
    try {
      localStorage.setItem(invitationKey(), String(Date.now() + 86400000))
    } catch {
      /* memory-only dismissal */
    }
  }
  async function load(append = false) {
    if (!owner.value || !online.value || document.visibilityState === 'hidden') return
    const own = generation,
      next = ++request,
      token = auth.token
    loading.value = true
    error.value = ''
    try {
      const result = await notificationsAPI.inbox(
        { offset: append ? items.value.length : 0, limit: 30, unread_only: unreadOnly.value },
        token,
      )
      if (!current(own) || next !== request) return
      if (
        initialized &&
        prefsReady &&
        prefs.value.sound_enabled &&
        result.items.some((item) => !item.read_at && !seen.has(`${item.id}:${item.version}`))
      )
        playNotificationSound()
      result.items.forEach((item) => seen.add(`${item.id}:${item.version}`))
      initialized = true
      items.value = append
        ? [
            ...items.value,
            ...result.items.filter(
              (item) => !items.value.some((existing) => existing.id === item.id),
            ),
          ]
        : result.items
      total.value = result.total
      unread.value = result.unread_count
    } catch {
      if (current(own) && next === request) error.value = n('error')
    } finally {
      if (current(own) && next === request) loading.value = false
    }
  }
  async function act(id: string, action: 'read' | 'ack' | 'all', note?: string, version?: number) {
    if (!owner.value || pending.value.includes(id)) return false
    const own = generation,
      token = auth.token
    pending.value = [...pending.value, id]
    error.value = ''
    try {
      if (action === 'all') await notificationsAPI.readAll(token)
      else if (action === 'ack') await notificationsAPI.acknowledge(id, note, version, token)
      else await notificationsAPI.read(id, token)
      if (!current(own)) return false
      await load()
      return true
    } catch (reason) {
      if (current(own)) error.value = n((reason as {response?:{status?:number}}).response?.status === 409 ? 'conflict' : 'saveError')
      return false
    } finally {
      if (current(own)) pending.value = pending.value.filter((value) => value !== id)
    }
  }
  async function preferences(value: NotificationPreferences) {
    if (!owner.value || preferencesBusy.value) return
    const own = generation,
      token = auth.token
    preferencesBusy.value = true
    error.value = ''
    if (value.sound_enabled) allowNotificationSound()
    try {
      const result = await notificationsAPI.savePreferences(value, token)
      if (current(own)) prefs.value = result
    } catch {
      if (current(own)) error.value = n('saveError')
    } finally {
      if (current(own)) preferencesBusy.value = false
    }
  }
  function enablePush() {
    if (!owner.value || !auth.token || !auth.user || pushBusy.value) return
    const own = generation
    pushBusy.value = true
    pushError.value = ''
    support.value = pushSupport()
    if (prefs.value.sound_enabled) allowNotificationSound()
    // No await before this call: the browser permission belongs to the trusted tap.
    const activation = enableNotificationDevice(auth.user.id, auth.token)
    void activation
      .then(async () => {
        if (!current(own)) return
        pushActive.value = true
        invitation.value = false
        await preferences({ ...prefs.value, push_enabled: true })
      })
      .catch((reason) => {
        if (!current(own)) return
        support.value = pushSupport()
        pushError.value = n(
          reason instanceof Error && reason.message === 'unavailable'
            ? 'unavailable'
            : support.value === 'denied'
              ? 'denied'
              : 'pushError',
        )
      })
      .finally(() => {
        if (current(own)) pushBusy.value = false
      })
  }
  async function disablePush() {
    if (!owner.value || !auth.token || pushBusy.value) return
    const own = generation,
      token = auth.token
    pushBusy.value = true
    pushError.value = ''
    try {
      await disableNotificationDevice(token)
      if (current(own)) {
        pushActive.value = false
        deferInvitation()
      }
    } catch {
      if (current(own)) {
        pushActive.value = false
        pushError.value = n('saveError')
      }
    } finally {
      if (current(own)) pushBusy.value = false
    }
  }
  function start() {
    if (interval) clearInterval(interval)
    interval = undefined
    if (owner.value && online.value && document.visibilityState !== 'hidden') {
      void load()
      interval = setInterval(() => {
        if (!loading.value) void load()
      }, 45000)
    }
  }
  watch(
    owner,
    (value, previous) => {
      generation++
      request++
      items.value = []
      total.value = 0
      unread.value = 0
      error.value = ''
      loading.value = false
      pending.value = []
      pushActive.value = false
      pushBusy.value = false
      pushError.value = ''
      preferencesBusy.value = false
      invitation.value = false
      prefs.value = {
        push_enabled: true,
        sound_enabled: false,
        categories: ['manual', 'sales', 'tracking', 'reminder', 'greeting'],
      }
      initialized = false
      prefsReady = false
      seen = new Set()
      if (previous && previous.split(':', 1)[0] !== value.split(':', 1)[0])
        clearNotificationDevice()
      if (value && auth.token && auth.user) {
        const own = generation,
          token = auth.token
        void notificationsAPI
          .preferences(token)
          .then((result) => {
            if (current(own)) {
              prefs.value = result
              prefsReady = true
            }
          })
          .catch(() => {
            if (current(own)) error.value = n('error')
          })
        void restoreNotificationDevice(auth.user.id, token)
          .then((active) => {
            if (current(own)) {
              pushActive.value = active
              showInvitation()
            }
          })
          .catch(() => {
            if (current(own)) showInvitation()
          })
      }
      start()
    },
    { immediate: true, flush: 'sync' },
  )
  watch(unreadOnly, () => {
    void load()
  })
  const visibility = () => {
    support.value = pushSupport()
    start()
  }
  const connectivity = () => {
    online.value = navigator.onLine
    start()
  }
  let soundUnlocked = false
  const unlockSound = () => {
    if (!soundUnlocked && owner.value && prefsReady && prefs.value.sound_enabled)
      soundUnlocked = allowNotificationSound()
  }
  document.addEventListener('visibilitychange', visibility)
  document.addEventListener('pointerdown', unlockSound, { passive: true })
  window.addEventListener('online', connectivity)
  window.addEventListener('offline', connectivity)
  onScopeDispose(() => {
    if (interval) clearInterval(interval)
    document.removeEventListener('visibilitychange', visibility)
    document.removeEventListener('pointerdown', unlockSound)
    window.removeEventListener('online', connectivity)
    window.removeEventListener('offline', connectivity)
  })
  return {
    items,
    total,
    unread,
    loading,
    error,
    prefs,
    pending,
    unreadOnly,
    pushActive,
    pushBusy,
    pushError,
    invitation,
    support,
    online,
    preferencesBusy,
    load,
    act,
    preferences,
    enablePush,
    disablePush,
    deferInvitation,
  }
})
