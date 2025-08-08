<!-- Expandable Exchange Rate Card for Dashboard -->
<template>
  <div class="exchange-rate-card">
    <!-- Card Header -->
    <div class="card-header" @click="toggleExpanded">
      <div class="header-content">
        <div class="card-title">
          <h3>Taxa de Câmbio</h3>
          <span class="last-update">
            {{ formatDate(exchangeStore.rates.last_updated) }}
          </span>
        </div>
        
        <!-- Quick rates display -->
        <div class="quick-rates">
          <div class="quick-rate">
            <span class="label">USD→BRL</span>
            <span class="value">{{ formatRate(exchangeStore.rates.usd_to_brl) }}</span>
          </div>
          <div class="quick-rate">
            <span class="label">USD→G$</span>
            <span class="value">{{ formatRate(exchangeStore.rates.usd_to_pyg) }}</span>
          </div>
        </div>
      </div>
      
      <div class="card-actions">
        <!-- Quick Edit Button (Admin only) -->
        <button 
          v-if="isAdmin && !editMode" 
          @click.stop="enterEditMode"
          class="quick-edit-btn"
          title="Edição rápida"
        >
          <Icon name="edit" />
        </button>
        
        <button class="expand-btn" :class="{ expanded: isExpanded }">
          <Icon name="chevron-down" />
        </button>
      </div>
    </div>

    <!-- Quick Edit Mode (Admin only) -->
    <div v-if="editMode" class="quick-edit-panel">
      <div class="edit-grid">
        <div class="edit-field" v-for="rate in editableRates" :key="rate.pair">
          <label>{{ rate.label }}</label>
          <input 
            v-model.number="rate.value"
            type="number"
            step="0.0001"
            :placeholder="rate.placeholder"
          />
        </div>
      </div>
      
      <div class="edit-actions">
        <button @click="saveQuickEdit" class="save-btn" :disabled="saving">
          {{ saving ? 'Salvando...' : 'Salvar' }}
        </button>
        <button @click="cancelEdit" class="cancel-btn">
          Cancelar
        </button>
      </div>
    </div>

    <!-- Expanded Content -->
    <div v-if="isExpanded" class="card-content">
      <div class="content-tabs">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          class="tab-btn"
          :class="{ active: activeTab === tab.id }"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Current Rates Tab -->
      <div v-if="activeTab === 'current'" class="tab-content">
        <div class="rates-grid">
          <div 
            v-for="rate in allRates" 
            :key="rate.pair"
            class="rate-card"
          >
            <div class="rate-header">
              <span class="pair">{{ rate.label }}</span>
              <span class="source">{{ rate.source || 'Manual' }}</span>
            </div>
            <div class="rate-body">
              <span class="rate-value">{{ formatRate(rate.value) }}</span>
              <span class="trend" :class="rate.trend">
                {{ rate.change }}
              </span>
            </div>
            <div class="rate-footer">
              <span class="updated">{{ formatDate(rate.updated_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Weekly Averages Tab -->
      <div v-if="activeTab === 'weekly'" class="tab-content">
        <div class="week-selector">
          <button 
            v-for="week in weeks" 
            :key="week.offset"
            @click="selectedWeek = week.offset"
            class="week-btn"
            :class="{ active: selectedWeek === week.offset }"
          >
            {{ week.label }}
          </button>
        </div>

        <div class="weekly-averages" v-if="weeklyAverages.length">
          <div 
            v-for="avg in weeklyAverages" 
            :key="avg.currency_pair"
            class="average-card"
          >
            <div class="avg-header">
              <h4>{{ getCurrencyLabel(avg.currency_pair) }}</h4>
              <span class="period">
                {{ formatDateRange(avg.week_start, avg.week_end) }}
              </span>
            </div>
            
            <div class="avg-stats">
              <div class="stat">
                <span class="label">Média</span>
                <span class="value primary">{{ formatRate(avg.average_rate) }}</span>
              </div>
              <div class="stat">
                <span class="label">Min</span>
                <span class="value">{{ formatRate(avg.min_rate) }}</span>
              </div>
              <div class="stat">
                <span class="label">Max</span>
                <span class="value">{{ formatRate(avg.max_rate) }}</span>
              </div>
              <div class="stat">
                <span class="label">Amostras</span>
                <span class="value">{{ avg.sample_count }}</span>
              </div>
            </div>

            <!-- Weekly recommendation for sales -->
            <div v-if="selectedWeek === 0" class="recommendation">
              <Icon name="lightbulb" />
              <span>
                Use <strong>{{ formatRate(avg.average_rate) }}</strong> 
                como taxa média para fechamento de vendas
              </span>
            </div>
          </div>
        </div>

        <div v-else class="no-data">
          <Icon name="calendar" />
          <p>Nenhuma taxa registrada para esta semana</p>
        </div>
      </div>

      <!-- History Tab -->
      <div v-if="activeTab === 'history'" class="tab-content">
        <div class="history-filters">
          <select v-model="historyDays" @change="loadHistory">
            <option value="7">Últimos 7 dias</option>
            <option value="30">Últimos 30 dias</option>
            <option value="90">Últimos 90 dias</option>
          </select>
          
          <select v-model="historyCurrency" @change="loadHistory">
            <option value="">Todas as moedas</option>
            <option value="USD_TO_BRL">USD → BRL</option>
            <option value="USD_TO_PYG">USD → G$</option>
            <option value="EUR_TO_BRL">EUR → BRL</option>
            <option value="EUR_TO_PYG">EUR → G$</option>
          </select>
        </div>

        <div class="history-table">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Par</th>
                <th>Taxa</th>
                <th>Fonte</th>
                <th>Atualizado por</th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="record in historyData" 
                :key="`${record.id}-${record.created_at}`"
              >
                <td>{{ formatDate(record.rate_date) }}</td>
                <td>{{ getCurrencyLabel(record.currency_pair) }}</td>
                <td class="rate-cell">{{ formatRate(record.rate) }}</td>
                <td>{{ record.source }}</td>
                <td>{{ record.updated_by || '--' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useExchangeRateStore } from '@/stores/exchangeRate'
import { useNotifications } from '@/composables/useNotifications'

const authStore = useAuthStore()
const exchangeStore = useExchangeRateStore()
const { showSuccess, showError } = useNotifications()

// Reactive data
const isExpanded = ref(false)
const editMode = ref(false)
const saving = ref(false)
const activeTab = ref('current')
const selectedWeek = ref(0) // 0 = current week, 1 = last week, etc.
const historyDays = ref('30')
const historyCurrency = ref('')

// Computed properties
const isAdmin = computed(() => authStore.user?.role === 'ADMIN')

const tabs = [
  { id: 'current', label: 'Taxas Atuais' },
  { id: 'weekly', label: 'Médias Semanais' },
  { id: 'history', label: 'Histórico' }
]

const weeks = [
  { offset: 0, label: 'Semana Atual' },
  { offset: 1, label: 'Semana Passada' },
  { offset: 2, label: '2 Semanas Atrás' },
  { offset: 3, label: '3 Semanas Atrás' }
]

const allRates = computed(() => [
  {
    pair: 'USD_TO_BRL',
    label: 'USD → BRL',
    value: exchangeStore.rates.usd_to_brl,
    source: exchangeStore.rates.source,
    updated_at: exchangeStore.rates.last_updated,
    change: '+0.05',
    trend: 'positive'
  },
  {
    pair: 'USD_TO_PYG',
    label: 'USD → G$',
    value: exchangeStore.rates.usd_to_pyg,
    source: exchangeStore.rates.source,
    updated_at: exchangeStore.rates.last_updated,
    change: '-12.50',
    trend: 'negative'
  },
  {
    pair: 'EUR_TO_BRL',
    label: 'EUR → BRL',
    value: exchangeStore.rates.eur_to_brl,
    source: exchangeStore.rates.source,
    updated_at: exchangeStore.rates.last_updated,
    change: '+0.08',
    trend: 'positive'
  },
  {
    pair: 'EUR_TO_PYG',
    label: 'EUR → G$',
    value: exchangeStore.rates.eur_to_pyg,
    source: exchangeStore.rates.source,
    updated_at: exchangeStore.rates.last_updated,
    change: '-25.00',
    trend: 'negative'
  }
])

const editableRates = ref([
  { pair: 'usd_to_brl', label: 'USD → BRL', value: 0, placeholder: '5.8500' },
  { pair: 'usd_to_pyg', label: 'USD → G$', value: 0, placeholder: '7500.0000' },
  { pair: 'eur_to_brl', label: 'EUR → BRL', value: 0, placeholder: '6.2000' },
  { pair: 'eur_to_pyg', label: 'EUR → G$', value: 0, placeholder: '8200.0000' }
])

const weeklyAverages = ref([])
const historyData = ref([])

// Methods
const toggleExpanded = () => {
  isExpanded.value = !isExpanded.value
  
  if (isExpanded.value) {
    loadWeeklyAverages()
    loadHistory()
  }
}

const enterEditMode = () => {
  if (!isAdmin.value) return
  
  editableRates.value[0].value = exchangeStore.rates.usd_to_brl
  editableRates.value[1].value = exchangeStore.rates.usd_to_pyg
  editableRates.value[2].value = exchangeStore.rates.eur_to_brl
  editableRates.value[3].value = exchangeStore.rates.eur_to_pyg
  
  editMode.value = true
}

const cancelEdit = () => {
  editMode.value = false
}

const saveQuickEdit = async () => {
  if (!isAdmin.value) return
  
  saving.value = true
  
  try {
    const updateData = {
      usd_to_brl: editableRates.value[0].value || null,
      usd_to_pyg: editableRates.value[1].value || null,
      eur_to_brl: editableRates.value[2].value || null,
      eur_to_pyg: editableRates.value[3].value || null,
      source: 'Dashboard',
      notes: `Atualizado via dashboard por ${authStore.user?.name}`,
      updated_by: authStore.user?.name || 'Admin'
    }
    
    await exchangeStore.updateRates(updateData)
    
    showSuccess('Taxas atualizadas com sucesso!')
    editMode.value = false
    
    // Reload data if expanded
    if (isExpanded.value) {
      await loadWeeklyAverages()
      await loadHistory()
    }
    
  } catch (error) {
    console.error('Erro ao salvar taxas:', error)
    showError('Erro ao atualizar taxas')
  } finally {
    saving.value = false
  }
}

const loadWeeklyAverages = async () => {
  try {
    weeklyAverages.value = await exchangeStore.getWeeklyAverages(selectedWeek.value)
  } catch (error) {
    console.error('Erro ao carregar médias semanais:', error)
  }
}

const loadHistory = async () => {
  try {
    const filters = {
      days: parseInt(historyDays.value),
      currency_pair: historyCurrency.value || undefined
    }
    historyData.value = await exchangeStore.getHistory(filters)
  } catch (error) {
    console.error('Erro ao carregar histórico:', error)
  }
}

const getCurrencyLabel = (pair: string) => {
  const labels = {
    'USD_TO_BRL': 'USD → BRL',
    'USD_TO_PYG': 'USD → G$',
    'EUR_TO_BRL': 'EUR → BRL',
    'EUR_TO_PYG': 'EUR → G$'
  }
  return labels[pair] || pair
}

const formatRate = (value: number) => {
  if (!value) return '--'
  
  if (value > 1000) {
    return value.toLocaleString('pt-BR', { 
      minimumFractionDigits: 0, 
      maximumFractionDigits: 0 
    })
  } else {
    return value.toLocaleString('pt-BR', { 
      minimumFractionDigits: 4, 
      maximumFractionDigits: 4 
    })
  }
}

const formatDate = (date: string) => {
  if (!date) return '--'
  return new Date(date).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatDateRange = (start: string, end: string) => {
  const startDate = new Date(start).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  const endDate = new Date(end).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  return `${startDate} - ${endDate}`
}

// Watch for week changes
watch(selectedWeek, () => {
  if (isExpanded.value) {
    loadWeeklyAverages()
  }
})

onMounted(() => {
  exchangeStore.fetchCurrentRates()
})
</script>

<style scoped>
.exchange-rate-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  transition: all 0.3s ease;
}

.card-header {
  padding: 20px;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.last-update {
  font-size: 0.8rem;
  opacity: 0.9;
}

.quick-rates {
  display: flex;
  gap: 24px;
}

.quick-rate {
  text-align: center;
}

.quick-rate .label {
  display: block;
  font-size: 0.7rem;
  opacity: 0.9;
}

.quick-rate .value {
  display: block;
  font-size: 0.9rem;
  font-weight: 700;
  font-family: 'Monaco', monospace;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quick-edit-btn {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
}

.expand-btn {
  background: none;
  border: none;
  color: white;
  transform: rotate(0deg);
  transition: transform 0.3s ease;
}

.expand-btn.expanded {
  transform: rotate(180deg);
}

.quick-edit-panel {
  padding: 20px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.edit-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.edit-field {
  display: flex;
  flex-direction: column;
}

.edit-field label {
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 4px;
  color: #374151;
}

.edit-field input {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-family: 'Monaco', monospace;
}

.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.save-btn {
  background: #10b981;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.cancel-btn {
  background: #6b7280;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.card-content {
  padding: 20px;
}

.content-tabs {
  display: flex;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 20px;
}

.tab-btn {
  background: none;
  border: none;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  color: #6b7280;
  font-weight: 500;
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.rates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

.rate-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.rate-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.pair {
  font-weight: 600;
  color: #374151;
}

.source {
  font-size: 0.75rem;
  color: #6b7280;
}

.rate-body {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.rate-value {
  font-size: 1.125rem;
  font-weight: 700;
  font-family: 'Monaco', monospace;
}

.trend {
  font-size: 0.875rem;
  font-weight: 500;
}

.trend.positive {
  color: #10b981;
}

.trend.negative {
  color: #ef4444;
}

.rate-footer {
  font-size: 0.75rem;
  color: #6b7280;
}

.week-selector {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.week-btn {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  background: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
}

.week-btn.active {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.weekly-averages {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.average-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.avg-header h4 {
  margin: 0 0 4px 0;
  color: #374151;
}

.period {
  font-size: 0.75rem;
  color: #6b7280;
}

.avg-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin: 12px 0;
}

.stat {
  text-align: center;
}

.stat .label {
  display: block;
  font-size: 0.75rem;
  color: #6b7280;
  margin-bottom: 2px;
}

.stat .value {
  display: block;
  font-weight: 600;
  font-family: 'Monaco', monospace;
}

.stat .value.primary {
  color: #3b82f6;
  font-size: 1.125rem;
}

.recommendation {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #92400e;
}

.history-filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.history-filters select {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
}

.history-table {
  overflow-x: auto;
}

.history-table table {
  width: 100%;
  border-collapse: collapse;
}

.history-table th,
.history-table td {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid #e2e8f0;
}

.history-table th {
  background: #f8fafc;
  font-weight: 600;
  color: #374151;
}

.rate-cell {
  font-family: 'Monaco', monospace;
  font-weight: 600;
}

.no-data {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    gap: 12px;
  }
  
  .quick-rates {
    gap: 16px;
  }
  
  .edit-grid {
    grid-template-columns: 1fr;
  }
  
  .rates-grid {
    grid-template-columns: 1fr;
  }
  
  .week-selector {
    justify-content: center;
  }
  
  .weekly-averages {
    grid-template-columns: 1fr;
  }
}
</style>