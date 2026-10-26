<template>
  <section class="related-products" :aria-label="tr('Produtos relacionados')">
    <header>
      <div>
        <h2>{{ tr('Continue por este produto') }}</h2>
        <p>
          {{
            tr(
              'Sugestões de grade, cor, marca e categoria. Os filtros da busca acima continuam preservados.',
            )
          }}
        </p>
      </div>
    </header>
    <div class="related-grid">
      <button
        v-for="row in rows"
        :key="row.item.id"
        type="button"
        class="related-card"
        @click="emit('open', row.item)"
      >
        <ProductThumbnail :item="row.item" class="related-thumb" />
        <span class="related-info"
          ><small
            >{{ tr(labels[row.relation])
            }}<template v-if="sameColor(row.item)"> · {{ tr('Mesma cor') }}</template></small
          ><strong>{{ row.item.name }}</strong
          ><span>{{ [row.item.size, row.item.color].filter(Boolean).join(' · ') }}</span
          ><span
            >{{ row.item.inventory_code }} · {{ displayStock(row.item.current_stock) }}
            {{ tr('un') }}</span
          ></span
        >
      </button>
    </div>
    <p v-if="loading" role="status">{{ tr('Buscando relacionados...') }}</p>
    <p v-else-if="error" role="alert">
      {{ tr('Não foi possível buscar os relacionados. O produto encontrado continua disponível.') }}
    </p>
    <p v-else-if="!rows.length">{{ tr('Nenhum relacionado disponível.') }}</p>
    <button
      v-if="error || cursor"
      class="erp-button erp-button--secondary erp-button--sm"
      :disabled="loading"
      @click="load"
    >
      {{ tr(error ? 'Tentar novamente' : 'Ver mais relacionados') }}
    </button>
  </section>
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  inventoryAPI,
  type InventoryItem,
  type ProductRelation,
  type RelatedProductCursor,
  type RelatedProducts,
} from '@/services/api'
import { colorKey } from '@/services/inventoryColors'
import { displayStock } from '@/services/inventoryStock'
import { useInventoryI18n } from './i18n'
import ProductThumbnail from './ProductThumbnail.vue'
const props = defineProps<{ source: InventoryItem }>()
const emit = defineEmits<{ open: [item: InventoryItem] }>()
const { tr } = useInventoryI18n()
const labels: Record<ProductRelation, string> = {
  family: 'Mesma grade',
  brand_category: 'Mesma marca e categoria',
  brand: 'Mesma marca',
  category: 'Mesma categoria',
}
const rows = ref<RelatedProducts['items']>([]),
  cursor = ref<RelatedProductCursor | null>(null),
  loading = ref(false),
  error = ref(false)
const controller = new AbortController()
const sameColor = (item: InventoryItem) =>
  !!item.color && colorKey(item.color) === colorKey(props.source.color || '')
async function load() {
  if (loading.value) return
  loading.value = true
  error.value = false
  try {
    const result = await inventoryAPI.getRelated(props.source.id, cursor.value, controller.signal)
    if (controller.signal.aborted) return
    const seen = new Set([props.source.id, ...rows.value.map((row) => row.item.id)])
    rows.value.push(...result.items.filter((row) => !seen.has(row.item.id)))
    cursor.value = result.next_cursor
  } catch {
    if (!controller.signal.aborted) error.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)
onBeforeUnmount(() => controller.abort())
</script>
<style scoped>
.related-products {
  margin: 16px 24px 32px;
  padding: 16px;
  background: white;
  border: 1px solid #dbe3ef;
  border-radius: 12px;
}
.related-products h2 {
  font-size: 15px;
  margin: 0 0 6px;
}
.related-products p {
  font-size: 12px;
  color: #64748b;
  margin: 8px 0 12px;
}
.related-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 8px;
  margin: 12px 0;
}
.related-card {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  color: #1e293b;
  text-align: left;
  cursor: pointer;
}
.related-card:hover,
.related-card:focus-visible {
  border-color: #2563eb;
  background: #eff6ff;
}
.related-thumb {
  width: 60px;
  height: 60px;
  flex-shrink: 0;
  object-fit: contain;
  background: white;
  border-radius: 6px;
}
.related-info {
  display: grid;
  gap: 4px;
  font-size: 12px;
  min-width: 0;
}
.related-info strong {
  font-size: 13px;
  overflow-wrap: anywhere;
}
.related-info small {
  color: #475569;
}
.related-info > span {
  color: #64748b;
}
@media (max-width: 600px) {
  .related-products {
    margin: 12px;
    padding: 12px;
  }
  .related-grid {
    grid-template-columns: 1fr;
  }
}
</style>
