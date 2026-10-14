// Deliberately independent of Vue, CSS and hashed bundles; compatible with CSP.
;(function () {
  const retryParam = '_erp_reload'
  const retryKey = 'erp:asset-retry-at'
  const retryWindow = 5 * 60 * 1000
  let ready = false
  let failed = false
  let navigating = false
  let panelPending = false
  let phase = 'ARQUIVOS'
  const release = document.currentScript?.getAttribute('data-release') || 'anterior'
  let diagnostic = 'AGUARDANDO'

  function isReady() {
    // Older cached entry bundles do not dispatch application-ready. Vue marks
    // their mounted root as well, so updating this stable script must not reload
    // an already open form or show a false timeout warning in those versions.
    return ready || Boolean(document.getElementById('app')?.hasAttribute('data-v-app'))
  }

  function reload() {
    if (navigating) return
    navigating = true
    const url = new URL(window.location.href)
    url.searchParams.set(retryParam, String(Date.now()))
    try { window.sessionStorage.setItem(retryKey, String(Date.now())) } catch { /* private mode */ }
    // Keep the route, query and authentication. The query also bounds retries
    // when sessionStorage is unavailable; never clear it until a healthy boot.
    window.location.replace(url.href)
  }

  function showRecovery() {
    if (!document.body) {
      if (!panelPending) {
        panelPending = true
        document.addEventListener('DOMContentLoaded', showRecovery, { once: true })
      }
      return
    }
    if (document.getElementById('erp-load-recovery')) return
    const panel = document.createElement('section')
    panel.id = 'erp-load-recovery'
    panel.setAttribute('role', 'alert')
    panel.style.cssText = 'position:fixed;z-index:2147483647;left:16px;right:16px;bottom:24px;max-width:520px;margin:auto;padding:20px;border:1px solid #cbd5e1;border-radius:16px;background:#fff;color:#172033;box-shadow:0 8px 32px #0003;font:16px/1.5 Arial,sans-serif;box-sizing:border-box'
    const title = document.createElement('strong')
    title.textContent = 'Não foi possível carregar esta tela'
    const message = document.createElement('p')
    message.textContent = window.navigator.onLine === false
      ? 'Você está sem conexão. Reconecte e toque em Recarregar sistema.'
      : ready
        ? 'Alguns arquivos ficaram indisponíveis após uma atualização. Recarregue quando puder; informações ainda não salvas nesta tela podem ser perdidas.'
        : 'Verifique sua conexão e recarregue para buscar a versão atual do sistema.'
    const detail = document.createElement('small')
    detail.textContent = `Diagnóstico: ${diagnostic} · ${phase} · ${release}`
    detail.style.cssText = 'display:block;margin:12px 0;color:#526077;font:12px/1.5 monospace;overflow-wrap:anywhere'
    const button = document.createElement('button')
    button.type = 'button'
    button.textContent = 'Recarregar sistema'
    button.style.cssText = 'border:0;border-radius:10px;padding:12px 18px;background:#245ce8;color:white;font:600 16px Arial,sans-serif;cursor:pointer;min-height:44px'
    button.addEventListener('click', reload)
    panel.append(title, message, detail, button)
    document.body.appendChild(panel)
  }

  function failAsset(code = 'MODULO') {
    diagnostic = code
    failed = true
    if (navigating) return
    ready = isReady()
    let lastRetry = 0
    try { lastRetry = Number(window.sessionStorage.getItem(retryKey)) || 0 } catch { /* private mode */ }
    const alreadyRetried = new URL(window.location.href).searchParams.has(retryParam)
    if (!ready && window.navigator.onLine !== false && !alreadyRetried && Date.now() - lastRetry > retryWindow) {
      reload()
    } else {
      // Never reload an active sale/form automatically after a lazy chunk fails.
      showRecovery()
    }
  }

  function isChunkError(error) {
    const message = String(error && error.message || error || '')
    return /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS|Loading chunk .+ failed/i.test(message)
  }

  window.addEventListener('error', function (event) {
    const target = event.target
    if (!target || !['SCRIPT', 'LINK'].includes(target.tagName)) {
      if (!isReady() && event.error) {
        failed = true
        diagnostic = 'JAVASCRIPT'
        showRecovery()
      }
      return
    }
    if (target.tagName === 'LINK' && !['stylesheet', 'modulepreload'].includes(target.rel)) return
    const url = new URL(target.src || target.href || '', window.location.href)
    if (url.origin === window.location.origin && url.pathname.startsWith('/assets/')) failAsset(target.tagName === 'LINK' && target.rel === 'stylesheet' ? 'CSS' : 'JS')
  }, true)

  window.addEventListener('erp:entry-ready', function () { phase = 'SESSAO/ROTA' })
  window.addEventListener('unhandledrejection', function (event) {
    if (isChunkError(event.reason)) failAsset()
    else if (!isReady()) {
      failed = true
      diagnostic = 'INICIALIZACAO'
      showRecovery()
    }
  })

  window.addEventListener('vite:preloadError', function (event) {
    if (isChunkError(event.payload)) {
      event.preventDefault()
      failAsset()
    }
  })
  window.addEventListener('erp:route-load-error', function (event) {
    if (isChunkError(event.detail)) failAsset()
  })
  window.addEventListener('erp:boot-error', function (event) {
    if (isChunkError(event.detail)) failAsset()
    else { failed = true; diagnostic = 'ROTA'; showRecovery() }
  })

  const timeout = setTimeout(function () {
    if (!isReady() && !navigating) { diagnostic = 'TEMPO'; showRecovery() }
  }, 15000)

  window.addEventListener('erp:application-ready', function () {
    ready = true
    clearTimeout(timeout)
    if (failed || navigating) return
    document.getElementById('erp-load-recovery')?.remove()
    const url = new URL(window.location.href)
    if (url.searchParams.has(retryParam)) {
      url.searchParams.delete(retryParam)
      window.history.replaceState(window.history.state, '', url.href)
    }
  })
})()
