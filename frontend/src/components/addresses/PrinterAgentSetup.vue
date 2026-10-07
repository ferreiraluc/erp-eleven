<template>
  <details class="printer-setup">
    <summary>{{ tr('Configurar impressora da loja') }}</summary>
    <p><strong>{{ tr('Impressora') }}:</strong> {{ device?.name || tr('Nenhuma impressora ativa') }}</p>
    <p>{{ tr('Troca para Samsung SL-M2035W: use a impressora que já funciona no Windows da loja.') }}</p>
    <ol>
      <li>{{ tr('Feche o Eleven Impressao e extraia todos os arquivos do novo pacote no mesmo computador e usuário Windows.') }}</li>
      <li>{{ tr('Execute Instalar.cmd, selecione a Samsung na lista e pressione Enter na credencial para manter a atual.') }}</li>
      <li>{{ tr('Abra Eleven Impressao novamente. O nome será atualizado aqui ao conectar; a fila e o histórico serão preservados.') }}</li>
    </ol>
    <p>{{ tr('A instalação não imprime. Ao abrir o agente, os trabalhos pendentes voltam a ser processados.') }}</p>
    <div class="actions">
      <button class="erp-button erp-button--primary erp-button--sm" :disabled="downloading" @click="download">
        {{ tr(downloading ? 'Baixando…' : 'Baixar agente Windows') }}
      </button>
      <button class="erp-button erp-button--secondary erp-button--sm" @click="$emit('refresh')">{{ tr('Atualizar') }}</button>
      <a href="https://www.samsung.com/sec/support/model/SL-M2035W/" target="_blank" rel="noopener noreferrer">{{ tr('Suporte oficial Samsung') }}</a>
    </div>
    <p v-if="error" role="alert" class="download-error">{{ tr('Não foi possível baixar o agente. Tente novamente.') }}</p>
  </details>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import api from '@/services/api'
import type { Overview } from './types'
import { useAddressI18n } from './i18n'
defineProps<{ device?: Overview['devices'][number] }>()
defineEmits<{ refresh: [] }>()
const { tr } = useAddressI18n()
const downloading = ref(false), error = ref(false)
async function download() {
  if (downloading.value) return
  downloading.value = true; error.value = false
  try {
    const response = await api.get('/api/printing/agent-package', { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url; link.download = 'Eleven-Impressao-Windows.zip'
    document.body.append(link); link.click(); link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch { error.value = true } finally { downloading.value = false }
}
</script>

<style scoped>
.printer-setup{margin:-8px 0 20px;padding:14px 18px;border:1px solid #e2e8f0;border-radius:12px;background:#fff;font-size:13px;color:#475569;overflow-wrap:anywhere}
summary{cursor:pointer;font-weight:600;color:#2563eb}
p,ol{margin:12px 0}ol{padding-left:20px}li{margin:8px 0}
.actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.actions a{color:#2563eb}
.download-error{color:#be123c}
</style>
