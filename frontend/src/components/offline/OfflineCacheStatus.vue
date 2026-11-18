<template>
  <section class="offline-cache-status" :aria-label="t('Consulta offline', 'Consulta sin conexión', 'Offline catalog')">
    <div>
      <strong>{{ t('Consulta offline', 'Consulta sin conexión', 'Offline catalog') }}</strong>
      <p v-if="!state.supported">{{ t('Armazenamento indisponível neste aparelho.', 'Almacenamiento no disponible en este dispositivo.', 'Storage is unavailable on this device.') }}</p>
      <p v-else-if="state.loading" role="status">{{ t('Atualizando a cópia salva…', 'Actualizando la copia guardada…', 'Updating the saved copy…') }}</p>
      <p v-else-if="state.syncedAt">
        {{ state.count.toLocaleString() }} {{ t('produtos', 'productos', 'products') }} · {{ dateTime(state.syncedAt) }}
        <span> · {{ state.thumbnailCount.toLocaleString() }} {{ t('miniaturas', 'miniaturas', 'thumbnails') }}</span>
      </p>
      <p v-else>{{ t('Preparando produtos para consultar sem internet.', 'Preparando productos para consultar sin internet.', 'Preparing products for offline browsing.') }}</p>
      <p v-if="state.error" role="status">{{ t('Não foi possível atualizar. A última cópia completa foi preservada.', 'No se pudo actualizar. Se conservó la última copia completa.', 'Update failed. The last complete copy was preserved.') }}</p>
    </div>
    <button v-if="state.supported" class="erp-button erp-button--secondary erp-button--sm" :disabled="state.loading || preparing" @click="refresh">
      {{ t('Atualizar', 'Actualizar', 'Refresh') }}
    </button>
  </section>
</template>
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { storedToken, tokenIsCurrent } from '@/services/sessionStorage'
import { offlineCatalogState as state, prepareOfflineCatalog, refreshOfflineCatalog } from '@/services/offlineCatalog'
import { formatDateTime as dateTime } from '@/utils/datetime'
const { locale } = useI18n()
const auth = useAuthStore(), preparing = ref(false)
const t = (pt: string, es: string, en: string) => locale.value.startsWith('es') ? es : locale.value.startsWith('en') ? en : pt
async function refresh() {
  const userId = auth.user?.id, token = auth.token
  if (!auth.isAuthenticated || !userId || !token || preparing.value) return
  preparing.value = true
  try {
    await prepareOfflineCatalog({ userId, token, isCurrent: () => auth.isAuthenticated && auth.user?.id === userId && storedToken() === token && tokenIsCurrent(token) })
    await refreshOfflineCatalog()
  } finally { preparing.value = false }
}
</script>
<style scoped>
.offline-cache-status { display:flex;align-items:center;justify-content:space-between;gap:16px;max-width:1200px;margin:12px auto 24px;padding:16px 20px;border:1px solid var(--color-border,#e2e8f0);border-radius:16px;background:var(--color-surface,#fff);font-size:13px; }
.offline-cache-status p { margin:4px 0 0;color:#64748b;line-height:1.5; }
.offline-cache-status button { flex-shrink:0; }
@media(max-width:600px) { .offline-cache-status { margin:8px 12px 20px;padding:12px; } }
</style>
