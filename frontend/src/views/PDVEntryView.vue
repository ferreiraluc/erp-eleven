<template>
  <OrderCheckout v-if="pedidoId" :key="pedidoId" :pedido-id="pedidoId" />
  <PDVView v-else />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PDVView from './PDVView.vue'
import OrderCheckout from '@/components/pdv/OrderCheckout.vue'

const route = useRoute()
const pedidoId = computed(() => typeof route.query.pedido_id === 'string' ? route.query.pedido_id : '')
</script>
