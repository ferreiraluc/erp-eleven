<template>
  <div class="lt-overlay" @click.self="emit('close')">
    <div class="lt-modal">
      <div class="lt-header">
        <div class="lt-header-left">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18" class="lt-header-icon">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <h3>Modelos de Etiqueta Treinados</h3>
        </div>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Brand filter tabs -->
      <div class="lt-brand-bar" v-if="brands.length > 0">
        <button
          @click="activeBrand = null"
          :class="['brand-tab', { active: activeBrand === null }]"
        >
          Todas
          <span class="brand-count">{{ templates.length }}</span>
        </button>
        <button
          v-for="b in brands"
          :key="b.brand"
          @click="activeBrand = b.brand"
          :class="['brand-tab', { active: activeBrand === b.brand }]"
        >
          {{ b.brand }}
          <span class="brand-count">{{ b.count }}</span>
        </button>
      </div>

      <div class="lt-body">
        <!-- Loading -->
        <div v-if="loading" class="lt-loading">
          <div class="lt-spinner"></div>
          <p>Carregando modelos...</p>
        </div>

        <!-- Empty -->
        <div v-else-if="filteredTemplates.length === 0" class="lt-empty">
          <svg fill="none" viewBox="0 0 24 24" stroke="#9ca3af" width="40" height="40">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <p v-if="activeBrand">Nenhum modelo treinado para <strong>{{ activeBrand }}</strong>.</p>
          <p v-else>Nenhum modelo treinado ainda.</p>
          <p class="lt-empty-hint">Use "Treinar IA" no leitor de etiquetas para salvar exemplos.</p>
        </div>

        <!-- Templates grid -->
        <div v-else class="lt-grid">
          <div
            v-for="tpl in filteredTemplates"
            :key="tpl.id"
            class="lt-card"
            :class="{ 'lt-card-deleting': deletingId === tpl.id }"
          >
            <!-- Thumbnail -->
            <div class="lt-thumb-wrap">
              <img
                v-if="tpl.sample_image"
                :src="ensureDataUrl(tpl.sample_image)"
                class="lt-thumb"
                alt="etiqueta"
                @click="openPreview(tpl)"
              />
              <div v-else class="lt-thumb-placeholder">
                <svg fill="none" viewBox="0 0 24 24" stroke="#d1d5db" width="24" height="24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            </div>

            <!-- Content -->
            <div class="lt-card-content">
              <div class="lt-card-top">
                <span class="lt-brand-pill">{{ tpl.brand }}</span>
                <span class="lt-date">{{ formatDate(tpl.created_at) }}</span>
              </div>

              <div class="lt-fields">
                <span v-if="tpl.parsed_name" class="lt-field">
                  <span class="lt-field-label">Nome</span>
                  <span class="lt-field-val">{{ tpl.parsed_name }}</span>
                </span>
                <span v-if="tpl.parsed_size" class="lt-field">
                  <span class="lt-field-label">Tam.</span>
                  <span class="lt-field-val">{{ tpl.parsed_size }}</span>
                </span>
                <span v-if="tpl.parsed_color" class="lt-field">
                  <span class="lt-field-label">Cor</span>
                  <span class="lt-field-val">{{ tpl.parsed_color }}</span>
                </span>
                <span v-if="tpl.parsed_barcode" class="lt-field">
                  <span class="lt-field-label">Barcode</span>
                  <span class="lt-field-val lt-mono">{{ tpl.parsed_barcode }}</span>
                </span>
                <span v-if="tpl.parsed_price" class="lt-field">
                  <span class="lt-field-label">Preço</span>
                  <span class="lt-field-val">{{ tpl.parsed_price }}{{ tpl.parsed_currency ? ' ' + tpl.parsed_currency : '' }}</span>
                </span>
              </div>

              <p v-if="tpl.notes" class="lt-notes">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="11" height="11">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                </svg>
                {{ tpl.notes }}
              </p>
            </div>

            <!-- Delete button -->
            <button
              class="lt-delete-btn"
              @click="confirmDelete(tpl)"
              :disabled="deletingId === tpl.id"
              title="Excluir modelo"
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="lt-footer">
        <span class="lt-footer-hint">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Mais modelos por marca = maior precisão na leitura
        </span>
        <button @click="emit('close')" class="btn-close-footer">Fechar</button>
      </div>
    </div>
  </div>

  <!-- Image preview lightbox -->
  <div v-if="previewImage" class="lt-lightbox" @click="previewImage = null">
    <img :src="previewImage" class="lt-lightbox-img" alt="etiqueta" />
    <button class="lt-lightbox-close" @click="previewImage = null">
      <svg fill="none" viewBox="0 0 24 24" stroke="white" width="24" height="24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </div>

  <!-- Delete confirmation dialog -->
  <div v-if="deleteTarget" class="lt-confirm-overlay" @click.self="deleteTarget = null">
    <div class="lt-confirm-box">
      <p>Excluir modelo de <strong>{{ deleteTarget.brand }}</strong>?</p>
      <p class="lt-confirm-sub">Esta ação não pode ser desfeita. A IA perderá este exemplo de treinamento.</p>
      <div class="lt-confirm-actions">
        <button @click="deleteTarget = null" class="btn-ghost-sm">Cancelar</button>
        <button @click="doDelete" class="btn-danger-sm" :disabled="deletingId !== null">
          {{ deletingId ? 'Excluindo...' : 'Excluir' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ocrAPI } from '@/services/api'

interface LabelTemplate {
  id: string
  brand: string
  notes?: string
  sample_image?: string
  parsed_name?: string
  parsed_size?: string
  parsed_color?: string
  parsed_barcode?: string
  parsed_price?: string
  parsed_currency?: string
  created_at: string
}

const emit = defineEmits<{
  (e: 'close'): void
}>()

const loading = ref(true)
const templates = ref<LabelTemplate[]>([])
const brands = ref<Array<{ brand: string; count: number }>>([])
const activeBrand = ref<string | null>(null)
const deletingId = ref<string | null>(null)
const deleteTarget = ref<LabelTemplate | null>(null)
const previewImage = ref<string | null>(null)

const filteredTemplates = computed(() =>
  activeBrand.value
    ? templates.value.filter(t => t.brand === activeBrand.value)
    : templates.value
)

function ensureDataUrl(img: string): string {
  if (!img) return ''
  if (img.startsWith('data:')) return img
  return `data:image/jpeg;base64,${img}`
}

function formatDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function openPreview(tpl: LabelTemplate) {
  if (tpl.sample_image) {
    previewImage.value = ensureDataUrl(tpl.sample_image)
  }
}

function confirmDelete(tpl: LabelTemplate) {
  deleteTarget.value = tpl
}

async function doDelete() {
  if (!deleteTarget.value) return
  deletingId.value = deleteTarget.value.id
  try {
    await ocrAPI.deleteTemplate(deleteTarget.value.id)
    templates.value = templates.value.filter(t => t.id !== deleteTarget.value!.id)
    // Recompute brands
    const counts: Record<string, number> = {}
    templates.value.forEach(t => { counts[t.brand] = (counts[t.brand] ?? 0) + 1 })
    brands.value = Object.entries(counts).map(([brand, count]) => ({ brand, count }))
    // If active brand no longer has items, reset filter
    if (activeBrand.value && !brands.value.find(b => b.brand === activeBrand.value)) {
      activeBrand.value = null
    }
    deleteTarget.value = null
  } catch (e) {
    console.error('Delete failed', e)
  } finally {
    deletingId.value = null
  }
}

onMounted(async () => {
  try {
    const [tpls, brnds] = await Promise.all([
      ocrAPI.getTemplates(),
      ocrAPI.getBrands(),
    ])
    templates.value = tpls
    brands.value = brnds
  } catch (e) {
    console.error('Failed to load templates', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* ── Overlay & Modal ── */
.lt-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
  padding: 1rem;
}

.lt-modal {
  background: #fff;
  border-radius: 0.75rem;
  width: 100%;
  max-width: 680px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

/* ── Header ── */
.lt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1rem;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.lt-header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.lt-header-icon {
  color: #8b5cf6;
}

.lt-header h3 {
  font-size: 0.9rem;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #64748b;
  padding: 0.25rem;
  border-radius: 0.25rem;
  display: flex;
  align-items: center;
  transition: color 0.15s;
}
.close-btn:hover { color: #1e293b; }

/* ── Brand filter tabs ── */
.lt-brand-bar {
  display: flex;
  gap: 0.25rem;
  padding: 0.6rem 1rem;
  border-bottom: 1px solid #f1f5f9;
  overflow-x: auto;
  flex-shrink: 0;
  scrollbar-width: none;
}
.lt-brand-bar::-webkit-scrollbar { display: none; }

.brand-tab {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 0.75rem;
  color: #64748b;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.brand-tab:hover { border-color: #8b5cf6; color: #7c3aed; }
.brand-tab.active { background: #8b5cf6; color: #fff; border-color: #8b5cf6; }

.brand-count {
  background: rgba(255,255,255,0.25);
  border-radius: 999px;
  padding: 0 0.35rem;
  font-size: 0.65rem;
  font-weight: 600;
  line-height: 1.6;
}
.brand-tab:not(.active) .brand-count {
  background: #f1f5f9;
  color: #94a3b8;
}

/* ── Body ── */
.lt-body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

/* ── Loading ── */
.lt-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2.5rem;
  color: #94a3b8;
  font-size: 0.8rem;
}

.lt-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e2e8f0;
  border-top-color: #8b5cf6;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Empty ── */
.lt-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2.5rem 1rem;
  text-align: center;
  color: #6b7280;
  font-size: 0.85rem;
}

.lt-empty-hint {
  font-size: 0.75rem;
  color: #9ca3af;
  margin-top: 0.25rem;
}

/* ── Grid ── */
.lt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}

/* ── Card ── */
.lt-card {
  display: flex;
  gap: 0.75rem;
  background: #fafafa;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 0.75rem;
  position: relative;
  transition: box-shadow 0.15s, opacity 0.2s;
}
.lt-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.lt-card-deleting { opacity: 0.4; pointer-events: none; }

/* ── Thumbnail ── */
.lt-thumb-wrap {
  flex-shrink: 0;
  width: 62px;
  height: 62px;
  border-radius: 0.375rem;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
}

.lt-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s;
}
.lt-thumb:hover { transform: scale(1.05); }

.lt-thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ── Card content ── */
.lt-card-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.lt-card-top {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.lt-brand-pill {
  font-size: 0.7rem;
  font-weight: 600;
  background: #ede9fe;
  color: #7c3aed;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  letter-spacing: 0.01em;
}

.lt-date {
  font-size: 0.65rem;
  color: #94a3b8;
  margin-left: auto;
}

/* ── Fields ── */
.lt-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.lt-field {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.7rem;
  background: #f1f5f9;
  border-radius: 0.25rem;
  padding: 0.1rem 0.35rem;
}

.lt-field-label {
  color: #94a3b8;
  font-weight: 500;
}

.lt-field-val {
  color: #334155;
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lt-mono {
  font-family: 'Courier New', monospace;
  font-size: 0.65rem;
}

/* ── Notes ── */
.lt-notes {
  display: flex;
  align-items: flex-start;
  gap: 0.3rem;
  font-size: 0.68rem;
  color: #6b7280;
  font-style: italic;
  margin: 0;
  line-height: 1.3;
}

/* ── Delete button ── */
.lt-delete-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: none;
  border: none;
  cursor: pointer;
  color: #cbd5e1;
  padding: 0.25rem;
  border-radius: 0.25rem;
  display: flex;
  align-items: center;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.lt-card:hover .lt-delete-btn { opacity: 1; }
.lt-delete-btn:hover { color: #ef4444; }

/* ── Footer ── */
.lt-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-top: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.lt-footer-hint {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.72rem;
  color: #9ca3af;
}

.btn-close-footer {
  padding: 0.4rem 0.9rem;
  border-radius: 0.375rem;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 0.8rem;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-close-footer:hover { background: #f8fafc; color: #1e293b; }

/* ── Lightbox ── */
.lt-lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;
  cursor: zoom-out;
}

.lt-lightbox-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 0.5rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.lt-lightbox-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: rgba(255,255,255,0.15);
  border: none;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
}
.lt-lightbox-close:hover { background: rgba(255,255,255,0.25); }

/* ── Delete confirmation ── */
.lt-confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1300;
  padding: 1rem;
}

.lt-confirm-box {
  background: #fff;
  border-radius: 0.625rem;
  padding: 1.25rem 1.5rem;
  max-width: 340px;
  width: 100%;
  box-shadow: 0 10px 30px rgba(0,0,0,0.15);
}

.lt-confirm-box p {
  font-size: 0.875rem;
  color: #1e293b;
  margin: 0 0 0.4rem;
}

.lt-confirm-sub {
  font-size: 0.78rem !important;
  color: #64748b !important;
  margin-bottom: 1rem !important;
}

.lt-confirm-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.btn-ghost-sm {
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 0.8rem;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-ghost-sm:hover { background: #f8fafc; }

.btn-danger-sm {
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  border: none;
  background: #ef4444;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-danger-sm:hover { background: #dc2626; }
.btn-danger-sm:disabled { opacity: 0.6; cursor: not-allowed; }

/* ── Mobile ── */
@media (max-width: 480px) {
  .lt-modal { max-height: 95vh; }
  .lt-grid { grid-template-columns: 1fr; }
  .lt-delete-btn { opacity: 1; }
}
</style>
