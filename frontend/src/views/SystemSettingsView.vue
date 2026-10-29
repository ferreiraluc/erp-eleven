<template>
  <div class="system-settings">
    <ModuleHeader :title="$t('footer.settings')" />
    <main class="settings-content">
      <section class="settings-card" :aria-label="uiText('Impressora de tickets')">
        <div>
          <h2>{{ uiText('Impressora de tickets') }}</h2>
          <p>{{ uiText('Tickets do PDV em uma fila própria. A impressora de endereços A4 continua separada.') }}</p>
        </div>
        <button type="button" class="erp-button erp-button--primary" @click="showPrinterModal = true">
          {{ uiText('Configurar impressora de tickets') }}
        </button>
      </section>
      <WoncaMonitoringPanel />
      <BonanzaSyncPanel />
    </main>
    <PDVPrinterModal v-if="showPrinterModal" @close="showPrinterModal = false" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ModuleHeader from '@/components/ModuleHeader.vue'
import PDVPrinterModal from '@/components/pdv/PDVPrinterModal.vue'
import { uiText } from '@/i18n/uiText'
import WoncaMonitoringPanel from '@/components/tracking/WoncaMonitoringPanel.vue'
import BonanzaSyncPanel from '@/components/currency/BonanzaSyncPanel.vue'

const showPrinterModal = ref(false)
</script>

<style scoped>
.system-settings { min-height: 100vh; background: #f8fafc; color: #172033; }
.settings-content { width: min(100%, 920px); margin: 0 auto; padding: 8px 24px 48px; box-sizing: border-box; display: grid; gap: 20px; }
.settings-card { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 24px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; }
.settings-card h2 { margin: 0 0 8px; font-size: 18px; }
.settings-card p { margin: 0; color: #64748b; line-height: 1.5; }
.settings-card button { flex: none; }
@media (max-width: 600px) {
  .settings-content { padding: 0 12px 32px; }
  .settings-card { align-items: stretch; flex-direction: column; gap: 16px; padding: 18px; }
}
</style>
