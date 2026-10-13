<template>
  <Teleport to="body">
    <div class="rate-overlay erp-dialog-backdrop" @click.self="close">
      <section v-erp-dialog class="erp-dialog erp-dialog--sm">
        <header class="erp-dialog__header">
          <h2>{{ uiText('Taxas de Câmbio') }}</h2>
          <button type="button" data-dialog-close class="erp-button erp-button--ghost erp-button--icon"
            :disabled="saving" :aria-label="uiText('Fechar')" @click="close">×</button>
        </header>
        <form class="erp-dialog__form" @submit.prevent="save">
          <div class="erp-dialog__body">
            <p class="rate-note">{{ uiText('Câmbio compartilhado em todo o ERP.') }}</p>
            <p v-if="loading" role="status">{{ uiText('Carregando taxas…') }}</p>
            <div v-else-if="!ready" role="alert">
              <p>{{ store.error || uiText('Erro ao carregar taxas de câmbio') }}</p>
              <button type="button" class="erp-button erp-button--secondary" @click="load">{{ uiText('Tentar novamente') }}</button>
            </div>
            <div v-else class="rate-grid">
              <label v-for="field in fields" :key="field.key">
                {{ field.label }}
                <DecimalInput v-model="draft[field.key]" :aria-label="field.label" :disabled="!store.canEdit || saving" :required="field.key !== 'eur_to_brl'" />
              </label>
            </div>
            <p v-if="error" class="rate-error" role="alert">{{ error }}</p>
          </div>
          <footer class="erp-dialog__footer">
            <button type="button" class="erp-button erp-button--secondary" :disabled="saving" @click="close">{{ uiText('Cancelar') }}</button>
            <button v-if="store.canEdit" type="submit" class="erp-button erp-button--primary" :disabled="!ready || saving || !valid">
              {{ uiText(saving ? 'Salvando…' : 'Salvar Taxas') }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { useCurrencyStore } from '@/stores/currency'
import { uiText } from '@/i18n/uiText'
import DecimalInput from '@/components/forms/DecimalInput.vue'
const emit = defineEmits<{ close: []; saved: [] }>()
const store = useCurrencyStore(), loading = ref(true), ready = ref(false), saving = ref(false), error = ref('')
const draft = reactive({ usd_to_pyg: null as number | null, usd_to_brl: null as number | null, eur_to_usd: null as number | null, eur_to_brl: null as number | null })
type Key = keyof typeof draft
const fields = computed(() => [
  { key: 'usd_to_pyg' as Key, label: '🇺🇸 U$ → 🇵🇾 G$' },
  { key: 'usd_to_brl' as Key, label: '🇺🇸 U$ → 🇧🇷 R$' },
  { key: 'eur_to_usd' as Key, label: '🇪🇺 EUR → 🇺🇸 U$' },
  { key: 'eur_to_brl' as Key, label: '🇪🇺 EUR → 🇧🇷 R$' },
])
const valid = computed(() => fields.value.every(({ key }) => (key === 'eur_to_brl' && draft[key] === null) ||
  (draft[key] !== null && Number.isFinite(draft[key]) && draft[key]! > 0 && draft[key]! <= 99999999)))
let disposed = false
async function load() {
  loading.value = true; ready.value = false; error.value = ''
  const ok = await store.loadCurrentRates()
  if (disposed) return
  if (ok && store.currentRates) {
    for (const { key } of fields.value) draft[key] = store.currentRates[key]
    ready.value = true
  }
  loading.value = false
}
async function save() {
  if (!ready.value || !valid.value || saving.value || !store.canEdit) return
  saving.value = true; error.value = ''
  try {
    const changed = Object.fromEntries(fields.value.filter(({ key }) => draft[key] !== null && draft[key] !== store.currentRates?.[key]).map(({ key }) => [key, draft[key]]))
    if (Object.keys(changed).length) await store.updateRatesAPI(changed)
    if (!disposed) { emit('saved'); emit('close') }
  } catch (e: any) {
    if (!disposed) error.value = typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : e.message || uiText('Erro ao salvar taxas')
  } finally { saving.value = false }
}
function close() { if (!saving.value) emit('close') }
onMounted(load)
onUnmounted(() => { disposed = true })
</script>
<style scoped>
.rate-overlay { position: fixed; inset: 0; display: flex; z-index: 3000; }
.rate-note { margin: 0 0 16px; font-size: 13px; color: #64748b; }
.rate-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px 12px; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; font-weight: 600; min-width: 0; }
input { width: 100%; min-width: 0; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px; font: inherit; font-size: 16px; }
.rate-error { color: #b91c1c; font-size: 13px; }
@media (max-width: 350px) { .rate-grid { grid-template-columns: 1fr; } }
</style>
