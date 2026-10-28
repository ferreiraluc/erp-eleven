<template>
  <section v-if="!center.pushActive || center.pushError" class="notification-delivery" :aria-label="n('deliveryStatus')">
    <p v-if="center.restoring" role="status">{{ n('reconnecting') }}</p>
    <template v-else>
      <p>{{ n(center.support === 'ready' ? 'companyDelivery' : center.support) }}</p>
      <p v-if="center.pushError" class="notification-error" role="alert">{{ center.pushError }}</p>
      <button v-if="!center.pushActive && center.support === 'ready'" type="button"
        class="erp-button erp-button--primary erp-button--sm" :disabled="center.pushBusy" @click="center.enablePush">
        {{ n(center.pushBusy ? 'loading' : 'enable') }}
      </button>
    </template>
  </section>
</template>
<script setup lang="ts">
import { useNotificationCenter } from '@/stores/notificationCenter'
import { notificationText as n } from '@/services/notificationText'
const center = useNotificationCenter()
</script>
<style scoped>
.notification-delivery{display:grid;justify-items:start;gap:8px;padding:12px;border:1px solid #dbeafe;border-radius:12px;background:#eff6ff;color:#475569}
.notification-delivery p{margin:0;font-size:12px;line-height:1.5;overflow-wrap:anywhere}
.notification-error{color:#b91c1c}
</style>
