<template>
  <div id="app">
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { RouterView, useRouter } from 'vue-router'
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

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
