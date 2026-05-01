<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-header">
        <h2>Importar Estoque</h2>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Type selector -->
      <div class="type-tabs">
        <button @click="importType = 'csv'" :class="['type-tab', { active: importType === 'csv' }]">
          CSV / Planilha
        </button>
        <button @click="importType = 'nfe'" :class="['type-tab', { active: importType === 'nfe' }]">
          NF-e XML
        </button>
      </div>

      <div class="modal-body">
        <!-- CSV info -->
        <template v-if="importType === 'csv'">
          <div class="info-box">
            <p>O arquivo CSV deve ter cabeçalhos em português ou inglês. Colunas aceitas:</p>
            <code>nome, categoria, tamanho, cor, unidade, codigo_barras, custo, preco_venda, moeda, estoque_minimo, estoque_maximo, localizacao, estoque_inicial</code>
            <button @click="downloadTemplate" class="download-link">
              Baixar template CSV
            </button>
          </div>
        </template>

        <!-- NF-e config panel -->
        <template v-if="importType === 'nfe'">
          <div class="info-box">
            <p>Campos extraídos: nome (xProd), código EAN, unidade, quantidade, valor unitário.</p>
          </div>

          <div class="config-panel">
            <h4 class="config-title">Configurações da importação</h4>

            <!-- Category -->
            <div class="config-row">
              <label class="config-label">Categoria dos produtos</label>
              <input
                v-model="nfeConfig.category"
                type="text"
                class="config-input"
                placeholder="Ex: Calçados, Camisetas, Acessórios..."
                list="category-suggestions"
              />
              <datalist id="category-suggestions">
                <option value="Calçados" />
                <option value="Camisetas" />
                <option value="Calças" />
                <option value="Vestidos" />
                <option value="Acessórios" />
                <option value="Bolsas" />
                <option value="Bermudas" />
                <option value="Jaquetas" />
              </datalist>
            </div>

            <!-- Currency -->
            <div class="config-row">
              <label class="config-label">Moeda do XML</label>
              <select v-model="nfeConfig.currency" class="config-select">
                <option value="BRL">R$ — Real Brasileiro</option>
                <option value="USD">U$ — Dólar Americano</option>
                <option value="PYG">G$ — Guarani Paraguaio</option>
                <option value="EUR">€ — Euro</option>
              </select>
            </div>

            <!-- Split info (always active) -->
            <div class="split-preview">
              <span class="preview-label">Separação automática:</span>
              <span class="preview-text">
                <strong>xProd:</strong> "TENIS ADIDAS PRETO VERNIZ"
                &rarr;
                <strong>Nome:</strong> "Tenis Adidas" &nbsp;·&nbsp;
                <strong>Cor:</strong> "Preto Verniz"
              </span>
            </div>
          </div>
        </template>

        <!-- File drop zone -->
        <div
          class="drop-zone"
          :class="{ dragover: isDragging, 'has-file': selectedFile }"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="onDrop"
          @click="fileInputRef?.click()"
        >
          <input
            ref="fileInputRef"
            type="file"
            :accept="importType === 'csv' ? '.csv,.txt' : '.xml'"
            class="file-input-hidden"
            @change="onFileChange"
          />
          <template v-if="!selectedFile">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="32" height="32" class="drop-icon">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p>Arraste o arquivo aqui ou <span class="click-link">clique para selecionar</span></p>
            <p class="file-hint">{{ importType === 'csv' ? 'Arquivo .csv ou .txt' : 'Arquivo .xml da NF-e' }}</p>
          </template>
          <template v-else>
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="28" height="28" class="file-icon">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p class="file-name">{{ selectedFile.name }}</p>
            <button @click.stop="selectedFile = null; result = null" class="remove-file">× remover</button>
          </template>
        </div>

        <!-- Result -->
        <div v-if="result" class="result-box" :class="{ success: result.created > 0, warning: result.skipped > 0 }">
          <p><strong>{{ result.created }}</strong> iten{{ result.created !== 1 ? 's' : '' }} criado{{ result.created !== 1 ? 's' : '' }}</p>
          <p v-if="result.skipped > 0" class="skipped">{{ result.skipped }} ignorado{{ result.skipped !== 1 ? 's' : '' }}</p>
          <ul v-if="result.errors.length > 0" class="error-list">
            <li v-for="e in result.errors" :key="e">{{ e }}</li>
          </ul>
        </div>

        <div v-if="uploading" class="uploading">
          <div class="spinner"></div>
          <p>Importando...</p>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="emit('close')" class="btn btn-secondary">{{ result ? 'Fechar' : 'Cancelar' }}</button>
        <button
          v-if="!result"
          @click="handleImport"
          class="btn btn-primary"
          :disabled="!selectedFile || uploading"
        >
          {{ uploading ? 'Importando...' : 'Importar' }}
        </button>
        <button v-if="result && result.created > 0" @click="emit('imported'); emit('close')" class="btn btn-primary">
          Ver itens importados
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { inventoryAPI } from '@/services/api'

const emit = defineEmits<{
  (e: 'imported'): void
  (e: 'close'): void
}>()

const importType = ref<'csv' | 'nfe'>('csv')
const selectedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement>()
const isDragging = ref(false)
const uploading = ref(false)
const result = ref<{ created: number; skipped: number; errors: string[] } | null>(null)

const nfeConfig = reactive({
  category: '',
  currency: 'BRL',
})

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) selectedFile.value = input.files[0]
  result.value = null
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) { selectedFile.value = file; result.value = null }
}

async function handleImport() {
  if (!selectedFile.value) return
  uploading.value = true
  result.value = null
  try {
    if (importType.value === 'csv') {
      result.value = await inventoryAPI.importCsv(selectedFile.value)
    } else {
      result.value = await inventoryAPI.importNfe(selectedFile.value, {
        category: nfeConfig.category || undefined,
        currency: nfeConfig.currency,
      })
    }
  } catch (e: any) {
    result.value = { created: 0, skipped: 0, errors: [e.response?.data?.detail || 'Erro na importação'] }
  } finally {
    uploading.value = false
  }
}

function downloadTemplate() {
  const headers = 'nome,categoria,tamanho,cor,unidade,codigo_barras,custo,preco_venda,moeda,estoque_minimo,estoque_maximo,localizacao,estoque_inicial'
  const example = 'Camiseta Polo Azul,Camisetas,M,Azul,un,7891234567890,25.00,45.00,BRL,5,50,A-01,10'
  const blob = new Blob([headers + '\n' + example], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'template_estoque.csv'
  a.click()
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 500; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal-container { background: white; border-radius: 12px; width: 100%; max-width: 500px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; }
.modal-header h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; }
.type-tabs { display: flex; border-bottom: 1px solid #e5e7eb; }
.type-tab { flex: 1; padding: 0.75rem; background: none; border: none; cursor: pointer; font-size: 0.875rem; color: #6b7280; border-bottom: 2px solid transparent; }
.type-tab.active { color: #3b82f6; border-bottom-color: #3b82f6; font-weight: 600; }
.modal-body { flex: 1; overflow-y: auto; padding: 1.25rem; display: flex; flex-direction: column; gap: 1rem; }
.info-box { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 0.75rem 1rem; font-size: 0.8rem; color: #1e40af; }
.info-box p { margin: 0 0 0.5rem; }
.info-box p:last-child { margin-bottom: 0; }
.info-box code { display: block; background: white; border-radius: 4px; padding: 0.4rem 0.6rem; font-size: 0.7rem; word-break: break-all; margin-top: 0.25rem; }
.download-link { margin-top: 0.5rem; background: none; border: none; color: #3b82f6; cursor: pointer; font-size: 0.8rem; text-decoration: underline; padding: 0; }

/* Config panel */
.config-panel { border: 1px solid #e5e7eb; border-radius: 10px; padding: 1rem; display: flex; flex-direction: column; gap: 0.875rem; }
.config-title { margin: 0 0 0.25rem; font-size: 0.8rem; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.04em; }
.config-row { display: flex; flex-direction: column; gap: 0.3rem; }
.config-row-check { flex-direction: row; align-items: center; justify-content: space-between; gap: 1rem; }
.config-label { font-size: 0.825rem; font-weight: 500; color: #374151; }
.config-hint { display: block; font-size: 0.72rem; color: #9ca3af; font-weight: 400; margin-top: 0.1rem; }
.config-input { border: 1px solid #d1d5db; border-radius: 6px; padding: 0.45rem 0.65rem; font-size: 0.85rem; outline: none; }
.config-input:focus { border-color: #3b82f6; }
.config-select { border: 1px solid #d1d5db; border-radius: 6px; padding: 0.45rem 0.65rem; font-size: 0.85rem; background: white; outline: none; cursor: pointer; }
.config-select:focus { border-color: #3b82f6; }

/* Toggle switch */
.toggle { position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-track {
  position: absolute; inset: 0; background: #d1d5db; border-radius: 22px;
  transition: background 0.2s; cursor: pointer;
}
.toggle-track::before {
  content: ''; position: absolute; width: 16px; height: 16px;
  left: 3px; top: 3px; background: white; border-radius: 50%;
  transition: transform 0.2s;
}
.toggle input:checked + .toggle-track { background: #3b82f6; }
.toggle input:checked + .toggle-track::before { transform: translateX(18px); }

/* Split preview */
.split-preview { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 0.5rem 0.75rem; font-size: 0.75rem; color: #6b7280; }
.preview-label { font-weight: 600; color: #374151; margin-right: 0.35rem; }
.preview-text { line-height: 1.6; }

.drop-zone {
  border: 2px dashed #d1d5db; border-radius: 10px; padding: 2rem 1.5rem;
  display: flex; flex-direction: column; align-items: center; gap: 0.5rem;
  cursor: pointer; transition: all 0.15s; text-align: center;
}
.drop-zone:hover, .drop-zone.dragover { border-color: #3b82f6; background: #eff6ff; }
.drop-zone.has-file { border-color: #10b981; background: #f0fdf4; }
.drop-icon { color: #9ca3af; }
.file-icon { color: #10b981; }
.drop-zone p { margin: 0; font-size: 0.875rem; color: #374151; }
.file-hint { font-size: 0.75rem; color: #9ca3af; }
.click-link { color: #3b82f6; text-decoration: underline; }
.file-input-hidden { display: none; }
.file-name { font-weight: 600; color: #059669; }
.remove-file { background: none; border: none; color: #ef4444; cursor: pointer; font-size: 0.8rem; }
.result-box { border-radius: 8px; padding: 0.75rem 1rem; font-size: 0.875rem; }
.result-box.success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d; }
.result-box.warning { background: #fefce8; border: 1px solid #fde047; color: #854d0e; }
.result-box p { margin: 0 0 0.25rem; }
.skipped { color: #d97706; }
.error-list { margin: 0.5rem 0 0; padding-left: 1.25rem; font-size: 0.75rem; color: #dc2626; }
.uploading { display: flex; align-items: center; gap: 0.75rem; justify-content: center; padding: 1rem; color: #6b7280; }
.spinner { width: 20px; height: 20px; border: 2px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; padding: 1rem 1.25rem; border-top: 1px solid #e5e7eb; }
.btn { padding: 0.5rem 1.25rem; border-radius: 6px; font-size: 0.875rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
</style>
