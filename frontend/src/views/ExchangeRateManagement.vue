<template>
  <div class="exchange-management">
    <!-- Header -->
    <div class="management-header">
      <div class="header-left">
        <button @click="goBack" class="back-button">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
          </svg>
          {{ $t('exchangeManagement.backToDashboard') }}
        </button>
        <div class="page-title">
          <h1>{{ $t('exchangeManagement.title') }}</h1>
          <p>{{ $t('exchangeManagement.subtitle') }}</p>
        </div>
      </div>
      <div class="header-actions">
        <!-- Language Selector -->
        <div class="language-selector">
          <button 
            @click="showLanguageDropdown = !showLanguageDropdown" 
            class="language-button"
          >
            <span class="language-flag">{{ currentLocale.flag }}</span>
            <span class="language-text">{{ currentLocale.code.toUpperCase() }}</span>
            <svg class="dropdown-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
          </button>
          
          <div v-if="showLanguageDropdown" class="language-dropdown">
            <button 
              v-for="lang in availableLocales" 
              :key="lang.code"
              @click="handleLanguageChange(lang.code)"
              class="language-option"
              :class="{ 'active': lang.code === locale }"
            >
              <span class="option-flag">{{ lang.flag }}</span>
              <span class="option-name">{{ lang.name }}</span>
            </button>
          </div>
        </div>
        
        <button @click="showQuickUpdateModal = true" class="btn btn-primary">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
          </svg>
          {{ $t('exchangeManagement.quickUpdateRates') }}
        </button>
      </div>
    </div>

    <!-- Current Rates Overview -->
    <div class="current-rates-section">
      <h2>{{ $t('exchangeManagement.currentRates') }}</h2>
      <div class="current-rates-grid">
        <div class="rate-card" v-for="(rate, key) in currentRatesDisplay" :key="key">
          <div class="rate-header">
            <span class="rate-flag">{{ rate.flag }}</span>
            <span class="rate-pair">{{ rate.pair }}</span>
          </div>
          <div class="rate-value">{{ rate.value }}</div>
          <div class="rate-meta">
            <span class="rate-source">{{ rate.source }}</span>
            <span class="rate-updated">{{ formatDate(rate.updated) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Sales Average Section -->
    <div class="sales-average-section">
      <h2>{{ $t('exchangeManagement.salesWeeklyAverage') }}</h2>
      <div class="average-controls">
        <select v-model="selectedCurrency" @change="loadSalesAverage" class="currency-select">
          <option value="USD_TO_BRL">USD → BRL</option>
          <option value="USD_TO_PYG">USD → G$</option>
          <option value="EUR_TO_BRL">EUR → BRL</option>
          <option value="EUR_TO_USD">EUR → USD</option>
        </select>
        <select v-model="averageDays" @change="loadSalesAverage" class="days-select">
          <option value="7">{{ $t('exchangeManagement.last7Days') }}</option>
          <option value="14">{{ $t('exchangeManagement.last14Days') }}</option>
          <option value="30">{{ $t('exchangeManagement.last30Days') }}</option>
        </select>
      </div>
      
      <div v-if="salesAverage" class="average-card">
        <div class="average-info">
          <div class="average-rate">
            <span class="average-label">{{ $t('exchangeManagement.recommendedRate') }}</span>
            <span class="average-value">{{ salesAverage.average_rate?.toFixed(4) }}</span>
          </div>
          <div class="average-details">
            <span class="detail-item">{{ $t('exchangeManagement.min') }}: {{ salesAverage.min_rate?.toFixed(4) }}</span>
            <span class="detail-item">{{ $t('exchangeManagement.max') }}: {{ salesAverage.max_rate?.toFixed(4) }}</span>
            <span class="detail-item">{{ salesAverage.sample_count }} {{ $t('exchangeManagement.changes') }}</span>
          </div>
        </div>
        <div class="calculation-method">
          <small>{{ salesAverage.calculation_method }}</small>
        </div>
      </div>
    </div>

    <!-- Historical Rates -->
    <div class="historical-section">
      <div class="section-header">
        <h2>{{ $t('exchangeManagement.exchangeHistory') }}</h2>
        <div class="history-controls">
          <select v-model="historyDays" @change="loadHistory" class="days-select">
            <option value="7">{{ $t('exchangeManagement.last7Days') }}</option>
            <option value="30">{{ $t('exchangeManagement.last30Days') }}</option>
            <option value="90">{{ $t('exchangeManagement.last3Months') }}</option>
          </select>
          <button @click="loadHistory" class="btn btn-secondary">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            {{ $t('common.refresh') }}
          </button>
        </div>
      </div>

      <div v-if="isLoadingHistory" class="loading-state">
        <div class="loading-spinner"></div>
        <p>{{ $t('exchangeManagement.loading') }}</p>
      </div>

      <div v-else-if="historyError" class="error-state">
        <div class="error-icon">⚠️</div>
        <p>{{ historyError }}</p>
        <button @click="loadHistory" class="btn btn-primary">{{ $t('exchangeManagement.tryAgain') }}</button>
      </div>

      <div v-else-if="historicalRates.length === 0" class="empty-state">
        <div class="empty-icon">📊</div>
        <p>{{ $t('exchangeManagement.noHistory') }}</p>
      </div>

      <div v-else class="history-table-container">
        <table class="history-table">
          <thead>
            <tr>
              <th>{{ $t('exchangeManagement.currencyPair') }}</th>
              <th>{{ $t('exchangeManagement.rate') }}</th>
              <th>{{ $t('exchangeManagement.source') }}</th>
              <th>{{ $t('exchangeManagement.updatedBy') }}</th>
              <th>{{ $t('exchangeManagement.date') }}</th>
              <th>{{ $t('exchangeManagement.status') }}</th>
              <th>{{ $t('exchangeManagement.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rate in historicalRates" :key="rate.id" :class="{ 'active-rate': rate.is_active }">
              <td>
                <div class="currency-cell">
                  <span class="currency-flag">{{ getCurrencyFlag(rate.currency_pair) }}</span>
                  <span class="currency-name">{{ formatCurrencyPair(rate.currency_pair) }}</span>
                </div>
              </td>
              <td class="rate-cell">
                <span v-if="editingRate?.id !== rate.id" class="rate-display">
                  {{ Number(rate.rate).toFixed(4) }}
                </span>
                <input 
                  v-else 
                  v-model="editingRate.rate" 
                  type="number" 
                  step="0.0001" 
                  class="rate-input"
                  @keyup.enter="saveEditedRate"
                  @keyup.escape="cancelEdit"
                >
              </td>
              <td>
                <span v-if="editingRate?.id !== rate.id" class="source-display">{{ rate.source || $t('exchangeManagement.na') }}</span>
                <input 
                  v-else 
                  v-model="editingRate.source" 
                  type="text" 
                  class="source-input"
                  :placeholder="$t('exchangeManagement.source')"
                >
              </td>
              <td class="updated-by">{{ rate.updated_by || $t('exchangeManagement.systemUser') }}</td>
              <td class="date-cell">
                <div class="date-info">
                  <span class="date">{{ formatDate(rate.created_at) }}</span>
                  <span class="time">{{ formatTime(rate.created_at) }}</span>
                </div>
              </td>
              <td>
                <span :class="['status-badge', rate.is_active ? 'active' : 'inactive']">
                  {{ rate.is_active ? $t('exchangeManagement.active') : $t('exchangeManagement.historical') }}
                </span>
              </td>
              <td class="actions-cell">
                <div class="action-buttons">
                  <button 
                    v-if="editingRate?.id !== rate.id && !rate.is_active" 
                    @click="startEdit(rate)" 
                    class="btn-icon edit"
                    :title="$t('exchangeManagement.editRate')"
                  >
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                    </svg>
                  </button>
                  
                  <template v-if="editingRate?.id === rate.id">
                    <button @click="saveEditedRate" class="btn-icon save" :title="$t('exchangeManagement.saveChanges')">
                      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                      </svg>
                    </button>
                    <button @click="cancelEdit" class="btn-icon cancel" :title="$t('common.cancel')">
                      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                      </svg>
                    </button>
                  </template>
                  
                  <button 
                    v-if="editingRate?.id !== rate.id && !rate.is_active" 
                    @click="confirmDelete(rate)" 
                    class="btn-icon delete"
                    :title="$t('exchangeManagement.deleteRate')"
                  >
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Quick Update Modal -->
    <div v-if="showQuickUpdateModal" class="modal-overlay" @click="showQuickUpdateModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ $t('exchangeManagement.quickUpdateTitle') }}</h3>
          <button @click="showQuickUpdateModal = false" class="modal-close">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="update-form">
            <div class="form-row">
              <div class="form-group">
                <label>🇺🇸 USD → G$</label>
                <input v-model="quickUpdateRates.usd_to_pyg" type="number" step="0.01" placeholder="7500.00">
              </div>
              <div class="form-group">
                <label>🇺🇸 USD → 🇧🇷 R$</label>
                <input v-model="quickUpdateRates.usd_to_brl" type="number" step="0.01" placeholder="5.85">
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>🇪🇺 EUR → 🇺🇸 USD</label>
                <input v-model="quickUpdateRates.eur_to_usd" type="number" step="0.0001" placeholder="1.0850">
              </div>
              <div class="form-group">
                <label>🇪🇺 EUR → 🇧🇷 R$</label>
                <input v-model="quickUpdateRates.eur_to_brl" type="number" step="0.01" placeholder="6.20">
              </div>
            </div>
            <div class="form-group">
              <label>{{ $t('exchangeManagement.source') }}</label>
              <input v-model="quickUpdateRates.source" type="text" :placeholder="$t('exchangeManagement.sourcePlaceholder')">
            </div>
            <div class="form-group">
              <label>{{ $t('exchangeManagement.notes') }}</label>
              <textarea v-model="quickUpdateRates.notes" :placeholder="$t('exchangeManagement.notesPlaceholder')"></textarea>
            </div>
          </div>
          <div v-if="updateError" class="error-message">{{ updateError }}</div>
        </div>
        <div class="modal-footer">
          <button @click="showQuickUpdateModal = false" class="btn btn-secondary">{{ $t('common.cancel') }}</button>
          <button @click="performQuickUpdate" :disabled="isUpdating" class="btn btn-primary">
            <span v-if="isUpdating">{{ $t('exchangeManagement.updating') }}</span>
            <span v-else>{{ $t('exchangeManagement.updateRates') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteModal" class="modal-overlay" @click="showDeleteModal = false">
      <div class="modal-content delete-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ $t('exchangeManagement.confirmDeletion') }}</h3>
        </div>
        <div class="modal-body">
          <p>{{ $t('exchangeManagement.deleteConfirmation') }}</p>
          <div class="delete-details">
            <p><strong>{{ $t('exchangeManagement.currency') }}:</strong> {{ formatCurrencyPair(rateToDelete?.currency_pair) }}</p>
            <p><strong>{{ $t('exchangeManagement.rate') }}:</strong> {{ Number(rateToDelete?.rate).toFixed(4) }}</p>
            <p><strong>{{ $t('exchangeManagement.date') }}:</strong> {{ formatDate(rateToDelete?.created_at) }}</p>
          </div>
          <p class="warning-text">{{ $t('exchangeManagement.warning') }}</p>
        </div>
        <div class="modal-footer">
          <button @click="showDeleteModal = false" class="btn btn-secondary">{{ $t('common.cancel') }}</button>
          <button @click="deleteRate" :disabled="isDeleting" class="btn btn-danger">
            <span v-if="isDeleting">{{ $t('exchangeManagement.deleting') }}</span>
            <span v-else>{{ $t('common.delete') }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { setLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { exchangeRateAPI } from '@/services/api'

const router = useRouter()
const authStore = useAuthStore()
const { locale, t } = useI18n()

// Language settings
const showLanguageDropdown = ref(false)
const availableLocales = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'pt', name: 'Português', flag: '🇧🇷' },
  { code: 'es', name: 'Español', flag: '🇪🇸' }
]

// Reactive data
const currentRates = ref<any>(null)
const historicalRates = ref<any[]>([])
const salesAverage = ref<any>(null)
const isLoadingHistory = ref(false)
const historyError = ref<string | null>(null)
const historyDays = ref(30)
const selectedCurrency = ref('USD_TO_BRL')
const averageDays = ref(7)

// Modals
const showQuickUpdateModal = ref(false)
const showDeleteModal = ref(false)
const isUpdating = ref(false)
const isDeleting = ref(false)
const updateError = ref<string | null>(null)

// Editing
const editingRate = ref<any>(null)
const rateToDelete = ref<any>(null)

// Quick update form - initial values will be set in onMounted
const quickUpdateRates = ref({
  usd_to_pyg: null,
  usd_to_brl: null,
  eur_to_usd: null,
  eur_to_brl: null,
  source: '',
  notes: '',
  updated_by: authStore.user?.nome || 'Admin'
})

// Computed
const currentRatesDisplay = computed(() => {
  if (!currentRates.value) return {}
  
  return {
    usd_pyg: {
      flag: '🇺🇸→🇵🇾',
      pair: 'USD → G$',
      value: (typeof currentRates.value.usd_to_pyg === 'number' ? currentRates.value.usd_to_pyg.toFixed(0) : '7500'),
      source: currentRates.value.source || 'Manual',
      updated: currentRates.value.last_updated
    },
    usd_brl: {
      flag: '🇺🇸→🇧🇷',
      pair: 'USD → R$',
      value: (typeof currentRates.value.usd_to_brl === 'number' ? currentRates.value.usd_to_brl.toFixed(2) : '5.85'),
      source: currentRates.value.source || 'Manual',
      updated: currentRates.value.last_updated
    },
    eur_usd: {
      flag: '🇪🇺→🇺🇸',
      pair: 'EUR → USD',
      value: (typeof currentRates.value.eur_to_usd === 'number' ? currentRates.value.eur_to_usd.toFixed(4) : '1.0850'),
      source: currentRates.value.source || 'Manual',
      updated: currentRates.value.last_updated
    },
    eur_brl: {
      flag: '🇪🇺→🇧🇷',
      pair: 'EUR → R$',
      value: (typeof currentRates.value.eur_to_brl === 'number' ? currentRates.value.eur_to_brl.toFixed(2) : '6.20'),
      source: currentRates.value.source || 'Manual',
      updated: currentRates.value.last_updated
    }
  }
})

// Methods
const goBack = () => {
  router.push('/dashboard')
}

const loadCurrentRates = async () => {
  try {
    currentRates.value = await exchangeRateAPI.getCurrentRates()
  } catch (error) {
    console.error('Error loading current rates:', error)
  }
}

const loadHistory = async () => {
  try {
    isLoadingHistory.value = true
    historyError.value = null
    const response = await exchangeRateAPI.getHistory(historyDays.value)
    historicalRates.value = response.historical_rates || []
  } catch (error: any) {
    historyError.value = error.message || 'Failed to load exchange rate history'
  } finally {
    isLoadingHistory.value = false
  }
}

const loadSalesAverage = async () => {
  try {
    salesAverage.value = await exchangeRateAPI.getSalesAverage(selectedCurrency.value, averageDays.value)
  } catch (error) {
    console.error('Error loading sales average:', error)
  }
}

const performQuickUpdate = async () => {
  try {
    isUpdating.value = true
    updateError.value = null
    
    await exchangeRateAPI.quickUpdate(quickUpdateRates.value)
    
    showQuickUpdateModal.value = false
    await loadCurrentRates()
    await loadHistory()
    
    // Reset form
    resetQuickUpdateForm()
  } catch (error: any) {
    updateError.value = error.message || 'Failed to update rates'
  } finally {
    isUpdating.value = false
  }
}

const startEdit = (rate: any) => {
  editingRate.value = {
    id: rate.id,
    rate: Number(rate.rate),
    source: rate.source,
    notes: rate.notes
  }
}

const cancelEdit = () => {
  editingRate.value = null
}

const saveEditedRate = async () => {
  if (!editingRate.value) return
  
  try {
    await exchangeRateAPI.editHistoricalRate(editingRate.value.id, {
      rate: editingRate.value.rate,
      source: editingRate.value.source,
      notes: editingRate.value.notes,
      updated_by: authStore.user?.nome || 'Admin'
    })
    
    editingRate.value = null
    await loadHistory()
  } catch (error: any) {
    console.error('Error saving edited rate:', error)
  }
}

const confirmDelete = (rate: any) => {
  rateToDelete.value = rate
  showDeleteModal.value = true
}

const deleteRate = async () => {
  if (!rateToDelete.value) return
  
  try {
    isDeleting.value = true
    await exchangeRateAPI.deleteHistoricalRate(rateToDelete.value.id)
    
    showDeleteModal.value = false
    rateToDelete.value = null
    await loadHistory()
  } catch (error: any) {
    console.error('Error deleting rate:', error)
  } finally {
    isDeleting.value = false
  }
}

// Language functions
const currentLocale = computed(() => {
  return availableLocales.find(loc => loc.code === locale.value) || availableLocales[0]
})

const handleLanguageChange = (langCode: string) => {
  setLocale(langCode)
  showLanguageDropdown.value = false
}

const resetQuickUpdateForm = () => {
  quickUpdateRates.value = {
    usd_to_pyg: null,
    usd_to_brl: null,
    eur_to_usd: null,
    eur_to_brl: null,
    source: t('exchangeManagement.managementPanel'),
    notes: '',
    updated_by: authStore.user?.nome || 'Admin'
  }
}

// Helper functions
const formatDate = (dateString: string) => {
  if (!dateString) return t('exchangeManagement.na')
  return new Date(dateString).toLocaleDateString()
}

const formatTime = (dateString: string) => {
  if (!dateString) return ''
  return new Date(dateString).toLocaleTimeString()
}

const formatCurrencyPair = (pair: string) => {
  const pairs: { [key: string]: string } = {
    'USD_TO_PYG': 'USD → G$',
    'USD_TO_BRL': 'USD → R$',
    'EUR_TO_USD': 'EUR → USD',
    'EUR_TO_BRL': 'EUR → R$'
  }
  return pairs[pair] || pair
}

const getCurrencyFlag = (pair: string) => {
  const flags: { [key: string]: string } = {
    'USD_TO_PYG': '🇺🇸→🇵🇾',
    'USD_TO_BRL': '🇺🇸→🇧🇷',
    'EUR_TO_USD': '🇪🇺→🇺🇸',
    'EUR_TO_BRL': '🇪🇺→🇧🇷'
  }
  return flags[pair] || '💱'
}

// Close dropdown when clicking outside
const handleClickOutside = (event: Event) => {
  const target = event.target as Element
  const languageSelector = document.querySelector('.language-selector')
  
  if (languageSelector && !languageSelector.contains(target)) {
    showLanguageDropdown.value = false
  }
}

// Initialize data
onMounted(() => {
  // Initialize form with translated values
  resetQuickUpdateForm()
  
  loadCurrentRates()
  loadHistory()
  loadSalesAverage()
  
  // Add click outside listener
  document.addEventListener('click', handleClickOutside)
})

// Cleanup
onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.exchange-management {
  min-height: 100vh;
  background-color: #f8fafc;
  padding: 1.5rem;
}

/* Header */
.management-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 2rem;
  background: white;
  padding: 1.5rem;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.back-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  color: #6b7280;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
  width: fit-content;
}

.back-button:hover {
  background-color: #f3f4f6;
  border-color: #d1d5db;
  color: #374151;
}

.back-button svg {
  width: 1rem;
  height: 1rem;
}

.page-title h1 {
  margin: 0;
  font-size: 1.875rem;
  font-weight: 700;
  color: #111827;
}

.page-title p {
  margin: 0.25rem 0 0 0;
  color: #6b7280;
  font-size: 1rem;
}

.header-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}

/* Language Selector */
.language-selector {
  position: relative;
}

.language-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background-color: #f9fafb;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.875rem;
  color: #6b7280;
}

.language-button:hover {
  background-color: #f3f4f6;
  border-color: #9ca3af;
  color: #374151;
}

.language-flag {
  font-size: 0.875rem;
  width: 1.25rem;
  display: inline-block;
}

.language-text {
  font-size: 0.875rem;
  font-weight: 500;
}

.dropdown-icon {
  width: 1rem;
  height: 1rem;
  transition: transform 0.2s;
}

.language-selector:hover .dropdown-icon {
  transform: rotate(180deg);
}

.language-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  background-color: white;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  z-index: 50;
  margin-top: 0.25rem;
  min-width: 160px;
}

.language-option {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem;
  background: none;
  border: none;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s;
  font-size: 0.875rem;
}

.language-option:hover {
  background-color: #f3f4f6;
}

.language-option.active {
  background-color: #dbeafe;
  color: #2563eb;
}

.language-option:first-child {
  border-radius: 0.5rem 0.5rem 0 0;
}

.language-option:last-child {
  border-radius: 0 0 0.5rem 0.5rem;
}

.option-flag {
  font-size: 1rem;
  width: 1.5rem;
  display: inline-block;
}

.option-name {
  font-weight: 500;
}

/* Current Rates Section */
.current-rates-section {
  background: white;
  padding: 1.5rem;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.current-rates-section h2 {
  margin: 0 0 1.5rem 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.current-rates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.rate-card {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1rem;
  transition: all 0.2s;
}

.rate-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.rate-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.rate-flag {
  font-size: 1rem;
}

.rate-pair {
  font-size: 0.875rem;
  font-weight: 500;
  color: #6b7280;
}

.rate-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #111827;
  margin-bottom: 0.5rem;
}

.rate-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #9ca3af;
}

/* Sales Average Section */
.sales-average-section {
  background: white;
  padding: 1.5rem;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.sales-average-section h2 {
  margin: 0 0 1rem 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.average-controls {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.currency-select,
.days-select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  background: white;
  font-size: 0.875rem;
}

.average-card {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1rem;
  background: #f9fafb;
}

.average-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.average-rate {
  display: flex;
  flex-direction: column;
}

.average-label {
  font-size: 0.875rem;
  color: #6b7280;
}

.average-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #059669;
}

.average-details {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.detail-item {
  padding: 0.25rem 0.5rem;
  background: white;
  border-radius: 0.25rem;
  border: 1px solid #e5e7eb;
}

.calculation-method {
  color: #6b7280;
  font-size: 0.75rem;
}

/* Historical Section */
.historical-section {
  background: white;
  padding: 1.5rem;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.section-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.history-controls {
  display: flex;
  gap: 1rem;
  align-items: center;
}

/* Table */
.history-table-container {
  overflow-x: auto;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
}

.history-table th {
  background-color: #f9fafb;
  padding: 0.75rem;
  text-align: left;
  font-weight: 500;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
  font-size: 0.875rem;
}

.history-table td {
  padding: 0.75rem;
  border-bottom: 1px solid #f3f4f6;
  font-size: 0.875rem;
}

.history-table tr:hover {
  background-color: #f9fafb;
}

.history-table tr.active-rate {
  background-color: #ecfdf5;
}

.currency-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.currency-flag {
  font-size: 1rem;
}

.rate-cell {
  font-family: 'Monaco', 'Menlo', monospace;
  font-weight: 600;
}

.rate-input {
  width: 100px;
  padding: 0.25rem 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
  font-family: inherit;
}

.source-input {
  width: 120px;
  padding: 0.25rem 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
}

.date-info {
  display: flex;
  flex-direction: column;
}

.date-info .time {
  font-size: 0.75rem;
  color: #6b7280;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-badge.active {
  background-color: #dcfce7;
  color: #16a34a;
}

.status-badge.inactive {
  background-color: #f3f4f6;
  color: #6b7280;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.btn-icon {
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-icon svg {
  width: 1rem;
  height: 1rem;
}

.btn-icon.edit {
  background-color: #dbeafe;
  color: #2563eb;
}

.btn-icon.edit:hover {
  background-color: #bfdbfe;
}

.btn-icon.save {
  background-color: #dcfce7;
  color: #16a34a;
}

.btn-icon.save:hover {
  background-color: #bbf7d0;
}

.btn-icon.cancel {
  background-color: #fee2e2;
  color: #dc2626;
}

.btn-icon.cancel:hover {
  background-color: #fecaca;
}

.btn-icon.delete {
  background-color: #fee2e2;
  color: #dc2626;
}

.btn-icon.delete:hover {
  background-color: #fecaca;
}

/* States */
.loading-state,
.error-state,
.empty-state {
  text-align: center;
  padding: 3rem;
  color: #6b7280;
}

.loading-spinner {
  width: 2rem;
  height: 2rem;
  border: 2px solid #e5e7eb;
  border-top: 2px solid #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon,
.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal-content {
  background: white;
  border-radius: 0.75rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 500px;
  width: 90vw;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.5rem;
  color: #6b7280;
}

.modal-close:hover {
  color: #374151;
}

.modal-close svg {
  width: 1.25rem;
  height: 1.25rem;
}

.modal-body {
  padding: 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
}

/* Form */
.update-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  margin-bottom: 0.5rem;
}

.form-group input,
.form-group textarea {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 0.875rem;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.form-group textarea {
  resize: vertical;
  min-height: 60px;
}

/* Delete Modal */
.delete-modal .modal-content {
  max-width: 400px;
}

.delete-details {
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1rem;
  margin: 1rem 0;
}

.delete-details p {
  margin: 0.25rem 0;
  font-size: 0.875rem;
}

.warning-text {
  color: #dc2626;
  font-size: 0.875rem;
  font-weight: 500;
  margin-top: 1rem;
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.btn svg {
  width: 1rem;
  height: 1rem;
}

.btn-primary {
  background-color: #2563eb;
  color: white;
}

.btn-primary:hover {
  background-color: #1d4ed8;
}

.btn-primary:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: white;
  color: #6b7280;
  border-color: #d1d5db;
}

.btn-secondary:hover {
  background-color: #f9fafb;
  border-color: #9ca3af;
}

.btn-danger {
  background-color: #dc2626;
  color: white;
}

.btn-danger:hover {
  background-color: #b91c1c;
}

.error-message {
  background-color: #fee2e2;
  color: #dc2626;
  padding: 0.75rem;
  border-radius: 0.375rem;
  border: 1px solid #fecaca;
  margin-top: 1rem;
  font-size: 0.875rem;
}

/* Responsive */
@media (max-width: 768px) {
  .management-header {
    flex-direction: column;
    align-items: stretch;
    gap: 1rem;
  }

  .form-row {
    grid-template-columns: 1fr;
  }

  /* Cards 2x2 no mobile - menores como Nova Venda */
  .current-rates-grid {
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 0.75rem;
  }
  
  .rate-card {
    padding: 0.75rem !important;
    min-height: auto;
  }
  
  .rate-header {
    margin-bottom: 0.5rem !important;
    gap: 0.375rem;
  }
  
  .rate-flag {
    font-size: 0.875rem !important;
  }
  
  .rate-pair {
    font-size: 0.8125rem !important;
  }
  
  .rate-value {
    font-size: 1.25rem !important;
    margin-bottom: 0.375rem !important;
  }
  
  .rate-meta {
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.6875rem !important;
  }
  
  /* Reduzir texto de alterações no mobile */
  .detail-item {
    padding: 0.1875rem 0.375rem !important;
    font-size: 0.6875rem !important;
    white-space: nowrap;
  }
  
  .average-details {
    gap: 0.5rem !important;
    flex-wrap: wrap;
    justify-content: center;
  }
  
  .calculation-method {
    font-size: 0.625rem !important;
    line-height: 1.2;
    text-align: center;
    margin-top: 0.5rem;
  }

  .average-controls {
    flex-direction: column;
  }

  .history-controls {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>