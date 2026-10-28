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
  enableNotificationDevice,
  playNotificationSound,
  pushSupport,
  restoreNotificationDevice,
} from '@/services/notificationPush'

export const useNotificationCenter = defineStore('notification-center', () => {
  const defaults = (): NotificationPreferences => ({ push_enabled: true, sound_enabled: true,
    categories: ['manual', 'sales', 'tracking', 'reminder', 'greeting'] })
  const auth = useAuthStore()
  const items = ref<NotificationItem[]>([]),
    total = ref(0),
    unread = ref(0),
    loading = ref(false),
    error = ref('')
  const prefs = ref<NotificationPreferences>(defaults())
  const pending = ref<string[]>([]),
    unreadOnly = ref(false),
    pushActive = ref(false),
    pushBusy = ref(false),
    pushError = ref(''),
    invitation = ref(false), restoring = ref(false)
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
    prefsReady = true
  let pushAttempt = 0, lastRestoreAt = -Infinity, invitationDismissed = false
  function current(id: number) {
    return id === generation && !!owner.value
  }
  function showInvitation() {
    invitation.value = !!owner.value && !pushActive.value && !invitationDismissed && !restoring.value
  }
  function deferInvitation() {
    invitation.value = false
    invitationDismissed = true
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
  async function preferences(_value: NotificationPreferences) {
    if (!owner.value || preferencesBusy.value) return
    const own = generation,
      token = auth.token
    preferencesBusy.value = true
    error.value = ''
    allowNotificationSound()
    try {
      await notificationsAPI.savePreferences(defaults(), token)
      if (current(own)) prefs.value = defaults()
    } catch {
      if (current(own)) error.value = n('saveError')
    } finally {
      if (current(own)) preferencesBusy.value = false
    }
  }
  function enablePush() {
    if (!owner.value || !auth.token || !auth.user || pushBusy.value || restoring.value) return
    const own = generation, attempt = ++pushAttempt
    pushBusy.value = true
    pushError.value = ''
    support.value = pushSupport()
    if (prefs.value.sound_enabled) allowNotificationSound()
    // No await before this call: the browser permission belongs to the trusted tap.
    const activation = enableNotificationDevice(auth.user.id, auth.token)
    void activation
      .then(async () => {
        if (!current(own) || attempt !== pushAttempt) return
        pushActive.value = true
        invitation.value = false
        await preferences({ ...prefs.value, push_enabled: true })
      })
      .catch((reason) => {
        if (!current(own) || attempt !== pushAttempt) return
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
        if (current(own) && attempt === pushAttempt) pushBusy.value = false
      })
  }
  async function restorePush(force = false) {
    if (!owner.value || !auth.user || !auth.token || !online.value || document.visibilityState === 'hidden' ||
        restoring.value || pushBusy.value || pushActive.value && !force || Date.now() - lastRestoreAt < 30000) return
    const own = generation, attempt = ++pushAttempt, userId = auth.user.id, token = auth.token
    lastRestoreAt = Date.now(); restoring.value = true; support.value = pushSupport()
    try {
      const active = await restoreNotificationDevice(userId, token)
      if (current(own) && attempt === pushAttempt) {
        pushActive.value = active; pushError.value = ''
      }
    } catch {
      if (current(own) && attempt === pushAttempt) {
        pushActive.value = false
        pushError.value = n('restoreError')
      }
    } finally {
      if (current(own) && attempt === pushAttempt) { restoring.value = false; showInvitation() }
    }
  }
  function start() {
    if (interval) clearInterval(interval)
    interval = undefined
    if (owner.value && online.value && document.visibilityState !== 'hidden') {
      void load()
      void restorePush()
      interval = setInterval(() => {
        if (!loading.value) void load()
        void restorePush()
      }, 45000)
    }
  }
  watch(
    owner,
    (value, previous) => {
      generation++
      request++
      pushAttempt++; lastRestoreAt = -Infinity; invitationDismissed = false; restoring.value = false
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
      prefs.value = defaults()
      initialized = false
      prefsReady = true
      seen = new Set()
      if (previous && previous.split(':', 1)[0] !== value.split(':', 1)[0])
        clearNotificationDevice()
      if (value && auth.token && auth.user) {
        const own = generation,
          token = auth.token
        void notificationsAPI
          .preferences(token)
          .then(() => {
            if (current(own)) {
              prefs.value = defaults()
              prefsReady = true
            }
          })
          .catch(() => {
            if (current(own)) error.value = n('error')
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
    if (document.visibilityState !== 'hidden') void restorePush(true)
  }
  const connectivity = () => {
    online.value = navigator.onLine
    start()
    if (online.value) void restorePush(true)
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
    generation++; request++; pushAttempt++
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
    restoring,
    invitation,
    support,
    online,
    preferencesBusy,
    load,
    act,
    preferences,
    enablePush,
    deferInvitation,
  }
})
