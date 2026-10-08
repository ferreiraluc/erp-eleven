<template>
  <div class="erp-dialog-backdrop" @click.self="close">
    <section v-erp-dialog class="erp-dialog variants-modal" role="dialog" aria-modal="true" :aria-label="title">
      <header class="erp-dialog__header"><h2>{{ title }}</h2><button data-dialog-close class="erp-button erp-button--secondary erp-button--icon" :disabled="busy" :aria-label="tr('Fechar')" @click="close">×</button></header>
      <form class="variants-form" @submit.prevent="submit">
        <div class="erp-dialog__body variants-body">
          <p v-if="loading" role="status">{{ tr('Carregando...') }}</p>
          <p v-if="error" role="alert" class="variant-error">{{ error }}</p>
          <button v-if="!context && !loading" type="button" class="erp-button erp-button--secondary" @click="load">{{ tr('Tentar novamente') }}</button>
          <template v-if="context">
            <div class="variant-source"><img v-if="context.source.image_data" :src="context.source.image_data" :alt="tr('Foto do produto')" /><div><strong>{{ context.source.name }}</strong><p>{{ context.source.color || '—' }} · {{ context.source.size || '—' }}</p><small>{{ tr('A foto e os dados salvos serão reutilizados. O estoque original não será copiado.') }}</small></div></div>
            <fieldset :disabled="busy || uncertain">
              <label>{{ tr('Nome do modelo') }}<input v-model="name" required minlength="2" maxlength="140" /></label>
              <label>{{ tr(mode === 'duplicate' ? 'Novo tamanho' : 'Tamanhos da grade') }}<input v-model="sizeText" required maxlength="500" :placeholder="mode === 'duplicate' ? '8' : '8; 9; 10; 11'" /></label>
              <small v-if="mode === 'grade'">{{ tr('Separe por ponto e vírgula. Para meio número, use 8.5.') }}</small>
              <div v-if="mode === 'grade'" class="variant-presets"><button v-for="preset in presets" :key="preset.label" type="button" class="erp-button erp-button--secondary erp-button--sm" @click="sizeText = preset.sizes.join('; ')">{{ preset.label }}</button></div>
              <label>{{ tr('Código base (opcional)') }}<input v-model="barcode" maxlength="140" /></label>
              <small>{{ tr('Informe o código sem tamanho; ele receberá o tamanho ao final. Vazio: novos itens sem código de barras.') }}</small>
              <small>{{ tr('Código do produto original') }}: {{ context.source.barcode || '—' }}</small>
              <div class="variant-fields"><label>{{ tr('Quantidade por novo tamanho') }}<input v-model.number="quantity" type="number" min="0" max="1000000" step="1" required /></label><label>{{ tr('Local do estoque') }}<select v-model="location"><option value="loja">{{ tr('Loja') }}</option><option value="deposito">{{ tr('Depósito') }}</option></select></label></div>
              <ul class="variant-preview"><li v-for="size in sizes" :key="size"><strong>{{ name }} {{ size }}</strong><span v-if="exists(size)">{{ tr(existingItem(size)?.is_active === false ? 'Já cadastrado e inativo: estoque preservado' : 'Já cadastrado: estoque preservado') }}</span><span v-else>{{ barcode.trim() ? barcode.trim() + size : '—' }} · {{ quantity }} {{ tr('unidades') }}</span></li></ul>
              <p>{{ tr('Novos tamanhos: {count}', { count: missing.length }) }}</p>
              <label class="variant-confirm"><input v-model="confirmed" type="checkbox" />{{ tr('Conferi os tamanhos, os códigos e o estoque dos novos itens.') }}</label>
            </fieldset>
            <button v-if="uncertain" type="button" class="erp-button erp-button--secondary" :disabled="loading" @click="load">{{ tr('Conferir tamanhos cadastrados') }}</button>
          </template>
        </div>
        <footer class="erp-dialog__footer"><button type="button" class="erp-button erp-button--secondary" :disabled="busy" @click="close">{{ tr('Cancelar') }}</button><button type="submit" class="erp-button erp-button--primary" :disabled="!ready">{{ tr(busy ? 'Salvando...' : 'Criar tamanhos') }}</button></footer>
      </form>
    </section>
  </div>
</template>
<script setup lang="ts">
import { isAxiosError } from 'axios'
import { vErpDialog } from '@/directives/erpDialog'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { inventoryVariantsAPI, type VariantContext, type VariantResult } from '@/services/inventoryVariants'
import { GRADE_PRESETS, HIDDEN_PRESETS_KEY, readCustomPresets, readHiddenOptions, optionKey } from '@/services/inventoryGradeOptions'
import { useInventoryI18n } from './i18n'
const props = defineProps<{ itemId: string; mode: 'duplicate' | 'grade' }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'saved', result: VariantResult): void }>()
const { tr } = useInventoryI18n()
const context = ref<VariantContext>(), loading = ref(false), busy = ref(false), uncertain = ref(false), error = ref('')
const name = ref(''), sizeText = ref(''), barcode = ref(''), quantity = ref(0), location = ref<'loja' | 'deposito'>('loja'), confirmed = ref(false)
const title = computed(() => tr(props.mode === 'duplicate' ? 'Duplicar produto' : 'Adicionar grade'))
const hidden = readHiddenOptions(HIDDEN_PRESETS_KEY, GRADE_PRESETS.map(p => p.label))
const presets = [...GRADE_PRESETS.filter(p => !hidden.includes(optionKey(p.label))), ...readCustomPresets()]
const sizes = computed(() => [...new Set((props.mode === 'duplicate' ? [sizeText.value] : sizeText.value.split(/[;,\s]+/)).map(s => s.trim().toUpperCase()).filter(Boolean))])
const existingItem = (size: string) => context.value?.existing.find(row => optionKey(row.size || '') === optionKey(size))
const exists = (size: string) => !!existingItem(size)
const missing = computed(() => sizes.value.filter(s => !exists(s)))
const ready = computed(() => !!context.value && !loading.value && !busy.value && !uncertain.value && confirmed.value && name.value.trim().length >= 2 && sizes.value.length <= 50 && sizes.value.every(s => s.length <= 50) && missing.value.length > 0 && Number.isInteger(quantity.value) && quantity.value >= 0 && quantity.value <= 1000000)
watch([name, sizeText, barcode, quantity, location], () => { confirmed.value = false })
let disposed = false
onBeforeUnmount(() => { disposed = true })
function apiError(reason: unknown) {
  const detail = isAxiosError(reason) ? reason.response?.data?.detail : null
  return typeof detail === 'string' ? tr(detail) : ''
}
function close() { if (!busy.value) emit('close') }
async function load() {
  loading.value = true; error.value = ''; confirmed.value = false
  try {
    const value = await inventoryVariantsAPI.context(props.itemId)
    if (disposed) return
    context.value = value; name.value = value.model_name; uncertain.value = false
  } catch (reason) { error.value = apiError(reason) || tr('Não foi possível carregar o produto. Tente novamente.') }
  finally { loading.value = false }
}
async function submit() {
  if (!ready.value || !context.value) return
  busy.value = true; error.value = ''
  try {
    const result = await inventoryVariantsAPI.create(props.itemId, { sizes: sizes.value, model_name: name.value.trim(), base_barcode: barcode.value.trim() || null, source_version: context.value.source_version, initial_stock: quantity.value, stock_location: location.value, confirm: true })
    emit('saved', result)
  } catch (reason) {
    uncertain.value = true; confirmed.value = false
    error.value = [apiError(reason), tr('Não foi possível confirmar a operação. Confira os tamanhos cadastrados antes de continuar; os existentes não receberão estoque novamente.')].filter(Boolean).join(' ')
  } finally { busy.value = false }
}
onMounted(load)
</script>
<style scoped>
.erp-dialog-backdrop { position:fixed; inset:0; z-index:1100; display:flex; align-items:center; justify-content:center; }
.variants-modal{width:min(640px,100%);max-height:90dvh;display:flex;flex-direction:column}.variants-form{display:flex;flex-direction:column;min-height:0}.variants-body{overflow:auto}.variant-source{display:flex;gap:12px;margin-bottom:18px}.variant-source img{width:76px;height:90px;object-fit:contain;border-radius:10px}.variant-source p{margin:5px 0}fieldset{border:0;padding:0;margin:0;display:grid;gap:12px;min-width:0}label{display:grid;gap:6px;font-size:.875rem;font-weight:600}input:not([type=checkbox]),select{width:100%;min-width:0;box-sizing:border-box;padding:9px 11px;border:1px solid #cbd5e1;border-radius:8px;font:inherit}small{color:#64748b;display:block;line-height:1.4}.variant-fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}.variant-presets{display:flex;flex-wrap:wrap;gap:6px}.variant-preview{margin:0;padding:0;list-style:none;display:grid;gap:8px}.variant-preview li{display:grid;gap:4px;padding:10px;border-radius:8px;background:#f1f5f9;overflow-wrap:anywhere}.variant-preview span{font-size:.8rem;color:#475569}.variant-confirm{display:flex;align-items:flex-start;line-height:1.5}.variant-confirm input{margin-top:4px;flex-shrink:0}.variant-error{color:#b91c1c}.erp-dialog__header h2{font-size:1.15rem;margin:0}@media(max-width:480px){.variants-modal{max-height:94dvh}.variant-fields{grid-template-columns:1fr}.erp-dialog__footer{flex-wrap:wrap}}
</style>
