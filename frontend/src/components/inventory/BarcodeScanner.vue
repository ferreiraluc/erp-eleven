<template>
  <div class="barcode-scanner-overlay" @click.self="emit('close')">
    <div class="barcode-scanner-modal">
      <div class="scanner-header">
        <h3>Escanear Código</h3>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="scanner-body">
        <div v-if="!cameraError" class="camera-container">
          <div id="qr-reader" class="qr-reader"></div>
          <div class="scan-line"></div>
          <p class="scanner-hint">Aponte a câmera para o código de barras</p>
        </div>

        <div v-if="cameraError" class="camera-error">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="48" height="48" class="error-icon">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p>Câmera não disponível</p>
        </div>

        <div class="manual-entry">
          <label class="manual-label">Ou insira o código manualmente:</label>
          <div class="manual-input-row">
            <input
              v-model="manualCode"
              type="text"
              placeholder="Código de barras..."
              class="manual-input"
              @keyup.enter="submitManual"
              ref="manualInputRef"
            />
            <button @click="submitManual" class="manual-btn" :disabled="!manualCode.trim()">
              Buscar
            </button>
          </div>
        </div>
      </div>

      <div v-if="timeoutWarning" class="timeout-warning">
        Sem detecção. Use o campo manual acima.
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const emit = defineEmits<{
  (e: 'barcode-detected', code: string): void
  (e: 'close'): void
}>()

const cameraError = ref(false)
const manualCode = ref('')
const timeoutWarning = ref(false)
const manualInputRef = ref<HTMLInputElement>()
let html5QrCode: any = null
let timeoutId: ReturnType<typeof setTimeout> | null = null

onMounted(async () => {
  try {
    const { Html5Qrcode } = await import('html5-qrcode')
    html5QrCode = new Html5Qrcode('qr-reader')

    await html5QrCode.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: { width: 250, height: 150 } },
      (decodedText: string) => {
        if (navigator.vibrate) navigator.vibrate(200)
        stopScanner()
        emit('barcode-detected', decodedText)
      },
      () => {}
    )

    // 30s timeout
    timeoutId = setTimeout(() => {
      timeoutWarning.value = true
      manualInputRef.value?.focus()
    }, 30000)
  } catch (err: any) {
    cameraError.value = true
    manualInputRef.value?.focus()
  }
})

onUnmounted(() => {
  stopScanner()
})

function stopScanner() {
  if (timeoutId) clearTimeout(timeoutId)
  if (html5QrCode) {
    html5QrCode.stop().catch(() => {})
    html5QrCode = null
  }
}

function submitManual() {
  const code = manualCode.value.trim()
  if (!code) return
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
