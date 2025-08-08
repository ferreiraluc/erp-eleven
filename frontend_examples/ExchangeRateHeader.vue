<!-- Exchange Rate Header Component for Admin Users -->
<template>
  <div class="exchange-rate-header">
    <!-- Header Display Mode -->
    <div v-if="!editMode" class="rate-display">
      <div class="rate-item" v-for="rate in currentRates" :key="rate.pair">
        <span class="currency-pair">{{ rate.pair }}</span>
        <span class="rate-value">{{ formatRate(rate.value) }}</span>
      </div>
      
      <!-- Edit Button (Only for Admin) -->
      <button 
        v-if="isAdmin" 
        @click="enterEditMode"
        class="edit-btn"
        title="Editar taxas de câmbio"
      >
        <Icon name="edit" />
      </button>
      
      <span class="last-updated">
        Atualizado: {{ formatDate(lastUpdated) }}
      </span>
    </div>

    <!-- Edit Mode -->
    <div v-else class="rate-edit">
      <div class="edit-form">
        <div class="rate-input" v-for="rate in editableRates" :key="rate.pair">
          <label>{{ rate.label }}</label>
          <input 
            v-model.number="rate.value"
            type="number"
            step="0.0001"
            :placeholder="rate.placeholder"
            class="rate-field"
          />
        </div>
        
        <div class="edit-actions">
          <button @click="saveRates" class="save-btn" :disabled="saving">
            {{ saving ? 'Salvando...' : 'Salvar' }}
          </button>
          <button @click="cancelEdit" class="cancel-btn">
            Cancelar
          </button>
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

const editMode = ref(false)
const saving = ref(false)

// Computed properties
const isAdmin = computed(() => authStore.user?.role === 'ADMIN')

const currentRates = computed(() => [
  { pair: 'USD→BRL', value: exchangeStore.rates.usd_to_brl },
  { pair: 'USD→G$', value: exchangeStore.rates.usd_to_pyg },
  { pair: 'EUR→BRL', value: exchangeStore.rates.eur_to_brl },
  { pair: 'EUR→G$', value: exchangeStore.rates.eur_to_pyg }
])

const lastUpdated = computed(() => exchangeStore.rates.last_updated)

// Editable rates for form
const editableRates = ref([
  { 
    pair: 'usd_to_brl', 
    label: 'USD → BRL', 
    value: 0,
    placeholder: 'Ex: 5.8500'
  },
  { 
    pair: 'usd_to_pyg', 
    label: 'USD → G$', 
    value: 0,
    placeholder: 'Ex: 7500.0000'
  },
  { 
    pair: 'eur_to_brl', 
    label: 'EUR → BRL', 
    value: 0,
    placeholder: 'Ex: 6.2000'
  },
  { 
    pair: 'eur_to_pyg', 
    label: 'EUR → G$', 
    value: 0,
    placeholder: 'Ex: 8200.0000'
  }
])

// Methods
const enterEditMode = () => {
  if (!isAdmin.value) return
  
  // Copy current values to edit form
  editableRates.value[0].value = exchangeStore.rates.usd_to_brl
  editableRates.value[1].value = exchangeStore.rates.usd_to_pyg
  editableRates.value[2].value = exchangeStore.rates.eur_to_brl
  editableRates.value[3].value = exchangeStore.rates.eur_to_pyg
  
  editMode.value = true
}

const cancelEdit = () => {
  editMode.value = false
  // Reset form values
  editableRates.value.forEach(rate => rate.value = 0)
}

const saveRates = async () => {
  if (!isAdmin.value) return
  
  saving.value = true
  
  try {
    const updateData = {
      usd_to_brl: editableRates.value[0].value || null,
      usd_to_pyg: editableRates.value[1].value || null,
      eur_to_brl: editableRates.value[2].value || null,
      eur_to_pyg: editableRates.value[3].value || null,
      source: 'Header Edit',
      notes: `Atualizado via header por ${authStore.user?.name}`,
      updated_by: authStore.user?.name || 'Admin'
    }
    
    await exchangeStore.updateRates(updateData)
    
    showSuccess('Taxas de câmbio atualizadas com sucesso!')
    editMode.value = false
    
  } catch (error) {
    console.error('Erro ao atualizar taxas:', error)
    showError('Erro ao atualizar taxas de câmbio')
  } finally {
    saving.value = false
  }
}

const formatRate = (value: number) => {
  if (!value) return '--'
  
  // Format based on currency magnitude
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
  return new Date(date).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Load rates on mount
onMounted(() => {
  exchangeStore.fetchCurrentRates()
})
</script>

<style scoped>
.exchange-rate-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.rate-display {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.rate-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
}

.currency-pair {
  font-size: 0.75rem;
  opacity: 0.9;
  font-weight: 500;
}

.rate-value {
  font-size: 0.9rem;
  font-weight: 700;
  font-family: 'Monaco', monospace;
}

.edit-btn {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.edit-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.last-updated {
  font-size: 0.7rem;
  opacity: 0.8;
  margin-left: auto;
}

.rate-edit {
  width: 100%;
}

.edit-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  align-items: end;
}

.rate-input {
  display: flex;
  flex-direction: column;
}

.rate-input label {
  font-size: 0.75rem;
  opacity: 0.9;
  margin-bottom: 4px;
}

.rate-field {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  padding: 6px 8px;
  border-radius: 4px;
  font-family: 'Monaco', monospace;
}

.rate-field::placeholder {
  color: rgba(255, 255, 255, 0.6);
}

.edit-actions {
  display: flex;
  gap: 8px;
}

.save-btn {
  background: #10b981;
  border: none;
  color: white;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cancel-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.5);
  color: white;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
}

.cancel-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

@media (max-width: 768px) {
  .rate-display {
    justify-content: center;
  }
  
  .edit-form {
    grid-template-columns: 1fr 1fr;
  }
  
  .edit-actions {
    grid-column: 1 / -1;
    justify-content: center;
  }
}
</style>