<template>
  <div class="barcode-scanner-overlay erp-dialog-backdrop" @click.self="emit('close')">
    <div v-erp-dialog class="barcode-scanner-modal erp-dialog erp-dialog--media">
      <div class="scanner-header erp-dialog__header">
        <h3>{{ tr('Escanear Código') }}</h3>
        <button data-dialog-close :aria-label="tr('Fechar')" @click="emit('close')" class="close-btn erp-button erp-button--ghost erp-button--icon">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="scanner-body erp-dialog__body">
        <div v-if="!cameraError" class="camera-container">
          <div id="qr-reader" class="qr-reader"></div>
          <div class="scan-line"></div>
          <p class="scanner-hint">{{ tr('Aponte a câmera para o QR Code ou código de barras') }}</p>
          <p class="scanner-hint">{{ tr('Se estiver desfocado, afaste um pouco a etiqueta e use o zoom.') }}</p>
        </div>

        <p v-if="switching" role="status" class="scanner-hint">{{ tr('Preparando câmera...') }}</p>
        <div v-if="!cameraError" class="camera-controls">
          <ErpSelect v-if="cameras.length > 1" :model-value="selectedCamera" :disabled="switching" :label="tr('Câmera')" @update:model-value="changeCamera(String($event))">
            <option v-for="(camera, index) in cameras" :key="camera.deviceId" :value="camera.deviceId">{{ camera.label || `${tr('Câmera')} ${index + 1}` }}</option>
          </ErpSelect>
          <label v-if="zoomRange" class="camera-zoom">{{ tr('Zoom') }}
            <input :value="zoom" type="range" :min="zoomRange.min" :max="zoomRange.max" :step="zoomRange.step || 0.1" :disabled="switching" @change="changeZoom" />
            <span>{{ zoom.toFixed(1) }}×</span>
          </label>
          <button v-if="hasTorch" type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="switching" :aria-pressed="torch" @click="toggleTorch">{{ tr(torch ? 'Apagar luz' : 'Acender luz') }}</button>
        </div>

        <div v-if="cameraError" class="camera-error">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="48" height="48" class="error-icon">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p>{{ tr('Câmera não disponível') }}</p>
        </div>

        <div class="manual-entry">
          <label class="manual-label">{{ tr('Ou insira o código manualmente:') }}</label>
          <div class="manual-input-row">
            <input
              v-model="manualCode"
              type="text"
              :placeholder="tr('Código de barras...')"
              class="manual-input"
              @keyup.enter="submitManual"
              ref="manualInputRef"
            />
            <button @click="submitManual" class="manual-btn erp-button erp-button--primary" :disabled="!manualCode.trim()">
              {{ tr('Buscar') }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="timeoutWarning" class="timeout-warning">
        {{ tr('Sem detecção. Use o campo manual acima.') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import { useInventoryI18n } from '@/components/inventory/i18n'
const { tr } = useInventoryI18n()
import { ref, onMounted, onUnmounted } from 'vue'
import type { Html5Qrcode } from 'html5-qrcode'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { cameraConstraintFailure, preferredScannerCamera, scannerFocusConstraints, scannerVideoConstraints, type ScannerCapabilities } from '@/services/scannerCamera'

const emit = defineEmits<{
  (e: 'barcode-detected', code: string): void
  (e: 'close'): void
}>()

const cameraError = ref(false)
const manualCode = ref('')
const timeoutWarning = ref(false)
const manualInputRef = ref<HTMLInputElement>()
const cameras = ref<MediaDeviceInfo[]>([])
const selectedCamera = ref('')
const switching = ref(false)
const hasTorch = ref(false), torch = ref(false)
const zoomRange = ref<ScannerCapabilities['zoom'] | null>(null)
const zoom = ref(1)
let html5QrCode: Html5Qrcode | null = null
let cameraRun = 0
let detected = false
let disposed = false
let timeoutId: ReturnType<typeof setTimeout> | null = null

async function listCameras() {
  try {
    const devices = await navigator.mediaDevices?.enumerateDevices()
    if (!disposed) cameras.value = (devices || []).filter(device => device.kind === 'videoinput' && device.deviceId)
  } catch { /* Camera enumeration is optional; facingMode remains available. */ }
}

async function startCamera(deviceId = '') {
  const run = ++cameraRun
  switching.value = true
  hasTorch.value = false; torch.value = false; zoomRange.value = null
  if (timeoutId) clearTimeout(timeoutId)
  try {
    const previous = html5QrCode
    if (previous) { await previous.stop(); if (html5QrCode === previous) html5QrCode = null }
    if (disposed || detected || run !== cameraRun) return
    const { Html5Qrcode } = await import('html5-qrcode')
    if (disposed || detected || run !== cameraRun) return
    const scanner = new Html5Qrcode('qr-reader')
    html5QrCode = scanner
    const success = (decodedText: string) => {
        if (detected || disposed || run !== cameraRun) return
        detected = true
        if (navigator.vibrate) navigator.vibrate(200)
        stopScanner()
        emit('barcode-detected', decodedText)
    }
    const config = { fps: 15, qrbox: (width: number, height: number) => {
      const side = Math.min(360, Math.floor(Math.min(width, height) * 0.88))
      return { width: side, height: side }
    } }
    try {
      await scanner.start(deviceId || { facingMode: 'environment' },
        { ...config, videoConstraints: scannerVideoConstraints(deviceId) }, success, () => {})
    } catch (error) {
      if (disposed || detected || run !== cameraRun || !cameraConstraintFailure(error)) throw error
      // Do not retry denied permission. Unsupported resolution/device gets the
      // library's compatible rear-camera request, without mandatory constraints.
      await scanner.start({ facingMode: 'environment' }, config, success, () => {})
    }

    if (disposed || detected || run !== cameraRun) {
      // A close may happen while camera permission/start is still pending.
      // Keep the local instance so that stream is stopped after start resolves.
      try { await scanner.stop() } catch { /* already stopped */ }
      if (html5QrCode === scanner) html5QrCode = null
      return
    }
    selectedCamera.value = deviceId
    let settings: MediaTrackSettings & { zoom?: number } = {}
    try {
      settings = scanner.getRunningTrackSettings()
      selectedCamera.value = settings.deviceId || deviceId
    } catch { /* Reading camera identity is optional on older browsers. */ }
    try {
      const capabilities = scanner.getRunningTrackCapabilities() as ScannerCapabilities
      hasTorch.value = capabilities.torch === true
      if (capabilities.zoom && capabilities.zoom.max > capabilities.zoom.min) {
        zoomRange.value = { ...capabilities.zoom, max: Math.max(capabilities.zoom.min, Math.min(capabilities.zoom.max, 4)) }
        zoom.value = Math.max(zoomRange.value.min, Math.min(zoomRange.value.max, settings.zoom || capabilities.zoom.min))
      }
      const focus = scannerFocusConstraints(capabilities)
      if (focus) await scanner.applyVideoConstraints(focus).catch(() => {})
    } catch { /* Older Safari lacks camera controls; decoding must continue. */ }
    if (disposed || detected || run !== cameraRun) return
    timeoutWarning.value = false
    timeoutId = setTimeout(() => {
      timeoutWarning.value = true
    }, 30000)
  } catch {
    if (disposed || detected || run !== cameraRun) return
    cameraError.value = true
    manualInputRef.value?.focus()
  } finally { if (!disposed && run === cameraRun) switching.value = false }
}

onMounted(async () => {
  await listCameras()
  let saved = ''
  try { saved = localStorage.getItem('eleven:scanner:camera') || '' } catch { /* optional preference */ }
  await startCamera(preferredScannerCamera(cameras.value, saved))
  if (disposed || detected || cameraError.value) return
  // Labels are available only after camera permission on a first visit.
  const run = cameraRun
  await listCameras()
  const preferred = preferredScannerCamera(cameras.value, saved)
  if (!disposed && !detected && run === cameraRun && preferred && selectedCamera.value && preferred !== selectedCamera.value) await startCamera(preferred)
})

async function changeCamera(id: string) {
  if (switching.value || disposed || detected || id === selectedCamera.value) return
  try { localStorage.setItem('eleven:scanner:camera', id) } catch { /* optional preference */ }
  await startCamera(id)
}
async function changeZoom(event: Event) {
  if (!html5QrCode || !zoomRange.value || switching.value || disposed || detected) return
  const scanner = html5QrCode, run = cameraRun
  const value = Math.max(zoomRange.value.min, Math.min(zoomRange.value.max, Number((event.target as HTMLInputElement).value)))
  if (!Number.isFinite(value)) return
  try {
    await scanner.applyVideoConstraints({ advanced: [{ zoom: value } as MediaTrackConstraintSet] })
    if (!disposed && !detected && run === cameraRun) zoom.value = value
  } catch { /* Unsupported controls cannot interrupt a live scanner. */ }
}
async function toggleTorch() {
  if (!html5QrCode || !hasTorch.value || switching.value || disposed || detected) return
  const scanner = html5QrCode, run = cameraRun
  const value = !torch.value
  try {
    await scanner.applyVideoConstraints({ advanced: [{ torch: value } as MediaTrackConstraintSet] })
    if (!disposed && !detected && run === cameraRun) torch.value = value
  } catch { /* Keep scanning if the browser refuses the light. */ }
}

onUnmounted(() => {
  disposed = true
  stopScanner()
})

function stopScanner() {
  if (timeoutId) clearTimeout(timeoutId)
  if (html5QrCode) {
    try { html5QrCode.stop().catch(() => {}) } catch { /* start still pending */ }
    html5QrCode = null
  }
}

function submitManual() {
  const code = manualCode.value.trim()
  if (!code || detected) return
  detected = true
  stopScanner()
  emit('barcode-detected', code)
}
</script>

<style scoped>
.barcode-scanner-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.barcode-scanner-modal {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 420px;
  overflow: hidden;
}
.scanner-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e5e7eb;
}
.scanner-header h3 { margin: 0; font-size: 1rem; font-weight: 600; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; padding: 4px; }
.scanner-body { padding: 1rem 1.25rem; }
.camera-container { position: relative; margin-bottom: 1rem; }
.qr-reader { width: 100%; border-radius: 8px; overflow: hidden; }
.scan-line {
  position: absolute;
  top: 50%;
  left: 10%;
  right: 10%;
  height: 2px;
  background: #ef4444;
  animation: scanAnim 2s linear infinite;
}
@keyframes scanAnim {
  0% { top: 20%; } 100% { top: 80%; }
}
.scanner-hint { text-align: center; font-size: 0.75rem; color: #6b7280; margin-top: 0.5rem; }
.camera-controls { display: flex; flex-direction: column; gap: 8px; margin: 10px 0; }
.camera-zoom { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #475569; }
.camera-zoom input { flex: 1; min-width: 0; }
.camera-zoom span { min-width: 32px; }
.camera-error { text-align: center; padding: 1.5rem 0; color: #ef4444; }
.error-icon { margin: 0 auto 0.5rem; display: block; }
.manual-entry { margin-top: 1rem; }
.manual-label { display: block; font-size: 0.8rem; color: #374151; margin-bottom: 0.5rem; }
.manual-input-row { display: flex; gap: 0.5rem; }
.manual-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
}
.manual-input:focus { border-color: #3b82f6; }
.manual-btn {
  padding: 0.5rem 1rem;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}
.manual-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.timeout-warning {
  padding: 0.75rem 1.25rem;
  background: #fef3c7;
  color: #92400e;
  font-size: 0.8rem;
  border-top: 1px solid #fde68a;
}
</style>
