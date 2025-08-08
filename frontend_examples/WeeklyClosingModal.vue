<!-- Weekly Closing Modal for Saturday Operations -->
<template>
  <div class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h2>Fechamento Semanal - Sábado</h2>
        <button @click="$emit('close')" class="close-btn">×</button>
      </div>

      <div class="modal-body">
        <div class="closing-info">
          <div class="info-card">
            <h3>📅 Período de Vendas</h3>
            <p>{{ formatDateRange(salesPeriod.start, salesPeriod.end) }}</p>
          </div>
          
          <div class="info-card">
            <h3>💰 Total de Vendas</h3>
            <p class="sales-total">R$ {{ totalSales.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) }}</p>
          </div>
        </div>

        <div class="exchange-rates-section">
          <h3>💱 Médias de Câmbio da Semana</h3>
          <p class="section-description">
            Estas são as médias calculadas automaticamente baseadas nas taxas 
            registradas durante a semana de vendas (Domingo a Sábado).
          </p>

          <div v-if="loading" class="loading">
            <div class="spinner"></div>
            <p>Calculando médias semanais...</p>
          </div>

          <div v-else-if="weeklyAverages.length" class="averages-grid">
            <div 
              v-for="avg in weeklyAverages" 
              :key="avg.currency_pair"
              class="average-card"
            >
              <div class="avg-header">
                <h4>{{ formatCurrencyPair(avg.currency_pair) }}</h4>
                <div class="samples">{{ avg.sample_count }} amostras</div>
              </div>
              
              <div class="avg-rate">
                {{ formatRate(avg.average_rate) }}
              </div>
              
              <div class="avg-range">
                <span class="min">Min: {{ formatRate(avg.min_rate) }}</span>
                <span class="max">Max: {{ formatRate(avg.max_rate) }}</span>
              </div>

              <div class="recommendation-badge">
                ✅ Usar para fechamento
              </div>
            </div>
          </div>

          <div v-else class="no-rates">
            <p>⚠️ Nenhuma taxa de câmbio registrada nesta semana</p>
            <p class="suggestion">
              Considere usar as taxas atuais ou registrar manualmente.
            </p>
          </div>
        </div>

        <div class="closing-actions">
          <div class="action-group">
            <label class="checkbox-label">
              <input 
                v-model="confirmData.salesConfirmed" 
                type="checkbox"
              />
              <span class="checkmark"></span>
              Confirmo que todas as vendas da semana foram registradas
            </label>
          </div>

          <div class="action-group">
            <label class="checkbox-label">
              <input 
                v-model="confirmData.ratesReviewed" 
                type="checkbox"
              />
              <span class="checkmark"></span>
              Revisei e concordo com as médias de câmbio calculadas
            </label>
          </div>

          <div class="action-group">
            <label for="notes">Observações do Fechamento:</label>
            <textarea 
              id="notes"
              v-model="confirmData.notes"
              placeholder="Observações adicionais sobre a semana de vendas (opcional)..."
              rows="3"
            ></textarea>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="$emit('close')" class="cancel-btn">
          Cancelar
        </button>
        
        <button 
          @click="processClosing"
          :disabled="!canProcess || processing"
          class="confirm-btn"
        >
          <span v-if="processing">Processando...</span>
          <span v-else>🔒 Confirmar Fechamento Semanal</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useExchangeRateStore } from '@/stores/exchangeRate'
import { useDashboardStore } from '@/stores/dashboard'
import { useNotifications } from '@/composables/useNotifications'

const exchangeStore = useExchangeRateStore()
const dashboardStore = useDashboardStore()
const { showSuccess, showError } = useNotifications()

const emit = defineEmits(['close', 'confirm'])

// Reactive data
const loading = ref(true)
const processing = ref(false)
const weeklyAverages = ref([])

const confirmData = ref({
  salesConfirmed: false,
  ratesReviewed: false,
  notes: ''
})

// Computed properties
const salesPeriod = computed(() => {
  const saturday = new Date()
  saturday.setDate(saturday.getDate() - saturday.getDay() + 6) // This Saturday
  const sunday = new Date(saturday)
  sunday.setDate(sunday.getDate() - 6) // Previous Sunday
  
  return {
    start: sunday,
    end: saturday
  }
})

const totalSales = computed(() => {
  // This should come from your dashboard store
  return dashboardStore.stats.totalVendas || 0
})

const canProcess = computed(() => {
  return confirmData.value.salesConfirmed && 
         confirmData.value.ratesReviewed && 
         weeklyAverages.value.length > 0
})

// Methods
const formatDateRange = (start: Date, end: Date) => {
  const startStr = start.toLocaleDateString('pt-BR', { 
    day: '2-digit', 
    month: '2-digit' 
  })
  const endStr = end.toLocaleDateString('pt-BR', { 
    day: '2-digit', 
    month: '2-digit',
    year: 'numeric'
  })
  return `${startStr} - ${endStr}`
}

const formatCurrencyPair = (pair: string) => {
  const labels = {
    'USD_TO_BRL': 'USD → BRL (Dólar para Real)',
    'USD_TO_PYG': 'USD → G$ (Dólar para Guarani)',
    'EUR_TO_BRL': 'EUR → BRL (Euro para Real)',
    'EUR_TO_PYG': 'EUR → G$ (Euro para Guarani)'
  }
  return labels[pair] || pair
}

const formatRate = (rate: number) => {
  if (!rate) return '--'
  
  if (rate > 1000) {
    return rate.toLocaleString('pt-BR', { 
      minimumFractionDigits: 0, 
      maximumFractionDigits: 0 
    })
  } else {
    return rate.toLocaleString('pt-BR', { 
      minimumFractionDigits: 4, 
      maximumFractionDigits: 4 
    })
  }
}

const loadWeeklyAverages = async () => {
  loading.value = true
  
  try {
    const saturdayDate = salesPeriod.value.end.toISOString().split('T')[0]
    const averages = await exchangeStore.getSalesWeekAverage(saturdayDate)
    
    weeklyAverages.value = averages.filter(avg => avg.average_rate !== null)
    
  } catch (error) {
    console.error('Error loading weekly averages:', error)
    showError('Erro ao carregar médias semanais')
  } finally {
    loading.value = false
  }
}

const processClosing = async () => {
  if (!canProcess.value) return
  
  processing.value = true
  
  try {
    const closingData = {
      period: {
        start: salesPeriod.value.start.toISOString().split('T')[0],
        end: salesPeriod.value.end.toISOString().split('T')[0]
      },
      totalSales: totalSales.value,
      exchangeRateAverages: weeklyAverages.value,
      notes: confirmData.value.notes,
      processedBy: 'admin', // You should get this from auth store
      processedAt: new Date().toISOString()
    }
    
    emit('confirm', closingData)
    
    showSuccess('Fechamento semanal processado com sucesso!')
    
  } catch (error) {
    console.error('Error processing weekly closing:', error)
    showError('Erro ao processar fechamento semanal')
  } finally {
    processing.value = false
  }
}

// Lifecycle
onMounted(() => {
  loadWeeklyAverages()
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: white;
  border-radius: 12px;
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8fafc;
}

.modal-header h2 {
  margin: 0;
  color: #1a202c;
  font-size: 1.25rem;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #6b7280;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
}

.close-btn:hover {
  background: #f3f4f6;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.closing-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.info-card {
  padding: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.info-card h3 {
  margin: 0 0 8px 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}

.info-card p {
  margin: 0;
  font-size: 1rem;
  color: #1a202c;
}

.sales-total {
  font-size: 1.25rem !important;
  font-weight: 700 !important;
  color: #059669 !important;
}

.exchange-rates-section {
  margin-bottom: 24px;
}

.exchange-rates-section h3 {
  margin: 0 0 8px 0;
  color: #1a202c;
  font-size: 1.125rem;
  font-weight: 600;
}

.section-description {
  margin: 0 0 16px 0;
  color: #6b7280;
  font-size: 0.875rem;
}

.loading {
  text-align: center;
  padding: 40px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e2e8f0;
  border-top: 3px solid #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.averages-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.average-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: white;
  position: relative;
}

.avg-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.avg-header h4 {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  line-height: 1.2;
}

.samples {
  font-size: 0.75rem;
  color: #6b7280;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 10px;
}

.avg-rate {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1a202c;
  font-family: 'Monaco', monospace;
  margin-bottom: 8px;
}

.avg-range {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.min, .max {
  font-size: 0.75rem;
  color: #6b7280;
  font-family: 'Monaco', monospace;
}

.recommendation-badge {
  background: #dcfce7;
  color: #166534;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  text-align: center;
}

.no-rates {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.suggestion {
  font-size: 0.875rem;
  margin-top: 8px;
}

.closing-actions {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.action-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  font-weight: 500;
  color: #374151;
}

.checkbox-label input[type="checkbox"] {
  display: none;
}

.checkmark {
  width: 20px;
  height: 20px;
  border: 2px solid #d1d5db;
  border-radius: 4px;
  position: relative;
  transition: all 0.2s;
}

.checkbox-label input[type="checkbox"]:checked + .checkmark {
  background: #3b82f6;
  border-color: #3b82f6;
}

.checkbox-label input[type="checkbox"]:checked + .checkmark::after {
  content: '✓';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: white;
  font-weight: bold;
  font-size: 12px;
}

.action-group label[for="notes"] {
  font-weight: 500;
  color: #374151;
}

.action-group textarea {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  resize: vertical;
  font-family: inherit;
}

.modal-footer {
  padding: 20px 24px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  background: #f8fafc;
}

.cancel-btn {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  background: white;
  color: #374151;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.cancel-btn:hover {
  background: #f9fafb;
}

.confirm-btn {
  padding: 8px 16px;
  background: #059669;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.confirm-btn:disabled {
  background: #d1d5db;
  cursor: not-allowed;
}

.confirm-btn:not(:disabled):hover {
  background: #047857;
}

@media (max-width: 768px) {
  .modal-overlay {
    padding: 10px;
  }
  
  .modal-content {
    max-height: 95vh;
  }
  
  .closing-info {
    grid-template-columns: 1fr;
  }
  
  .averages-grid {
    grid-template-columns: 1fr;
  }
  
  .modal-footer {
    flex-direction: column-reverse;
  }
  
  .cancel-btn,
  .confirm-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>