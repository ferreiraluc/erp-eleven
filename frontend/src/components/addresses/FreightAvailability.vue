<template>
  <p v-if="availability === 'unavailable'" class="freight-status warning" role="status">{{ tr('Emissão de etiquetas temporariamente fora do ar. As solicitações pendentes serão consultadas automaticamente. Avisaremos quando puderem continuar.') }}</p>
  <p v-else-if="availability === 'configuration'" class="freight-status warning" role="alert">{{ tr('Confira o token, o contato técnico e as permissões da conta SuperFrete. Isso não impede a impressão de endereços A4.') }}</p>
  <p v-else-if="availability === 'unknown'" class="freight-status warning" role="status">{{ tr('Não foi possível verificar a integração agora. A consulta será repetida; seus endereços e impressões A4 continuam disponíveis.') }}</p>
  <p v-else-if="availability === 'available' && restored" class="freight-status restored" role="status">{{ tr('A SuperFrete voltou a responder. Confira o andamento das solicitações abaixo; pagamentos continuam sujeitos à confirmação.') }}</p>
</template>

<script setup lang="ts">
import { useAddressI18n } from './i18n'
defineProps<{ availability: string; restored?: boolean }>()
const { tr } = useAddressI18n()
</script>

<style scoped>
.freight-status { padding: .85rem 1rem; margin: 0 0 1rem; border: 1px solid; border-radius: 10px; line-height: 1.5; font-size: .875rem; }
.warning { color: #92400e; background: #fffbeb; border-color: #fde68a; }
.restored { color: #065f46; background: #ecfdf5; border-color: #a7f3d0; }
</style>
