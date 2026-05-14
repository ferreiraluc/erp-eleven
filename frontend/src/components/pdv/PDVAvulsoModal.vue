<template>
  <div class="avulso-overlay" @click.self="$emit('close')">
    <div class="avulso-modal">
      <div class="avulso-header">
        <div class="avulso-icon">⚠</div>
        <div>
          <h3>Produto não encontrado</h3>
          <p>Adicione manualmente ao carrinho</p>
        </div>
        <button class="avulso-close" @click="$emit('close')">×</button>
      </div>

      <div class="avulso-body">
        <div v-if="scannedCode" class="avulso-code-hint">
          Código escaneado: <strong>{{ scannedCode }}</strong>
        </div>

        <div class="avulso-field">
          <label>Descrição do produto *</label>
          <input
            ref="nameInput"
            v-model="form.item_name"
            type="text"
            placeholder="Ex: Camiseta azul M"
            class="avulso-input"
            @keydown.enter="focusPrice"
          />
        </div>

        <div class="avulso-row">
          <div class="avulso-field">
            <label>Preço unitário (G$) *</label>
            <input
              ref="priceInput"
              v-model.number="form.unit_price_gs"
              type="number"
              min="0"
              placeholder="0"
              class="avulso-input"
              @keydown.enter="focusQty"
            />
          </div>
          <div class="avulso-field avulso-field-sm">
            <label>Qtd</label>
            <input
              ref="qtyInput"
              v-model.number="form.quantity"
              type="number"
              min="1"
              class="avulso-input"
              @keydown.enter="submit"
            />
          </div>
        </div>

        <div v-if="error" class="avulso-error">{{ error }}</div>
      </div>

      <div class="avulso-footer">
        <button class="avulso-btn-cancel" @click="$emit('close')">Cancelar</button>
        <button class="avulso-btn-add" @click="submit" :disabled="!canSubmit">
          + Adicionar ao carrinho
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'

const props = defineProps<{
  scannedCode?: string | null
}>()

const emit = defineEmits<{
  (e: 'add', item: {
    item_name: string
    quantity: number
    unit_price_gs: number
    is_avulso: true
    item_id: null
    item_sku: null
    item_category: null
    item_size: null
    item_color: null
    original_price_gs: null
    discount_gs: number
    location: string
  }): void
  (e: 'close'): void
}>()

const nameInput = ref<HTMLInputElement>()
const priceInput = ref<HTMLInputElement>()
const qtyInput = ref<HTMLInputElement>()

const form = ref({
  item_name: '',
  unit_price_gs: 0,
  quantity: 1,
})
const error = ref('')

const canSubmit = computed(() =>
  form.value.item_name.trim().length >= 2 && form.value.unit_price_gs > 0
)

onMounted(() => nextTick(() => nameInput.value?.focus()))

function focusPrice() { priceInput.value?.focus() }
function focusQty() { qtyInput.value?.focus() }

function submit() {
  if (!form.value.item_name.trim()) { error.value = 'Informe a descrição'; return }
  if (form.value.unit_price_gs <= 0) { error.value = 'Informe o preço'; return }
  error.value = ''
  emit('add', {
    item_id: null,
    item_name: form.value.item_name.trim(),
    item_sku: null,
    item_category: null,
    item_size: null,
    item_color: null,
    quantity: form.value.quantity,
    unit_price_gs: form.value.unit_price_gs,
    original_price_gs: null,
    discount_gs: 0,
    is_avulso: true,
    location: 'loja',
  })
}
</script>

<style scoped>
.avulso-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 2000; padding: 1rem;
}
.avulso-modal {
  background: white; border-radius: 1rem;
  width: 100%; max-width: 420px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.avulso-header {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 1.25rem 1.25rem 0.75rem;
  border-bottom: 1px solid #f3f4f6;
}
.avulso-icon { font-size: 1.75rem; line-height: 1; }
.avulso-header h3 { margin: 0; font-size: 1rem; font-weight: 700; color: #111827; }
.avulso-header p  { margin: 0; font-size: 0.75rem; color: #9ca3af; }
.avulso-close {
  margin-left: auto; background: none; border: none;
  font-size: 1.5rem; color: #6b7280; cursor: pointer; line-height: 1;
}
.avulso-body { padding: 1rem 1.25rem; }
.avulso-code-hint {
  background: #f0fdf4; border: 1px solid #bbf7d0;
  border-radius: 0.5rem; padding: 0.5rem 0.75rem;
  font-size: 0.8rem; color: #166534; margin-bottom: 1rem;
}
.avulso-field { display: flex; flex-direction: column; gap: 0.3rem; margin-bottom: 0.75rem; }
.avulso-field label { font-size: 0.78rem; font-weight: 600; color: #374151; }
.avulso-row { display: grid; grid-template-columns: 1fr auto; gap: 0.75rem; }
.avulso-field-sm { min-width: 80px; }
.avulso-input {
  border: 1.5px solid #e5e7eb; border-radius: 0.5rem;
  padding: 0.6rem 0.75rem; font-size: 0.95rem;
  outline: none; transition: border-color 0.15s;
}
.avulso-input:focus { border-color: #f97316; }
.avulso-error { color: #dc2626; font-size: 0.8rem; margin-top: 0.25rem; }
.avulso-footer {
  display: flex; gap: 0.75rem;
  padding: 0.875rem 1.25rem;
  border-top: 1px solid #f3f4f6;
}
.avulso-btn-cancel {
  flex: 1; padding: 0.6rem; border: 1.5px solid #e5e7eb;
  border-radius: 0.5rem; background: white; color: #6b7280;
  font-weight: 600; cursor: pointer;
}
.avulso-btn-add {
  flex: 2; padding: 0.6rem; border: none;
  border-radius: 0.5rem; background: #f97316; color: white;
  font-weight: 700; cursor: pointer; font-size: 0.9rem;
}
.avulso-btn-add:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
