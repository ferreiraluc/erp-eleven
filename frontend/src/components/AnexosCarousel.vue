<template>
  <div class="anexos-wrap">

    <!-- Carousel -->
    <div v-if="anexos.length" class="carousel">
      <!-- Main image -->
      <div class="carousel-main">
        <button v-if="anexos.length > 1" class="nav-btn nav-prev" @click.prevent="prev" aria-label="Anterior">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        </button>

        <div class="img-wrapper" @click="openLightbox(current)">
          <img
            :src="dataUrl(anexos[current])"
            :alt="anexos[current].nome_arquivo"
            class="main-img"
          />
          <div class="img-overlay">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"/></svg>
          </div>
        </div>

        <button v-if="anexos.length > 1" class="nav-btn nav-next" @click.prevent="next" aria-label="Próximo">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        </button>
      </div>

      <!-- Info bar -->
      <div class="info-bar">
        <span class="file-name">{{ anexos[current].nome_arquivo }}</span>
        <span class="file-size">{{ formatSize(anexos[current].tamanho) }}</span>
        <button
          v-if="editable"
          class="del-btn"
          @click.prevent="emit('delete', anexos[current])"
          title="Remover anexo"
        >
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          Remover
        </button>
      </div>

      <!-- Thumbnails -->
      <div class="thumbs" v-if="anexos.length > 1">
        <button
          v-for="(a, i) in anexos"
          :key="a.id"
          :class="['thumb-btn', { active: i === current }]"
          @click.prevent="current = i"
        >
          <img :src="dataUrl(a)" :alt="a.nome_arquivo" class="thumb-img" />
        </button>
      </div>

      <!-- Dots -->
      <div v-if="anexos.length > 1" class="dots">
        <button
          v-for="(_, i) in anexos"
          :key="i"
          :class="['dot', { active: i === current }]"
          @click.prevent="current = i"
          :aria-label="`Imagem ${i + 1}`"
        />
      </div>
    </div>

    <!-- Upload zone -->
    <div v-if="editable" class="upload-zone">
      <input
        ref="fileInput"
        type="file"
        accept="image/jpeg,image/png,image/gif,image/webp"
        multiple
        class="hidden-input"
        @change="onFilesSelected"
      />
      <div class="upload-btns-row">
        <button
          type="button"
          class="upload-btn"
          @click="fileInput?.click()"
          :disabled="uploading || anexos.length >= 10"
        >
          <svg v-if="!uploading" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
          <svg v-else class="spin" fill="none" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="spin-track"/><path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" class="spin-path"/></svg>
          <span>{{ uploading ? 'Enviando...' : anexos.length >= 10 ? 'Limite atingido' : 'Galeria' }}</span>
        </button>
        <button
          type="button"
          class="upload-btn camera-btn"
          @click="openCamera"
          :disabled="uploading || anexos.length >= 10"
        >
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
          <span>Câmera</span>
        </button>
      </div>
      <p v-if="errorMsg" class="upload-error">{{ errorMsg }}</p>
    </div>

    <!-- Camera capture modal -->
    <teleport to="body">
      <div v-if="showCamera" class="camera-overlay" @click.self="closeCamera">
        <div class="camera-modal">
          <div class="camera-header">
            <span>Tirar foto</span>
            <button type="button" @click="closeCamera" class="camera-close">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>

          <div class="camera-body">
            <video v-if="!capturedDataUrl" ref="videoEl" autoplay playsinline class="camera-video"></video>
            <img v-else :src="capturedDataUrl" class="camera-preview" alt="Foto capturada" />
            <canvas ref="canvasEl" class="hidden-input"></canvas>
            <p v-if="cameraError" class="camera-error">{{ cameraError }}</p>
          </div>

          <div class="camera-footer">
            <template v-if="!capturedDataUrl">
              <button type="button" class="btn-capture" @click="capturePhoto" :disabled="!cameraReady">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                Capturar
              </button>
            </template>
            <template v-else>
              <button type="button" class="btn-retake" @click="retakePhoto">Tirar novamente</button>
              <button type="button" class="btn-use-photo" @click="usePhoto">Usar esta foto</button>
            </template>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Lightbox -->
    <teleport to="body">
      <div v-if="lightboxIndex !== null" class="lightbox" @click="lightboxIndex = null">
        <button class="lb-close" @click.stop="lightboxIndex = null">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
        <button v-if="anexos.length > 1" class="lb-nav lb-prev" @click.stop="lightboxPrev">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        </button>
        <img
          :src="dataUrl(anexos[lightboxIndex])"
          :alt="anexos[lightboxIndex].nome_arquivo"
          class="lb-img"
          @click.stop
        />
        <button v-if="anexos.length > 1" class="lb-nav lb-next" @click.stop="lightboxNext">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        </button>
        <p class="lb-caption">{{ anexos[lightboxIndex].nome_arquivo }}</p>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import type { PedidoAnexo } from '@/services/api'

const props = withDefaults(defineProps<{
  anexos: PedidoAnexo[]
  editable?: boolean
  uploading?: boolean
  errorMsg?: string
}>(), {
  editable: false,
  uploading: false,
  errorMsg: '',
})

const emit = defineEmits<{
  delete: [anexo: PedidoAnexo]
  upload: [files: File[]]
}>()

const current = ref(0)
const lightboxIndex = ref<number | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

// Camera capture
const showCamera = ref(false)
const videoEl = ref<HTMLVideoElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const capturedDataUrl = ref<string | null>(null)
const cameraStream = ref<MediaStream | null>(null)
const cameraReady = ref(false)
const cameraError = ref('')

async function openCamera() {
  cameraError.value = ''
  capturedDataUrl.value = null
  cameraReady.value = false
  showCamera.value = true
  await nextTick()
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }
    })
    cameraStream.value = stream
    if (videoEl.value) {
      videoEl.value.srcObject = stream
      videoEl.value.onloadedmetadata = () => { cameraReady.value = true }
    }
  } catch (e: any) {
    cameraError.value = e?.name === 'NotAllowedError'
      ? 'Permissão de câmera negada. Verifique as configurações do navegador.'
      : 'Câmera não disponível neste dispositivo.'
  }
}

function closeCamera() {
  cameraStream.value?.getTracks().forEach(t => t.stop())
  cameraStream.value = null
  showCamera.value = false
  capturedDataUrl.value = null
  cameraReady.value = false
}

function capturePhoto() {
  if (!videoEl.value || !canvasEl.value) return
  const v = videoEl.value
  const c = canvasEl.value
  c.width = v.videoWidth
  c.height = v.videoHeight
  c.getContext('2d')!.drawImage(v, 0, 0)
  capturedDataUrl.value = c.toDataURL('image/jpeg', 0.9)
  if (navigator.vibrate) navigator.vibrate(100)
}

function retakePhoto() {
  capturedDataUrl.value = null
}

function usePhoto() {
  if (!capturedDataUrl.value || !canvasEl.value) return
  canvasEl.value.toBlob(blob => {
    if (!blob) return
    const file = new File([blob], `foto_${Date.now()}.jpg`, { type: 'image/jpeg' })
    emit('upload', [file])
    closeCamera()
  }, 'image/jpeg', 0.9)
}

watch(() => props.anexos.length, (n, o) => {
  if (current.value >= n) current.value = Math.max(0, n - 1)
  // jump to new image on upload
  if (n > o) current.value = n - 1
})

function dataUrl(a: PedidoAnexo) {
  return `data:${a.tipo_arquivo};base64,${a.dados}`
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function prev() {
  current.value = (current.value - 1 + props.anexos.length) % props.anexos.length
}

function next() {
  current.value = (current.value + 1) % props.anexos.length
}

function openLightbox(i: number) {
  lightboxIndex.value = i
}

function lightboxPrev() {
  if (lightboxIndex.value === null) return
  lightboxIndex.value = (lightboxIndex.value - 1 + props.anexos.length) % props.anexos.length
}

function lightboxNext() {
  if (lightboxIndex.value === null) return
  lightboxIndex.value = (lightboxIndex.value + 1) % props.anexos.length
}

function onFilesSelected(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length) return
  emit('upload', Array.from(input.files))
  input.value = ''
}
</script>

<style scoped>
.anexos-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

/* ── Carousel ─────────────────────────────── */
.carousel {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.carousel-main {
  position: relative;
  background: #0f172a;
  border-radius: 0.75rem;
  overflow: hidden;
  aspect-ratio: 4/3;
  display: flex;
  align-items: center;
  justify-content: center;
}

.img-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-in;
  position: relative;
}

.main-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.2s;
}

.img-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s;
}
.img-overlay svg { width: 2rem; height: 2rem; color: white; }

.img-wrapper:hover .img-overlay {
  opacity: 1;
  background: rgba(0,0,0,0.25);
}

.nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 2;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  background: rgba(255,255,255,0.9);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.25);
  transition: background 0.2s, transform 0.1s;
  backdrop-filter: blur(4px);
}
.nav-btn svg { width: 1rem; height: 1rem; color: #1e293b; }
.nav-btn:hover { background: white; transform: translateY(-50%) scale(1.08); }
.nav-prev { left: 0.6rem; }
.nav-next { right: 0.6rem; }

/* ── Info bar ─────────────────────────────── */
.info-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.25rem;
}
.file-name {
  flex: 1;
  font-size: 0.8rem;
  color: #374151;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.file-size {
  font-size: 0.75rem;
  color: #9ca3af;
  flex-shrink: 0;
}
.del-btn {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.6rem;
  background: #fee2e2;
  color: #dc2626;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
}
.del-btn:hover { background: #fecaca; }
.del-btn svg { width: 0.875rem; height: 0.875rem; }

/* ── Thumbnails ───────────────────────────── */
.thumbs {
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
  padding-bottom: 0.25rem;
  scrollbar-width: thin;
}
.thumb-btn {
  flex-shrink: 0;
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 0.5rem;
  overflow: hidden;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
  background: #f1f5f9;
  transition: border-color 0.15s, transform 0.15s;
}
.thumb-btn.active {
  border-color: #2563eb;
  transform: scale(1.05);
}
.thumb-btn:hover:not(.active) { border-color: #93c5fd; }
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* ── Dots ─────────────────────────────────── */
.dots {
  display: flex;
  justify-content: center;
  gap: 0.4rem;
  margin-top: 0.1rem;
}
.dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: #d1d5db;
  border: none;
  cursor: pointer;
  padding: 0;
  transition: background 0.2s, transform 0.2s;
}
.dot.active {
  background: #2563eb;
  transform: scale(1.3);
}

/* ── Upload zone ──────────────────────────── */
.hidden-input { display: none; }

.upload-btns-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.upload-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 2px dashed #d1d5db;
  border-radius: 0.75rem;
  background: #f9fafb;
  color: #6b7280;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.upload-btn svg { width: 1.25rem; height: 1.25rem; }
.upload-btn:hover:not(:disabled) {
  border-color: #2563eb;
  background: #eff6ff;
  color: #2563eb;
}
.upload-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.camera-btn:hover:not(:disabled) {
  border-color: #7c3aed;
  background: #f5f3ff;
  color: #7c3aed;
}

.upload-error {
  margin: 0;
  font-size: 0.78rem;
  color: #dc2626;
  text-align: center;
}

/* Spinner */
.spin { animation: spin 1s linear infinite; width: 1.25rem; height: 1.25rem; }
.spin-track { opacity: 0.25; }
.spin-path { opacity: 0.75; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Lightbox ─────────────────────────────── */
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.92);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 1rem;
}
.lb-img {
  max-width: min(90vw, 1200px);
  max-height: 85vh;
  object-fit: contain;
  border-radius: 0.5rem;
  cursor: default;
  box-shadow: 0 25px 50px rgba(0,0,0,0.5);
}
.lb-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: background 0.2s;
  backdrop-filter: blur(4px);
}
.lb-close:hover { background: rgba(255,255,255,0.3); }
.lb-close svg { width: 1.25rem; height: 1.25rem; }
.lb-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: background 0.2s;
  backdrop-filter: blur(4px);
}
.lb-nav:hover { background: rgba(255,255,255,0.3); }
.lb-nav svg { width: 1.25rem; height: 1.25rem; }
.lb-prev { left: 1rem; }
.lb-next { right: 1rem; }
.lb-caption {
  position: absolute;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255,255,255,0.75);
  font-size: 0.85rem;
  background: rgba(0,0,0,0.4);
  padding: 0.3rem 0.75rem;
  border-radius: 9999px;
  backdrop-filter: blur(4px);
  white-space: nowrap;
  max-width: 80vw;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Camera modal ─────────────────────────── */
.camera-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,0.85);
  display: flex; align-items: center; justify-content: center;
  padding: 1rem;
}
.camera-modal {
  background: #0f172a;
  border-radius: 1rem;
  width: 100%; max-width: 540px;
  display: flex; flex-direction: column;
  overflow: hidden;
  box-shadow: 0 25px 60px rgba(0,0,0,0.6);
}
.camera-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.9rem 1.25rem;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  color: white; font-weight: 600; font-size: 0.95rem;
}
.camera-close {
  background: none; border: none; cursor: pointer;
  color: rgba(255,255,255,0.6); display: flex;
  transition: color 0.2s;
}
.camera-close:hover { color: white; }
.camera-close svg { width: 1.25rem; height: 1.25rem; }
.camera-body {
  position: relative; background: #000;
  min-height: 280px; display: flex; align-items: center; justify-content: center;
}
.camera-video {
  width: 100%; max-height: 380px; object-fit: cover;
  display: block;
}
.camera-preview {
  width: 100%; max-height: 380px; object-fit: contain;
}
/* aim crosshair overlay */
.camera-body::after {
  content: '';
  position: absolute; inset: 0;
  border: 2px solid rgba(255,255,255,0.12);
  border-radius: 0;
  pointer-events: none;
}
.camera-error {
  color: #fca5a5; font-size: 0.85rem; text-align: center;
  padding: 1.5rem; margin: 0;
}
.camera-footer {
  display: flex; gap: 0.75rem; justify-content: center;
  padding: 1rem 1.25rem;
  border-top: 1px solid rgba(255,255,255,0.08);
}
.btn-capture {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.7rem 1.75rem;
  background: white; color: #0f172a;
  border: none; border-radius: 9999px;
  font-weight: 700; font-size: 0.95rem; cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 4px 14px rgba(255,255,255,0.2);
}
.btn-capture svg { width: 1.1rem; height: 1.1rem; }
.btn-capture:hover:not(:disabled) { background: #e2e8f0; transform: scale(1.04); }
.btn-capture:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-retake {
  padding: 0.65rem 1.25rem;
  background: rgba(255,255,255,0.1); color: white;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 9999px; cursor: pointer; font-size: 0.875rem;
  transition: background 0.2s;
}
.btn-retake:hover { background: rgba(255,255,255,0.2); }
.btn-use-photo {
  padding: 0.65rem 1.5rem;
  background: #2563eb; color: white;
  border: none; border-radius: 9999px;
  font-weight: 600; font-size: 0.875rem; cursor: pointer;
  transition: background 0.2s;
  box-shadow: 0 4px 12px rgba(37,99,235,0.4);
}
.btn-use-photo:hover { background: #1d4ed8; }
</style>
