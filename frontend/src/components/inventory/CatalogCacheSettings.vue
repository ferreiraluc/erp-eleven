<template>
  <section class="cache-settings" :aria-label="uiText('Busca rápida neste aparelho')">
    <h2>{{ uiText('Busca rápida neste aparelho') }}</h2>
    <p>
      {{
        uiText(
          'Índice local de produtos para agilizar as consultas no estoque e no PDV. Fotos e saldos não são armazenados; vendas continuam confirmadas no servidor.',
        )
      }}
    </p>
    <p v-if="!state.supported" role="status">
      {{ uiText('Este navegador não oferece armazenamento local para a busca.') }}
    </p>
    <template v-else>
      <p role="status">
        {{ state.count.toLocaleString() }} {{ uiText('produtos disponíveis na consulta local') }} ·
        {{ (state.bytes / 1048576).toFixed(1) }} MB
        <span v-if="state.syncedAt"> · {{ new Date(state.syncedAt).toLocaleString() }}</span>
      </p>
      <p v-if="state.loading" role="status">
        {{ uiText('Preparando o índice em segundo plano… Você pode continuar usando o sistema.') }}
      </p>
      <p v-else-if="state.error" role="status">
        {{
          uiText(
            'A cópia local não foi atualizada. A última cópia completa foi preservada. Tente novamente com uma conexão estável.',
          )
        }}
      </p>
      <div>
        <button class="erp-button erp-button--secondary" :disabled="state.loading" @click="refresh">
          {{ uiText('Atualizar consulta local') }}
        </button>
        <button
          class="erp-button erp-button--ghost"
          :disabled="state.loading"
          @click="clearCatalogIndex"
        >
          {{ uiText('Limpar cópia deste aparelho') }}
        </button>
      </div>
    </template>
  </section>
</template>
<script setup lang="ts">
import { onMounted } from 'vue'
import {
  catalogCacheState as state,
  prepareCatalogIndex,
  refreshCatalogIndex,
  clearCatalogIndex,
} from '@/services/catalogIndex'
import { useAuthStore } from '@/stores/auth'
import { uiText } from '@/i18n/uiText'
const auth = useAuthStore()
async function refresh() {
  await prepareCatalogIndex(auth.user?.id)
  await refreshCatalogIndex(true)
}
onMounted(() => prepareCatalogIndex(auth.user?.id))
</script>
<style scoped>
.cache-settings {
  padding: 24px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: white;
}
.cache-settings h2 {
  margin: 0 0 8px;
  font-size: 18px;
}
.cache-settings p {
  color: #64748b;
  line-height: 1.5;
}
.cache-settings button {
  margin-top: 8px;
}
</style>
