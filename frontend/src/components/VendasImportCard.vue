<template>
  <div class="vendas-import-card">
    <div class="card-header">
      <div class="header-left">
        <h3 class="card-title">{{ uiText(`Importar Vendas`) }}</h3>
        <p class="card-subtitle">{{ uiText(`Planilha VENDASgeral.xlsx`) }}</p>
      </div>
      <div class="header-right">
        <button @click="openImportModal" class="import-button erp-button erp-button--primary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
          </svg> {{ uiText(`Importar`) }} </button>
      </div>
    </div>

    <div class="card-content">
      <!-- Status de importação -->
      <div class="import-stats">
        <div class="stat-item">
          <div class="stat-icon success">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <div class="stat-details">
            <div class="stat-number">{{ lastImportStats.imported || 0 }}</div>
            <div class="stat-label">{{ uiText(`Importadas`) }}</div>
          </div>
        </div>
        
        <div class="stat-item">
          <div class="stat-icon warning">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <div class="stat-details">
            <div class="stat-number">{{ lastImportStats.skipped || 0 }}</div>
            <div class="stat-label">{{ uiText(`Duplicadas`) }}</div>
          </div>
        </div>

        <div class="stat-item">
          <div class="stat-icon error">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <div class="stat-details">
            <div class="stat-number">{{ lastImportStats.errors || 0 }}</div>
            <div class="stat-label">{{ uiText(`Erros`) }}</div>
          </div>
        </div>
      </div>

      <!-- Última importação -->
      <div v-if="lastImportDate" class="last-import">
        <div class="last-import-info">
          <svg class="calendar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
          <span class="last-import-text"> {{ uiText(`Última importação:`) }} {{ formatDate(lastImportDate) }}
          </span>
        </div>
      </div>
    </div>

    <!-- Modal de Importação -->
    <div v-if="showImportModal" class="import-modal-overlay erp-dialog-backdrop" @click="closeImportModal">
      <div v-erp-dialog class="import-modal erp-dialog erp-dialog--lg" @click.stop>
        <div class="modal-header erp-dialog__header">
          <h2>{{ uiText(`Importar Vendas - VENDASgeral.xlsx`) }}</h2>
          <button data-dialog-close :aria-label="uiText('Fechar')" @click="closeImportModal" class="close-button erp-button erp-button--secondary erp-button--icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="modal-content erp-dialog__body">
          <!-- Info sobre o formato -->
          <div class="custom-format-info">
            <div class="info-box">
              <h4>{{ uiText(`📊 Dados Semanais - VENDASgeral.xlsx`) }}</h4>
              <p>{{ uiText(`Sistema otimizado para extrair totais semanais por vendedor e moeda:`) }}</p>
              
              <div class="mapping-section">
                <h5>{{ uiText(`👥 Vendedores (Linha 2):`) }}</h5>
                <ul class="mapping-list">
                  <li><strong>{{ uiText(`Coluna D:`) }}</strong> Junior</li>
                  <li><strong>{{ uiText(`Coluna E:`) }}</strong> Denis</li>
                  <li><strong>{{ uiText(`Coluna F:`) }}</strong> Sol</li>
                  <li><strong>{{ uiText(`Coluna G:`) }}</strong> Wiss</li>
                  <li><strong>{{ uiText(`Coluna H:`) }}</strong> Lucas</li>
                </ul>
              </div>
              
              <div class="mapping-section">
                <h5>{{ uiText(`💰 Moedas (Coluna C):`) }}</h5>
                <ul class="mapping-list">
                  <li><strong>{{ uiText(`Linha 3:`) }}</strong> {{ uiText(`G$ (Guaranis)`) }}</li>
                  <li><strong>{{ uiText(`Linha 4:`) }}</strong> {{ uiText(`EUR (Euros)`) }}</li>
                  <li><strong>{{ uiText(`Linha 5:`) }}</strong> {{ uiText(`R$ (Reais)`) }}</li>
                  <li><strong>{{ uiText(`Linha 6:`) }}</strong> {{ uiText(`U$ (Dólares)`) }}</li>
                </ul>
              </div>
              
              <p class="note">{{ uiText(`📈 O sistema extrairá os valores das interseções (ex: D3 = vendas do Junior em G$)`) }}</p>
            </div>
          </div>

          <!-- Conteúdo Upload -->
          <div class="tab-content">
            <div class="upload-area" @drop="handleDrop" @dragover.prevent @dragenter.prevent>
              <input 
                ref="fileInput"
                type="file" 
                accept=".xlsx,.xls" 
                @change="handleFileSelect"
                style="display: none;"
              >
              
              <div v-if="!selectedFile" class="upload-placeholder" @click="fileInput?.click()">
                <div class="upload-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                  </svg>
                </div>
                <div class="upload-text">
                  <p><strong>{{ uiText(`Clique para selecionar`) }}</strong> {{ uiText(`sua planilha VENDASgeral.xlsx`) }}</p>
                  <p class="upload-hint">{{ uiText(`Formato personalizado com mapeamento de células`) }}</p>
                </div>
              </div>

              <div v-else class="file-selected">
                <div class="file-info">
                  <div class="file-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                  </div>
                  <div class="file-details">
                    <div class="file-name">{{ selectedFile.name }}</div>
                    <div class="file-size">{{ formatFileSize(selectedFile.size) }}</div>
                  </div>
                </div>
                <button @click="clearFile" class="remove-file-btn erp-button erp-button--danger erp-button--icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>

            <div v-if="selectedFile" class="form-actions">
              <button @click="previewUpload" :disabled="loading" class="btn btn-secondary erp-button erp-button--secondary">
                {{ loading ? uiText(`Carregando...`) : uiText(`Preview`) }}
              </button>
            </div>
          </div>

          <!-- Preview dos Dados -->
          <div v-if="previewData" class="preview-section">
            <div class="preview-header">
              <h3>{{ uiText(`Preview da Importação`) }}</h3>
              <div class="preview-stats">
                <span class="stat success">{{ previewData.valid_rows }} {{ uiText(`válidas`) }}</span>
                <span class="stat error" v-if="previewData.errors.length > 0">
                  {{ previewData.errors.length }} {{ uiText(`erros`) }} </span>
              </div>
            </div>

            <!-- Erros -->
            <div v-if="previewData.errors.length > 0" class="preview-errors">
              <h4>{{ uiText(`Erros Encontrados:`) }}</h4>
              <ul class="error-list">
                <li v-for="error in previewData.errors.slice(0, 5)" :key="error" class="error-item">
                  {{ error }}
                </li>
                <li v-if="previewData.errors.length > 5" class="error-more"> {{ uiText(`... e mais`) }} {{ previewData.errors.length - 5 }} {{ uiText(`erros`) }} </li>
              </ul>
            </div>

            <!-- Dados válidos -->
            <div v-if="previewData.preview_data.length > 0" class="preview-table">
              <h4>{{ uiText(`Primeiras`) }} {{ previewData.preview_data.length }} {{ uiText(`vendas válidas:`) }}</h4>
              <table class="data-table">
                <thead>
                  <tr>
                    <th>{{ uiText(`Vendedor`) }}</th>
                    <th>{{ uiText(`Data`) }}</th>
                    <th>{{ uiText(`Valor`) }}</th>
                    <th>{{ uiText(`Moeda`) }}</th>
                    <th>{{ uiText(`Pagamento`) }}</th>
                    <th>{{ uiText(`Produto`) }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="sale in previewData.preview_data" :key="sale.row_number">
                    <td>{{ sale.vendedor_nome }}</td>
                    <td>{{ sale.data_venda }}</td>
                    <td>{{ uiNumber(sale.valor_bruto) }}</td>
                    <td>{{ sale.moeda }}</td>
                    <td>{{ sale.metodo_pagamento }}</td>
                    <td>{{ sale.descricao_produto || '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="preview-actions">
              <button @click="clearPreview" class="btn btn-secondary erp-button erp-button--secondary"> {{ uiText(`Cancelar`) }} </button>
              <button 
                @click="confirmImport" 
                :disabled="loading || previewData.valid_rows === 0"
                class="btn btn-primary erp-button erp-button--primary"
              >
                {{ loading ? uiText(`Importando...`) : uiText(`Importar {0} vendas`,{0:previewData.valid_rows}) }}
              </button>
            </div>
          </div>

          <!-- Resultado da Importação -->
          <div v-if="importResult" class="import-result">
            <div class="result-header">
              <div class="result-icon" :class="{ 'success': importResult.success, 'error': !importResult.success }">
                <svg v-if="importResult.success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="15" y1="9" x2="9" y2="15"/>
                  <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
              </div>
              <h3>{{ importResult.success ? uiText(`Importação Concluída!`) : uiText(`Erro na Importação`) }}</h3>
            </div>

            <div class="result-stats">
              <div class="result-stat success">
                <strong>{{ importResult.imported_count }}</strong> {{ uiText(`vendas importadas`) }} </div>
              <div v-if="importResult.skipped_count > 0" class="result-stat warning">
                <strong>{{ importResult.skipped_count }}</strong> {{ uiText(`vendas duplicadas (ignoradas)`) }} </div>
              <div v-if="importResult.total_errors > 0" class="result-stat error">
                <strong>{{ importResult.total_errors }}</strong> {{ uiText(`erros encontrados`) }} </div>
            </div>

            <div class="result-actions">
              <button @click="closeImportModal" class="btn btn-primary erp-button erp-button--primary"> {{ uiText(`Fechar`) }} </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import { uiText, uiLocale, uiNumber } from '@/i18n/uiText'
import { ref, onMounted } from 'vue'
import { excelImportAPI, type ImportPreviewResponse, type ImportResultResponse } from '@/services/api'

// Estado reativo
const showImportModal = ref(false)
const loading = ref(false)

// Estado do arquivo selecionado

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)

// Dados
const previewData = ref<ImportPreviewResponse | null>(null)
const importResult = ref<ImportResultResponse | null>(null)
const lastImportStats = ref({
  imported: 0,
  skipped: 0,
  errors: 0
})
const lastImportDate = ref<string | null>(null)

// Métodos
const openImportModal = () => {
  showImportModal.value = true
  clearPreview()
}

const closeImportModal = () => {
  showImportModal.value = false
  clearPreview()
  clearFile()
}

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    selectedFile.value = target.files[0]
  }
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    selectedFile.value = event.dataTransfer.files[0]
  }
}

const clearFile = () => {
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

const clearPreview = () => {
  previewData.value = null
  importResult.value = null
}


const previewUpload = async () => {
  if (!selectedFile.value) {
    alert(uiText(`Selecione um arquivo Excel`))
    return
  }

  try {
    loading.value = true
    const result = await excelImportAPI.previewUpload(selectedFile.value)
    previewData.value = result
  } catch (error: any) {
    console.error('Erro no preview upload:', error)
    alert(uiText(`Erro ao fazer preview: {0}`,{0:error.response?.data?.detail || error.message}))
  } finally {
    loading.value = false
  }
}

const confirmImport = async () => {
  if (!previewData.value) return

  try {
    loading.value = true
    
    const result = await excelImportAPI.importUpload(selectedFile.value!)
    
    importResult.value = result
    
    // Atualizar estatísticas
    lastImportStats.value = {
      imported: result.imported_count,
      skipped: result.skipped_count,
      errors: result.total_errors
    }
    lastImportDate.value = new Date().toISOString()
    
    // Limpar preview
    previewData.value = null
    
  } catch (error: any) {
    console.error('Erro na importação:', error)
    alert(uiText(`Erro na importação: {0}`,{0:error.response?.data?.detail || error.message}))
  } finally {
    loading.value = false
  }
}

const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleString(uiLocale(), {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k,i)).toLocaleString(uiLocale(),{maximumFractionDigits:2}) + ' ' + sizes[i]
}

// Lifecycle
onMounted(() => {
  // Carregar estatísticas do localStorage se existirem
  const savedStats = localStorage.getItem('last_import_stats')
  if (savedStats) {
    lastImportStats.value = JSON.parse(savedStats)
  }
  
  const savedDate = localStorage.getItem('last_import_date')
  if (savedDate) {
    lastImportDate.value = savedDate
  }
})
</script>

<style scoped>
.vendas-import-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 1.5rem 1rem;
  border-bottom: 1px solid #f3f4f6;
}

.header-left {
  flex: 1;
}

.card-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 0.25rem;
}

.card-subtitle {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
}

.import-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: #1f2937;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.import-button:hover {
  background: #374151;
}

.import-button svg {
  width: 1rem;
  height: 1rem;
}

.card-content {
  padding: 1rem 1.5rem 1.5rem;
}

/* Import Stats */
.import-stats {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 8px;
}

.stat-icon {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon svg {
  width: 1.25rem;
  height: 1.25rem;
}

.stat-icon.success {
  background: #dcfce7;
  color: #16a34a;
}

.stat-icon.warning {
  background: #fef3c7;
  color: #d97706;
}

.stat-icon.error {
  background: #fee2e2;
  color: #dc2626;
}

.stat-details {
  min-width: 0;
}

.stat-number {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1f2937;
  line-height: 1;
}

.stat-label {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
}

/* Last Import */
.last-import {
  padding: 1rem;
  background: #f3f4f6;
  border-radius: 8px;
}

.last-import-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.calendar-icon {
  width: 1rem;
  height: 1rem;
  color: #6b7280;
  flex-shrink: 0;
}

.last-import-text {
  font-size: 0.875rem;
  color: #6b7280;
}

/* Modal */
.import-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 1rem;
}

.import-modal {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.modal-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.close-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: none;
  background: #f3f4f6;
  border-radius: 6px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
}

.close-button:hover {
  background: #e5e7eb;
  color: #374151;
}

.close-button svg {
  width: 1rem;
  height: 1rem;
}

.modal-content {
  padding: 1.5rem;
  overflow-y: auto;
  flex: 1;
}


/* Form */
.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
}

.form-group input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Upload Area */
.upload-area {
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  transition: all 0.2s;
}

.upload-area:hover {
  border-color: #9ca3af;
}

.upload-placeholder {
  cursor: pointer;
}

.upload-icon {
  margin-bottom: 1rem;
}

.upload-icon svg {
  width: 3rem;
  height: 3rem;
  color: #9ca3af;
  margin: 0 auto;
}

.upload-text p {
  margin: 0.25rem 0;
  color: #6b7280;
}

.upload-text strong {
  color: #1f2937;
}

.upload-hint {
  font-size: 0.875rem;
  color: #9ca3af;
}

.file-selected {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 6px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.file-icon svg {
  width: 2rem;
  height: 2rem;
  color: #6b7280;
}

.file-name {
  font-weight: 600;
  color: #1f2937;
}

.file-size {
  font-size: 0.875rem;
  color: #6b7280;
}

.remove-file-btn {
  padding: 0.5rem;
  border: none;
  background: #fee2e2;
  color: #dc2626;
  border-radius: 6px;
  cursor: pointer;
}

.remove-file-btn svg {
  width: 1rem;
  height: 1rem;
}

/* Preview Section */
.preview-section {
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid #e5e7eb;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.preview-header h3 {
  font-size: 1.125rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.preview-stats {
  display: flex;
  gap: 0.75rem;
}

.preview-stats .stat {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 500;
}

.preview-stats .stat.success {
  background: #dcfce7;
  color: #16a34a;
}

.preview-stats .stat.error {
  background: #fee2e2;
  color: #dc2626;
}

/* Preview Errors */
.preview-errors {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: #fef2f2;
  border-radius: 8px;
  border: 1px solid #fecaca;
}

.preview-errors h4 {
  font-size: 1rem;
  font-weight: 600;
  color: #dc2626;
  margin: 0 0 0.5rem;
}

.error-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.error-item,
.error-more {
  padding: 0.25rem 0;
  color: #991b1b;
  font-size: 0.875rem;
}

.error-more {
  font-style: italic;
  color: #dc2626;
}

/* Preview Table */
.preview-table {
  margin-bottom: 1.5rem;
}

.preview-table h4 {
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 1rem;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.data-table th,
.data-table td {
  padding: 0.75rem 0.5rem;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
}

.data-table th {
  font-weight: 600;
  color: #374151;
  background: #f9fafb;
}

.data-table td {
  color: #6b7280;
}

/* Actions */
.form-actions,
.preview-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.875rem;
}

.btn-primary {
  background: #1f2937;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #374151;
}

.btn-secondary {
  background: #f3f4f6;
  color: #1f2937;
}

.btn-secondary:hover {
  background: #e5e7eb;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Import Result */
.import-result {
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid #e5e7eb;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.result-icon {
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.result-icon svg {
  width: 1.5rem;
  height: 1.5rem;
}

.result-icon.success {
  background: #dcfce7;
  color: #16a34a;
}

.result-icon.error {
  background: #fee2e2;
  color: #dc2626;
}

.result-header h3 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.result-stats {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.result-stat {
  padding: 0.75rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.result-stat.success {
  background: #dcfce7;
  color: #16a34a;
}

.result-stat.warning {
  background: #fef3c7;
  color: #d97706;
}

.result-stat.error {
  background: #fee2e2;
  color: #dc2626;
}

.result-actions {
  display: flex;
  justify-content: flex-end;
}

/* Custom Format Info */
.custom-format-info {
  margin-bottom: 1.5rem;
}

.info-box {
  padding: 1.5rem;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
}

.info-box h4 {
  font-size: 1rem;
  font-weight: 600;
  color: #0369a1;
  margin: 0 0 1rem;
}

.info-box p {
  color: #0c4a6e;
  font-size: 0.875rem;
  margin: 0 0 1rem;
  line-height: 1.5;
}

.mapping-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem;
}

.mapping-list li {
  padding: 0.5rem 0;
  color: #0c4a6e;
  font-size: 0.875rem;
  border-bottom: 1px solid #e0f2fe;
}

.mapping-list li:last-child {
  border-bottom: none;
}

.mapping-list strong {
  color: #0369a1;
}

.note {
  font-style: italic;
  color: #0369a1;
  background: #e0f2fe;
  padding: 0.75rem;
  border-radius: 4px;
  margin: 0;
  font-size: 0.875rem;
}

.mapping-section {
  margin: 1rem 0;
}

.mapping-section h5 {
  font-size: 0.9rem;
  font-weight: 600;
  color: #0369a1;
  margin: 0 0 0.5rem;
}

/* Responsivo */
@media (max-width: 640px) {
  .import-stats {
    flex-direction: column;
  }
  
  .preview-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
  
  .preview-actions,
  .form-actions {
    flex-direction: column;
  }
  
  .data-table {
    font-size: 0.75rem;
  }
  
  .data-table th,
  .data-table td {
    padding: 0.5rem 0.25rem;
  }
}
</style>