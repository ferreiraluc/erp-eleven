<template>
  <div id="app">
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

onMounted(() => {
  // Load stored authentication data on app startup
  authStore.loadStoredAuth()
})
</script>

<style>
/* Global styles are handled in main.css */
</style>
