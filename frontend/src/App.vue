<template>
  <div id="app">
    <RouterView />
    <NotificationToast />
  </div>
</template>

<script setup lang="ts">
import { RouterView, useRouter } from 'vue-router'
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import NotificationToast from '@/components/NotificationToast.vue'

const authStore = useAuthStore()
const router = useRouter()

onMounted(async () => {
  // Load stored authentication data on app startup
  authStore.loadStoredAuth()
  
  // Ensure router is ready
  await router.isReady()
})
</script>

<style>
/* Global styles are handled in main.css */
</style>
