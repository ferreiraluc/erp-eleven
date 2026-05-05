<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-header">
        <h2>Agrupar sugestão <span class="item-count">({{ localItems.length }} itens)</span></h2>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <!-- Nome do grupo -->
        <div class="form-group">
          <label>Nome do grupo</label>
          <input
            v-model="groupName"
            type="text"
            class="form-input"
            placeholder="Ex: DKR003, FLC009 LUTT/NAPA..."
            :list="'sug-gname-list'"
            ref="nameInputRef"
            @keydown.enter.prevent="confirm"
          />
          <datalist id="sug-gname-list">
            <option v-for="gk in existingGroupKeys" :key="gk" :value="gk" />
          </datalist>
        </div>

        <!-- Lista de itens -->
        <div class="items-section">
          <div class="items-header">
            <span class="items-title">Itens a agrupar</span>
            <span class="items-hint">Clique em × para remover um item da seleção</span>
          </div>
          <div class="items-list" v-if="localItems.length > 0">
            <div
              v-for="item in localItems"
              :key="item.id"
              class="item-row"
            >
              <div class="item-thumb-wrap">
                <img v-if="item.image_data" :src="item.image_data" alt="" class="item-thumb" />
                <div v-else class="item-thumb-placeholder">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                </div>
              </div>
              <div class="item-info">
                <span class="item-name">{{ item.name }}</span>
                <div class="item-meta">
                  <span v-if="item.color" class="meta-tag">{{ item.color }}</span>
                  <span v-if="item.size" class="meta-tag meta-size">{{ item.size }}</span>
                  <span v-if="item.sku_internal" class="meta-sku">{{ item.sku_internal }}</span>
                </div>
              </div>
              <div class="item-stock">{{ item.current_stock }}</div>
              <button class="remove-btn" @click="removeItem(item.id)" title="Remover da seleção">×</button>
            </div>
          </div>
          <div v-else class="empty-items">
            <p>Nenhum item na seleção. Cancele e selecione os itens manualmente.</p>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="emit('close')" class="btn btn-secondary" :disabled="grouping">Cancelar</button>
        <button
          @click="confirm"
          class="btn btn-primary"
          :disabled="!groupName.trim() || localItems.length < 2 || grouping"
        >
          <span v-if="grouping">Agrupando...</span>
          <span v-else>Agrupar {{ localItems.length }} itens</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'

const props = defineProps<{
  items: InventoryItem[]
  suggestedName: string
  existingGroupKeys?: string[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'grouped', groupKey: string, count: number): void
}>()

const groupName = ref(props.suggestedName)
const localItems = ref<InventoryItem[]>([...props.items])
const grouping = ref(false)
const nameInputRef = ref<HTMLInputElement | null>(null)

onMounted(() => {
  nextTick(() => nameInputRef.value?.focus())
})

function removeItem(id: string) {
  localItems.value = localItems.value.filter(i => i.id !== id)
}

async function confirm() {
  const name = groupName.value.trim()
  if (!name || localItems.value.length < 2 || grouping.value) return
  grouping.value = true
  try {
    await inventoryAPI.groupItems(localItems.value.map(i => i.id), name)
    emit('grouped', name, localItems.value.length)
  } catch (e: any) {
    const msg = e.response?.data?.detail || 'Erro ao agrupar'
    alert(msg)
  } finally {
    grouping.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 2500; padding: 1rem;
}
.modal-container {
  background: white; border-radius: 12px; width: 100%;
  max-width: 540px; max-height: 90vh;
  display: flex; flex-direction: column; overflow: hidden;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; flex-shrink: 0;
}
.modal-header h2 { font-size: 1rem; font-weight: 700; color: #111827; margin: 0; }
.item-count { font-weight: 400; color: #6b7280; font-size: 0.875rem; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; padding: 0.25rem; }

.modal-body { overflow-y: auto; padding: 1rem 1.25rem; flex: 1; display: flex; flex-direction: column; gap: 1rem; }

.form-group { display: flex; flex-direction: column; gap: 0.3rem; }
.form-group label { font-size: 0.78rem; font-weight: 600; color: #374151; }
.form-input { padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.9rem; width: 100%; box-sizing: border-box; }
.form-input:focus { outline: none; border-color: #3b82f6; }

.items-section { display: flex; flex-direction: column; gap: 0.5rem; }
.items-header { display: flex; align-items: baseline; justify-content: space-between; }
.items-title { font-size: 0.82rem; font-weight: 600; color: #374151; }
.items-hint { font-size: 0.7rem; color: #9ca3af; }

.items-list { display: flex; flex-direction: column; gap: 0.35rem; max-height: 340px; overflow-y: auto; }

.item-row {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.45rem 0.6rem; border: 1px solid #e5e7eb; border-radius: 8px;
  background: #fafafa;
}
.item-thumb-wrap { flex-shrink: 0; }
.item-thumb { width: 32px; height: 32px; object-fit: cover; border-radius: 5px; }
.item-thumb-placeholder {
  width: 32px; height: 32px; background: #e5e7eb; border-radius: 5px;
  display: flex; align-items: center; justify-content: center; color: #9ca3af;
}
.item-info { flex: 1; min-width: 0; }
.item-name { font-size: 0.82rem; font-weight: 600; color: #111827; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.item-meta { display: flex; gap: 0.3rem; flex-wrap: wrap; margin-top: 0.15rem; }
.meta-tag { font-size: 0.68rem; padding: 0.1rem 0.35rem; background: #e0e7ff; color: #3730a3; border-radius: 4px; }
.meta-size { background: #dcfce7; color: #166534; }
.meta-sku { font-size: 0.65rem; color: #9ca3af; }
.item-stock { font-size: 0.8rem; font-weight: 600; color: #374151; flex-shrink: 0; min-width: 24px; text-align: right; }
.remove-btn {
  flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%;
  background: #fee2e2; color: #dc2626; border: none; cursor: pointer;
  font-size: 1rem; display: flex; align-items: center; justify-content: center;
  line-height: 1;
}
.remove-btn:hover { background: #fca5a5; }

.empty-items { text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 1.5rem; }

.modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; padding: 0.875rem 1.25rem; border-top: 1px solid #e5e7eb; flex-shrink: 0; }
.btn { padding: 0.5rem 1.25rem; border-radius: 8px; font-size: 0.875rem; font-weight: 500; cursor: pointer; border: none; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { background: #93c5fd; cursor: not-allowed; }
.btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }
.btn-secondary:disabled { opacity: 0.5; }
</style>
