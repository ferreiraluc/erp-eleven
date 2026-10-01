import type { Router } from 'vue-router'
import type { useAuthStore } from '@/stores/auth'
import api from './api'

export function startActivity(router: Router, auth: ReturnType<typeof useAuthStore>) {
  let lastInput = Date.now(), lastTick = Date.now(), sequence = 0, seconds = 0
  let id = '', module = '', started = 0
  let queue = Promise.resolve()
  const usable = () => auth.isAuthenticated && !auth.user?.must_change_password && !!router.currentRoute.value.meta.requiresAuth
  function send() {
    if (!id || !usable()) return
    const payload = { id, module, sequence: sequence++, seconds: Math.min(30, Math.floor(seconds)) }
    const session = auth.token
    seconds = 0
    queue = queue.then(async () => {
      if (auth.token === session && usable()) await api.post('/api/access/activity', payload)
    }).catch(() => {})
  }
  function begin() {
    send()
    id = ''; seconds = 0; sequence = 0
    lastTick = Date.now(); started = lastTick
    if (!usable()) return
    module = router.currentRoute.value.path.split('/')[1] || 'dashboard'
    id = crypto.randomUUID()
    send()
  }
  function tick() {
    const moment = Date.now()
    if (usable() && !document.hidden && document.hasFocus()) {
      seconds += Math.max(0, Math.min(moment, lastInput + 60000) - lastTick) / 1000
    }
    lastTick = moment
    if (started && moment - started > 300000) begin()
    else send()
  }
  for (const event of ['pointerdown', 'keydown', 'scroll', 'touchstart']) {
    window.addEventListener(event, () => { lastInput = Date.now() }, { passive: true })
  }
  document.addEventListener('visibilitychange', () => { tick(); if (!document.hidden) begin() })
  window.addEventListener('pagehide', tick)
  router.afterEach(begin)
  setInterval(tick, 15000)
}
