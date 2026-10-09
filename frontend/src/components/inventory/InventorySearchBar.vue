<template>
  <div class="inventory-search">
    <div class="search-box">
      <Search class="search-icon" aria-hidden="true" />
      <input
        :value="modelValue"
        type="search"
        class="search-input"
        :class="{ 'search-input-clearable': modelValue }"
        :aria-label="tr('Buscar no estoque')"
        :placeholder="tr('Produto, marca, tamanho ou código...')"
        autocomplete="off"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      />
      <button v-if="modelValue" type="button" class="search-clear erp-button erp-button--ghost erp-button--icon" :aria-label="tr('Limpar busca')" @click="emit('clear')">
        <X aria-hidden="true" />
      </button>
    </div>
    <button type="button" class="scan-button erp-button erp-button--secondary erp-button--icon" :aria-label="tr('Escanear código')" :title="tr('Escanear código')" @click="emit('scan')">
      <ScanLine aria-hidden="true" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { ScanLine, Search, X } from 'lucide-vue-next'
import { useInventoryI18n } from '@/components/inventory/i18n'

defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; clear: []; scan: [] }>()
const { tr } = useInventoryI18n()
</script>

<style scoped>
.inventory-search{display:flex;gap:var(--space-3);margin-bottom:var(--space-3)}.search-box{position:relative;flex:1;min-width:0}.search-icon{position:absolute;left:12px;top:50%;width:16px;height:16px;color:#64748b;transform:translateY(-50%);pointer-events:none}.search-input{width:100%;min-height:42px;padding:10px 12px 10px 36px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);color:var(--color-text);font:inherit;font-size:.875rem;box-sizing:border-box}.search-input:hover{border-color:#94a3b8}.search-input:focus-visible{border-color:var(--color-brand-600);box-shadow:0 0 0 3px rgb(37 99 235 / 10%)}.search-input-clearable{padding-right:44px}.search-clear{position:absolute;right:5px;top:50%;transform:translateY(-50%)}.scan-button{width:42px;min-width:42px;height:42px;min-height:42px}.search-clear :deep(svg),.scan-button :deep(svg){width:18px;height:18px}@media(max-width:600px){.inventory-search{gap:var(--space-2)}.search-input,.scan-button{min-height:44px}.scan-button{width:44px;min-width:44px;height:44px}}
</style>
