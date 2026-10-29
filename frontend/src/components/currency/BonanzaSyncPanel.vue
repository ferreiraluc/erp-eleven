<template>
  <section class="bonanza-panel">
    <h2>{{ text('title') }}</h2>
    <p>{{ text('intro') }} <a href="https://www.bonanzacambios.com.py/?suc=2" target="_blank" rel="noopener">Bonanza · Jebai · Venta ↗</a></p>
    <p v-if="error || state?.last_error" role="alert">{{ error || text('failure') }}</p>
    <p v-if="state?.last_success">{{ text('last') }}: {{ new Date(state.last_success).toLocaleString() }}</p>
    <p v-if="state?.source_at">{{ text('published') }}: {{ new Date(state.source_at).toLocaleString() }}</p>
    <button class="erp-button" :class="state?.enabled ? 'erp-button--secondary' : 'erp-button--primary'" :disabled="busy || !state" @click="toggle">{{ text(busy ? 'loading' : state?.enabled ? 'pause' : 'enable') }}</button>
  </section>
</template>
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useCurrencyStore } from '@/stores/currency'
const messages = {
  pt: { title: 'Câmbio automático · Bonanza', intro: 'Dólar/guarani e dólar/real a cada 6 horas. Mantém a última cotação se a consulta falhar.', last: 'Última consulta concluída', published: 'Publicado pela Bonanza', failure: 'Não foi possível atualizar. As taxas anteriores foram preservadas.', pause: 'Pausar atualização automática', enable: 'Ativar Jebai · Venda', loading: 'Aguarde…' },
  es: { title: 'Cambio automático · Bonanza', intro: 'Dólar/guaraní y dólar/real cada 6 horas. Conserva la última cotización si falla la consulta.', last: 'Última consulta completada', published: 'Publicado por Bonanza', failure: 'No se pudo actualizar. Se conservaron las tasas anteriores.', pause: 'Pausar actualización automática', enable: 'Activar Jebai · Venta', loading: 'Espere…' },
  en: { title: 'Automatic rates · Bonanza', intro: 'USD/guarani and USD/real every 6 hours. Keeps the last quote if a request fails.', last: 'Last successful check', published: 'Published by Bonanza', failure: 'Rates could not be updated. Previous rates were kept.', pause: 'Pause automatic updates', enable: 'Enable Jebai · Venta', loading: 'Please wait…' },
}
const { t: text } = useI18n({ useScope: 'local', messages }), auth = useAuthStore(), currency = useCurrencyStore()
interface Status { enabled: boolean; last_success: string | null; source_at: string | null; last_error: string | null }
const state = ref<Status | null>(null), error = ref(''), busy = ref(false)
let generation = 0
async function request(enabled?: boolean) {
  if (!auth.isOwner || busy.value) return
  const current = ++generation, token = auth.token
  busy.value = true; error.value = ''
  try {
    const config = { headers: { Authorization: token ? `Bearer ${token}` : null } }
    const { data } = enabled === undefined ? await api.get<Status>('/api/exchange-rates/bonanza', config) : await api.put<Status>('/api/exchange-rates/bonanza', { enabled }, config)
    if (current !== generation || token !== auth.token) return
    state.value = data
    if (enabled && !data.last_error) await currency.loadCurrentRates()
  } catch { if (current === generation) error.value = text('failure') }
  finally { if (current === generation) busy.value = false }
}
function toggle() { void request(!state.value?.enabled) }
watch(() => auth.token, () => { generation++; state.value = null; busy.value = false })
onBeforeUnmount(() => { generation++ })
onMounted(() => request())
</script>
<style scoped>
.bonanza-panel { background: white; border: 1px solid #e2e8f0; border-radius: 14px; padding: 24px; }
h2 { font-size: 18px; margin: 0 0 8px; } p { font-size: .85rem; color: #64748b; line-height: 1.6; } a { color: #2563eb; } [role=alert] { color: #b91c1c; }
@media(max-width:600px) { .bonanza-panel { padding:18px; } }
</style>
