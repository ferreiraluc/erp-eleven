<template>
  <div class="receipt-overlay erp-dialog-backdrop" @click.self="$emit('close')">
    <div v-erp-dialog class="receipt-modal erp-dialog erp-dialog--sm" :aria-label="uiText('Recibo')">
      <div class="receipt-actions no-print erp-dialog__header">
        <button class="receipt-btn-print erp-button erp-button--primary" @click="printReceipt">{{ uiText(`🖨 Imprimir`) }}</button>
        <button class="receipt-btn-pdf erp-button erp-button--secondary" @click="savePDF">{{ uiText(`📄 Salvar PDF`) }}</button>
        <button data-dialog-close :aria-label="uiText('Fechar')" class="receipt-btn-close erp-button erp-button--secondary" @click="$emit('close')">{{ uiText(`Fechar`) }}</button>
      </div>

      <!-- Receipt body (printable) -->
      <div class="receipt-paper erp-dialog__body" ref="receiptRef" id="receipt-print-area">
        <!-- Header -->
        <div class="receipt-store">
          <div class="receipt-logo">ELEVEN</div>
          <p class="receipt-store-sub">{{ uiText(`Moda & Vestuário`) }}</p>
          <p class="receipt-store-info">Ciudad del Este, Paraguay</p>
          <p class="receipt-date">{{ formatDate(sale.created_at) }}</p>
          <p class="receipt-id">{{ uiText(`Venda #`) }}{{ sale.id.slice(-8).toUpperCase() }}</p>
        </div>

        <div class="receipt-divider">- - - - - - - - - - - - - - - - - -</div>

        <!-- Items -->
        <div class="receipt-items">
          <div v-for="item in sale.items" :key="item.id" class="receipt-item">
            <div class="receipt-item-name">
              {{ item.item_name }}
              <span v-if="item.is_avulso" class="receipt-avulso-tag">{{ uiText(`avulso`) }}</span>
            </div>
            <div class="receipt-item-meta">
              <span v-if="item.item_size || item.item_color">
                {{ [item.item_size, item.item_color].filter(Boolean).join(' · ') }}
              </span>
            </div>
            <div class="receipt-item-calc">
              <span>{{ item.quantity }}x {{ fmtGs(item.unit_price_gs) }}</span>
              <span v-if="item.discount_gs > 0" class="receipt-item-disc">-{{ fmtGs(item.discount_gs) }}</span>
              <span class="receipt-item-total">{{ fmtGs(item.total_gs) }}</span>
            </div>
          </div>
        </div>

        <div class="receipt-divider">- - - - - - - - - - - - - - - - - -</div>

        <!-- Totals -->
        <div class="receipt-totals">
          <div class="receipt-total-row">
            <span>{{ uiText(`Subtotal`) }}</span>
            <span>{{ fmtGs(sale.subtotal_gs) }}</span>
          </div>
          <div v-if="sale.desconto_gs > 0" class="receipt-total-row receipt-discount-row">
            <span>{{ uiText(`Desconto`) }}</span>
            <span>-{{ fmtGs(sale.desconto_gs) }}</span>
          </div>
          <div class="receipt-total-row receipt-grand-total">
            <span>{{ uiText(`TOTAL`) }}</span>
            <span>{{ fmtGs(sale.total_gs) }}</span>
          </div>
        </div>

        <div class="receipt-divider">- - - - - - - - - - - - - - - - - -</div>

        <!-- Payments -->
        <div class="receipt-payments">
          <p class="receipt-section-label">{{ uiText(`Pagamento`) }}</p>
          <div v-for="p in sale.payments" :key="p.id" class="receipt-payment-row">
            <span>{{ methodLabel(p.method) }}</span>
            <span>
              <template v-if="p.currency !== 'GS'">
                {{ p.currency }} {{ fmtNum(p.amount_original) }} →
              </template>
              {{ fmtGs(p.amount_gs) }}
            </span>
          </div>
          <div v-if="troco > 0" class="receipt-payment-row receipt-troco-row">
            <span>{{ uiText(`Troco`) }}</span>
            <span>{{ fmtGs(troco) }}</span>
          </div>
        </div>

        <div v-if="sale.cliente_nome" class="receipt-client"> {{ uiText(`Cliente:`) }} {{ sale.cliente_nome }}
        </div>

        <div class="receipt-divider">- - - - - - - - - - - - - - - - - -</div>

        <div class="receipt-footer">
          <p>{{ uiText(`Obrigado pela sua compra!`) }}</p>
          <p>{{ uiText(`Volte sempre ✨`) }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import { uiText, uiLocale } from '@/i18n/uiText'
import { ref, computed } from 'vue'
import type { PdvSaleResponse } from '@/services/api'

const props = defineProps<{ sale: PdvSaleResponse }>()
defineEmits<{ (e: 'close'): void }>()

const receiptRef = ref<HTMLElement>()

const PAYMENT_LABELS = computed<Record<string, string>>(() => ({
  cash_gs: uiText(`Dinheiro G$`), cash_brl: uiText(`Dinheiro R$`), cash_usd: uiText(`Dinheiro U$`),
  cash_eur: uiText(`Dinheiro €`), card: uiText(`Cartão`), pix: 'PIX',
  mercadopago: 'MercadoPago', transfer_br: uiText(`Transf. Brasil`),
  transfer_py: uiText(`Transf. Paraguai`), pix_cambista: uiText(`PIX Cambista`),
  qr_py: uiText(`QR Paraguai`), tigo_money: 'Tigo Money', fiado: uiText(`Fiado`),
}))
function methodLabel(m: string) { return PAYMENT_LABELS.value[m] || m }

const troco = computed(() => {
  const paid = props.sale.payments.reduce((s, p) => s + p.amount_gs, 0)
  return Math.max(0, paid - props.sale.total_gs)
})

function fmtGs(v: number) {
  return 'G$ ' + Math.round(v).toLocaleString(uiLocale())
}
function fmtNum(v: number) {
  return v.toLocaleString(uiLocale(), { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}
function formatDate(s: string) {
  return new Date(s).toLocaleString(uiLocale(), {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function printReceipt() {
  window.print()
}

async function savePDF() {
  if (!receiptRef.value) return
  try {
    const html2canvas = (await import('html2canvas')).default
    const jsPDF = (await import('jspdf')).default
    const canvas = await html2canvas(receiptRef.value, { scale: 2, useCORS: true, backgroundColor: '#ffffff' })
    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: [80, canvas.height * 80 / canvas.width] })
    pdf.addImage(imgData, 'PNG', 0, 0, 80, canvas.height * 80 / canvas.width)
    pdf.save(`nota-eleven-${props.sale.id.slice(-8).toUpperCase()}.pdf`)
  } catch (e) {
    console.error('PDF error:', e)
    alert(uiText(`Erro ao gerar PDF. Tente usar o botão Imprimir.`))
  }
}
</script>

<style scoped>
.receipt-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 2000; padding: 1rem; box-sizing: border-box;
}
.receipt-modal {
  background: #f3f4f6; border-radius: 1rem;
  max-height: 95dvh; max-height: 95vh;
  overflow-y: auto; display: flex; flex-direction: column;
  box-shadow: 0 25px 70px rgba(0,0,0,0.25);
}
.receipt-actions {
  display: flex; gap: 0.5rem; padding: 0.75rem 1rem;
  background: #1f2937; border-radius: 1rem 1rem 0 0;
}
.receipt-btn-print, .receipt-btn-pdf, .receipt-btn-close {
  padding: 0.45rem 0.875rem; border: none; border-radius: 0.4rem;
  font-weight: 600; cursor: pointer; font-size: 0.82rem;
}
.receipt-btn-print { background: #3b82f6; color: white; }
.receipt-btn-pdf   { background: #10b981; color: white; }
.receipt-btn-close { background: #374151; color: #d1d5db; margin-left: auto; }

/* The actual receipt paper */
.receipt-paper {
  background: white;
  width: 300px; min-width: 280px;
  padding: 1.25rem 1rem;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.8rem;
  color: #111;
  margin: 0 auto 1rem;
}
.receipt-store { text-align: center; margin-bottom: 0.5rem; }
.receipt-logo { font-size: 2rem; font-weight: 900; letter-spacing: 0.15em; color: #111; }
.receipt-store-sub { margin: 0; font-size: 0.7rem; color: #555; }
.receipt-store-info { margin: 0.1rem 0; font-size: 0.65rem; color: #888; }
.receipt-date { margin: 0.35rem 0 0; font-size: 0.72rem; color: #444; }
.receipt-id { margin: 0; font-size: 0.65rem; color: #888; }

.receipt-divider { text-align: center; color: #ccc; font-size: 0.75rem; margin: 0.5rem 0; letter-spacing: 0.05em; }

.receipt-items { margin: 0.35rem 0; }
.receipt-item { margin-bottom: 0.5rem; }
.receipt-item-name { font-weight: 700; font-size: 0.8rem; }
.receipt-avulso-tag { background: #fef3c7; color: #92400e; font-size: 0.6rem; padding: 0.05rem 0.3rem; border-radius: 0.2rem; margin-left: 0.3rem; }
.receipt-item-meta { font-size: 0.68rem; color: #777; }
.receipt-item-calc { display: flex; justify-content: space-between; font-size: 0.75rem; gap: 0.5rem; }
.receipt-item-disc { color: #dc2626; }
.receipt-item-total { font-weight: 700; }

.receipt-totals { margin: 0.35rem 0; }
.receipt-total-row { display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem; }
.receipt-discount-row { color: #dc2626; }
.receipt-grand-total { font-weight: 900; font-size: 1rem; border-top: 1px dashed #ccc; padding-top: 0.35rem; margin-top: 0.25rem; }

.receipt-payments { margin: 0.35rem 0; }
.receipt-section-label { font-weight: 700; font-size: 0.72rem; margin: 0 0 0.25rem; text-transform: uppercase; letter-spacing: 0.05em; }
.receipt-payment-row { display: flex; justify-content: space-between; font-size: 0.78rem; margin-bottom: 0.2rem; }
.receipt-troco-row { font-weight: 700; color: #059669; }
.receipt-client { font-size: 0.72rem; color: #555; margin: 0.35rem 0; }

.receipt-footer { text-align: center; margin-top: 0.5rem; }
.receipt-footer p { margin: 0.1rem 0; font-size: 0.7rem; color: #888; }

/* Print styles */
@media print {
  .no-print { display: none !important; }
  .receipt-overlay { position: static; background: none; padding: 0; }
  .receipt-modal { background: none; box-shadow: none; max-height: none; overflow: visible; border-radius: 0; }
  .receipt-paper { width: 72mm; margin: 0; box-shadow: none; }
  body > *:not(.receipt-overlay) { display: none !important; }
  @page { size: 80mm auto; margin: 2mm; }
}
</style>
