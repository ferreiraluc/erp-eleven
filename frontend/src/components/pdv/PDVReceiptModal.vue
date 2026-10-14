<template>
  <Teleport to="body">
    <div class="receipt-overlay erp-dialog-backdrop" @click.self="emit('close')" @keydown.esc.stop.prevent="emit('close')">
      <section v-erp-dialog class="receipt-modal erp-dialog erp-dialog--sm" :aria-label="uiText('Ticket da venda')">
        <header class="receipt-actions erp-dialog__header no-print">
          <strong>{{ uiText('Ticket da venda') }}</strong>
          <button type="button" data-dialog-close class="erp-button erp-button--ghost erp-button--icon" :aria-label="uiText('Fechar')" @click="emit('close')">×</button>
        </header>
        <PDVReceiptDelivery :sale-id="sale.id" />
        <div class="receipt-scroll erp-dialog__body">
          <p v-if="loading" class="receipt-message" role="status">{{ uiText('Carregando…') }}</p>
          <div v-if="error" role="alert" class="receipt-message no-print">{{ error }} <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="load">{{ uiText('Tentar novamente') }}</button></div>
          <article v-if="data" class="receipt-paper" lang="es" id="receipt-print-area">
            <header class="receipt-store"><h2>{{ data.title }}</h2><p>{{ data.location }}</p><p class="receipt-email">{{ data.email }}</p><p class="receipt-identity">Ticket: <b>{{ data.code }}</b> | {{ data.date }}</p></header>
            <p v-if="data.copy" class="receipt-status">COPIA</p>
            <p v-if="data.status_changed" class="receipt-status">{{ data.status }}</p>
            <hr />
            <section aria-label="Productos">
              <div v-for="(item, index) in data.items" :key="index" class="receipt-item">
                <strong>{{ item.name }}</strong><small v-if="item.meta">{{ item.meta }}</small>
                <div class="receipt-pair"><span>{{ item.calculation }}</span><b>{{ item.total }}</b></div>
                <small v-if="item.discount">Descuento del artículo: {{ item.discount }}</small>
                <small v-if="item.returned">Cantidad devuelta: {{ item.returned }}</small>
              </div>
            </section>
            <hr />
            <div class="receipt-pair"><span>Subtotal</span><span>{{ data.subtotal }}</span></div>
            <div v-if="data.discount" class="receipt-pair"><span>Descuento</span><span>{{ data.discount }}</span></div>
            <div class="receipt-pair receipt-total"><strong>TOTAL</strong><strong>{{ data.total }}</strong></div>
            <div v-if="data.refunded" class="receipt-pair"><span>Importe devuelto</span><span>{{ data.refunded }}</span></div>
            <hr />
            <strong>PAGO</strong>
            <div v-for="(payment, index) in data.payments" :key="index" class="receipt-payment">
              <div class="receipt-pair"><span>{{ payment.label }}</span><span>{{ payment.amount }}</span></div>
              <div v-if="payment.equivalent" class="receipt-pair receipt-small"><span>Equivalente</span><span>{{ payment.equivalent }}</span></div>
            </div>
            <div v-if="data.change" class="receipt-pair"><span>Cambio</span><strong>{{ data.change }}</strong></div>
            <p>Vendedor: {{ data.seller }}</p><p>Cliente: {{ data.customer }}</p>
            <hr />
            <figure class="receipt-barcode"><img :src="data.barcode" :alt="'Código de barras del ticket '+data.code" /><figcaption>{{ data.code }}</figcaption></figure>
            <p class="receipt-full-id">ID: {{ data.sale_id }}</p>
            <hr />
            <footer class="receipt-thanks"><p v-for="line in data.footer" :key="line">{{ line }}</p></footer>
          </article>
        </div>
        <footer class="receipt-actions erp-dialog__footer no-print">
          <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="!data" @click="printReceipt">{{ uiText('🖨 Neste aparelho') }}</button>
          <button type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="!data || saving" @click="savePDF">{{ uiText(saving ? 'Carregando…' : '📄 Salvar PDF') }}</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { uiText } from '@/i18n/uiText'
import { pdvReceipts, type ReceiptPreview } from '@/services/pdvReceipts'
import { saleError } from '@/services/pdvManagement'
import PDVReceiptDelivery from './PDVReceiptDelivery.vue'
const props = defineProps<{ sale: { id: string } }>()
const emit = defineEmits<{ (e: 'close'): void }>()
const data = ref<ReceiptPreview | null>(null), loading = ref(true), saving = ref(false), error = ref('')
let mounted = true
async function load() {
  loading.value = true; error.value = ''
  try { const result = await pdvReceipts.preview(props.sale.id); if (mounted) data.value = result }
  catch (e) { if (mounted) error.value = saleError(e) }
  finally { if (mounted) loading.value = false }
}
function printReceipt() { window.print() }
async function savePDF() {
  if (saving.value) return
  saving.value = true; error.value = ''
  try {
    const pdf = await pdvReceipts.pdf(props.sale.id)
    if (!mounted) return
    const url = URL.createObjectURL(pdf), link = document.createElement('a')
    link.href = url; link.download = `eleven-ticket-${data.value?.code || props.sale.id}.pdf`; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  } catch (e) { if (mounted) error.value = saleError(e) }
  finally { if (mounted) saving.value = false }
}
onMounted(load)
onUnmounted(() => { mounted = false })
</script>
<style scoped>
.receipt-overlay{position:fixed;inset:0;z-index:13000;background:#0f172a99;display:flex;align-items:center;justify-content:center;padding:12px}.receipt-modal{width:min(460px,100%);max-height:calc(100dvh - 24px);display:flex;flex-direction:column;background:#f1f5f9;border-radius:16px;overflow:hidden;box-shadow:0 20px 60px #0003}.receipt-actions{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:12px 16px;background:white;flex-shrink:0}.receipt-scroll{overflow:auto;padding:16px;min-height:0}.receipt-message{font-size:14px;padding:12px}.receipt-paper{box-sizing:border-box;max-width:340px;margin:auto;padding:22px 16px;background:white;color:#111;font:13px/1.5 'Courier New',monospace;overflow-wrap:anywhere;box-shadow:0 2px 8px #0001}.receipt-paper p{margin:6px 0}.receipt-store{text-align:center}.receipt-store h2{font:900 36px/1.2 Arial,sans-serif;letter-spacing:1px;margin:0 0 14px}.receipt-email,.receipt-identity{font-size:11px}.receipt-paper hr{border:0;border-top:1px dashed #111;margin:14px 0}.receipt-item{margin:12px 0}.receipt-item strong,.receipt-item small{display:block}.receipt-item small,.receipt-small{font-size:11px}.receipt-pair{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:5px 0}.receipt-pair>:last-child{text-align:right;flex-shrink:0;max-width:55%}.receipt-total{font-size:17px;font-weight:700;margin-top:10px}.receipt-status{text-align:center;font-weight:bold}.receipt-barcode{margin:14px 0 6px;text-align:center}.receipt-barcode img{width:100%;height:auto;display:block;image-rendering:crisp-edges}.receipt-barcode figcaption{font-size:12px;letter-spacing:2px;margin-top:5px}.receipt-full-id{font-size:10px;overflow-wrap:anywhere;text-align:center}.receipt-thanks{text-align:center;font-size:12px}
@media print{.no-print{display:none!important}.receipt-overlay{position:absolute;inset:0;display:block;background:white;padding:0}.receipt-modal,.receipt-scroll{display:block;max-height:none;height:auto;overflow:visible;padding:0;background:white;box-shadow:none}.receipt-paper{width:72mm;max-width:none;box-shadow:none;margin:0;padding:3mm}.receipt-item,.receipt-barcode{break-inside:avoid}:global(body>#app),:global(body>.sale-overlay){display:none!important}@page{size:80mm auto;margin:2mm}}
</style>
