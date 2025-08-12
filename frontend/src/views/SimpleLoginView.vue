<template>
  <div style="padding: 20px; background: blue; color: white;">
    <h1>LOGIN SIMPLES FUNCIONANDO!</h1>
    <p>Este é o LoginView sem i18n e authStore</p>
    <form>
      <div>
        <label>Email:</label>
        <input type="email" v-model="email" />
      </div>
      <div>
        <label>Senha:</label>
        <input type="password" v-model="password" />
      </div>
      <button type="submit">Entrar</button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

console.log('SimpleLoginView component is being rendered')

const email = ref('')
const password = ref('')
</script>