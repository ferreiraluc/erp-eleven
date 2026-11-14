// Public installation metadata only. Never fetch ERP sessions or device IDs here.
function validAndroidRelease(value) {
  if (!value || !['pilot', 'ready'].includes(value.status)) return false
  try {
    const url = new URL(value.url)
    return (
      url.origin === 'https://github.com' &&
      /^\/ferreiraluc\/erp-eleven\/releases\/download\/[^/]+\/[^/]+\.apk$/.test(url.pathname) &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash &&
      typeof value.version === 'string' &&
      value.version.length > 0 &&
      value.version.length < 80 &&
      Number.isSafeInteger(value.sizeBytes) &&
      value.sizeBytes > 0 &&
      /^[a-f0-9]{64}$/i.test(value.sha256)
    )
  } catch {
    return false
  }
}

function validIosRelease(value, now = Date.now()) {
  if (
    !value ||
    value.status !== 'ready' ||
    typeof value.version !== 'string' ||
    !value.version ||
    value.version.length > 80
  )
    return false
  try {
    const url = new URL(value.manifestUrl)
    return (
      url.origin === 'https://elevenparispy.com' &&
      url.pathname === '/download/ios/manifest.plist' &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash &&
      typeof value.expiresAt === 'string' &&
      Number.isFinite(Date.parse(value.expiresAt)) &&
      Date.parse(value.expiresAt) > now
    )
  } catch {
    return false
  }
}

function applyReleases(data, doc = document, now = Date.now()) {
  if (data?.schemaVersion !== 1) throw new Error('Unsupported release metadata')
  const android = data.android
  const androidDownload = doc.getElementById('android-download')
  const androidState = doc.getElementById('android-state')
  const androidBadge = doc.getElementById('android-badge')
  androidDownload.hidden = true
  androidDownload.removeAttribute('href')
  if (validAndroidRelease(android)) {
    androidDownload.href = android.url
    androidDownload.hidden = false
    androidState.hidden = true
    androidBadge.textContent = android.status === 'pilot' ? 'Piloto disponível' : 'Disponível'
    androidBadge.className = `badge ${android.status === 'pilot' ? 'badge-pilot' : 'badge-ready'}`
    doc.getElementById('android-meta').textContent =
      `${android.version} · ${(android.sizeBytes / 1024 / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB · APK`
    doc.getElementById('android-meta').hidden = false
    doc.getElementById('android-pilot').hidden = android.status !== 'pilot'
    doc.getElementById('android-sha').textContent = android.sha256
    doc.getElementById('android-integrity').hidden = false
  } else {
    androidState.hidden = false
    androidState.textContent =
      'O arquivo Android está temporariamente indisponível. Continue pelo navegador e tente novamente mais tarde.'
    androidBadge.textContent = 'Indisponível'
    for (const id of ['android-meta', 'android-pilot', 'android-integrity'])
      doc.getElementById(id).hidden = true
  }
  const ios = data.ios
  const iosInstall = doc.getElementById('ios-install')
  iosInstall.hidden = true
  iosInstall.removeAttribute('href')
  doc.getElementById('ios-meta').hidden = true
  doc.getElementById('ios-badge').className = 'badge badge-neutral'
  doc.getElementById('ios-badge').textContent = 'Em preparação'
  doc.getElementById('ios-state').textContent =
    'Aguardando a assinatura Apple Developer, o cadastro dos aparelhos e a assinatura do aplicativo.'
  if (validIosRelease(ios, now)) {
    iosInstall.href = `itms-services://?action=download-manifest&url=${encodeURIComponent(ios.manifestUrl)}`
    iosInstall.hidden = false
    doc.getElementById('ios-state').textContent =
      'Abra no Safari do iPhone ou iPad já cadastrado para iniciar a instalação.'
    doc.getElementById('ios-badge').textContent = 'Disponível'
    doc.getElementById('ios-badge').className = 'badge badge-ready'
    doc.getElementById('ios-meta').textContent =
      `Versão ${ios.version} · Autorização válida até ${new Date(ios.expiresAt).toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' })}`
    doc.getElementById('ios-meta').hidden = false
  } else if (ios?.status === 'ready') {
    doc.getElementById('ios-state').textContent =
      'A instalação do iPhone está aguardando a atualização da assinatura. Continue usando o ERP pelo navegador.'
    doc.getElementById('ios-badge').textContent = 'Aguardando atualização'
    doc.getElementById('ios-meta').hidden = true
  }
}

async function loadReleases(doc = document, fetcher = fetch) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 12000)
  try {
    const response = await fetcher('/download/releases.json', {
      cache: 'no-store',
      credentials: 'omit',
      signal: controller.signal,
    })
    if (!response.ok) throw new Error('Release metadata unavailable')
    applyReleases(await response.json(), doc)
  } catch {
    doc.getElementById('release-error').hidden = false
    for (const id of ['android-download', 'ios-install']) {
      doc.getElementById(id).hidden = true
      doc.getElementById(id).removeAttribute('href')
    }
    doc.getElementById('android-state').textContent =
      'Não foi possível conferir a versão disponível.'
    doc.getElementById('android-badge').textContent = 'Indisponível'
  } finally {
    clearTimeout(timeout)
  }
}

if (typeof document !== 'undefined' && document.getElementById('android-download'))
  void loadReleases()
