import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { pdvAPI, type PdvSaleCreate, type PdvSaleResponse, type PdvClienteResponse } from '@/services/api'

export interface CartItem {
  id: string                    // temp id para o carrinho
  item_id: string | null
  item_name: string
  item_sku: string | null
  item_category: string | null
  item_size: string | null
  item_color: string | null
  quantity: number
  unit_price_gs: number
  original_price_gs: number | null
  original_price: number        // price in native currency (e.g. 259 USD)
  sale_currency: string         // native currency: 'USD', 'BRL', 'PYG', etc.
  image_data: string | null     // base64 thumbnail for display
  discount_gs: number
  is_avulso: boolean
  location: string
}

export interface CartPayment {
  id: string
  method: string
  currency: string
  amount_original: number
  exchange_rate: number
  amount_gs: number
  cambista_id: string | null
  reference: string | null
  label: string                 // display label
}

export const usePdvStore = defineStore('pdv', () => {
  const auth = useAuthStore()
  let sessionGeneration = 0
  let clientsRequest = 0
  // Cart state
  const cart = ref<CartItem[]>([])
  const payments = ref<CartPayment[]>([])
  const discountGs = ref(0)
  const clienteId = ref<string | null>(null)
  const clienteNome = ref<string | null>(null)
  const notas = ref('')

  // UI state
  const loading = ref(false)
  const lastSale = ref<PdvSaleResponse | null>(null)
  const clients = ref<PdvClienteResponse[]>([])

  // Computed
  const subtotal = computed(() =>
    cart.value.reduce((s, i) => s + i.quantity * i.unit_price_gs - i.discount_gs, 0)
  )
  const total = computed(() => Math.max(0, subtotal.value - discountGs.value))
  const totalPaid = computed(() => payments.value.reduce((s, p) => s + p.amount_gs, 0))
  const troco = computed(() => Math.max(0, totalPaid.value - total.value))
  const remaining = computed(() => Math.max(0, total.value - totalPaid.value))
  const cartCount = computed(() => cart.value.reduce((s, i) => s + i.quantity, 0))

  function addItem(item: Omit<CartItem, 'id'>) {
    // Se mesmo produto (item_id) e mesmo preço → incrementa quantidade
    if (item.item_id) {
      const existing = cart.value.find(
        c => c.item_id === item.item_id && c.unit_price_gs === item.unit_price_gs
      )
      if (existing) {
        existing.quantity++
        return
      }
    }
    cart.value.push({ ...item, id: crypto.randomUUID() })
  }

  function removeItem(id: string) {
    const idx = cart.value.findIndex(i => i.id === id)
    if (idx !== -1) cart.value.splice(idx, 1)
  }

  function updateItemQty(id: string, qty: number) {
    const item = cart.value.find(i => i.id === id)
    if (item) item.quantity = Math.max(1, qty)
  }

  function updateItemPrice(id: string, price: number) {
    const item = cart.value.find(i => i.id === id)
    if (item) item.unit_price_gs = Math.max(0, price)
  }

  function updateItemDiscount(id: string, discount: number) {
    const item = cart.value.find(i => i.id === id)
    if (item) item.discount_gs = Math.max(0, discount)
  }

  // Update price in native currency and recalculate G$ equivalent
  function updateItemOriginalPrice(id: string, originalPrice: number, rateToGs: number) {
    const item = cart.value.find(i => i.id === id)
    if (!item) return
    item.original_price = Math.max(0, originalPrice)
    item.unit_price_gs = Math.round(originalPrice * rateToGs)
  }

  function addPayment(payment: Omit<CartPayment, 'id'>) {
    payments.value.push({ ...payment, id: crypto.randomUUID() })
  }

  function removePayment(id: string) {
    const idx = payments.value.findIndex(p => p.id === id)
    if (idx !== -1) payments.value.splice(idx, 1)
  }

  function clearCart() {
    cart.value = []
    payments.value = []
    discountGs.value = 0
    clienteId.value = null
    clienteNome.value = null
    notas.value = ''
  }

  function resetSessionState() {
    sessionGeneration++
    clientsRequest++
    clearCart()
    lastSale.value = null
    clients.value = []
    loading.value = false
  }

  // Pinia survives hash navigation. Clear financial drafts and cached balances
  // synchronously when identity, token or the user's financial scope changes.
  watch([() => auth.user?.id, () => auth.token, () => auth.user?.sales_scope,
         () => auth.user?.vendedor_id, () => auth.user?.sales_seller], resetSessionState, { flush: 'sync' })

  async function completeSale(vendedorId?: string): Promise<PdvSaleResponse> {
    const generation = sessionGeneration
    loading.value = true
    try {
      const body: PdvSaleCreate = {
        vendedor_id: vendedorId || undefined,
        cliente_id: clienteId.value || undefined,
        cliente_nome: clienteNome.value || undefined,
        items: cart.value.map(i => ({
          item_id: i.item_id || undefined,
          item_name: i.item_name,
          item_sku: i.item_sku || undefined,
          item_category: i.item_category || undefined,
          item_size: i.item_size || undefined,
          item_color: i.item_color || undefined,
          quantity: i.quantity,
          unit_price_gs: i.unit_price_gs,
          original_price_gs: i.original_price_gs || undefined,
          discount_gs: i.discount_gs,
          is_avulso: i.is_avulso,
          location: i.location,
        })),
        desconto_gs: discountGs.value,
        payments: payments.value.map(p => ({
          method: p.method,
          currency: p.currency,
          amount_original: p.amount_original,
          exchange_rate: p.exchange_rate,
          amount_gs: p.amount_gs,
          cambista_id: p.cambista_id || undefined,
          reference: p.reference || undefined,
        })),
        notas: notas.value || undefined,
      }
      const sale = await pdvAPI.createSale(body)
      if (generation === sessionGeneration) {
        lastSale.value = sale
        clearCart()
      }
      // A committed sale remains successful, even if its original view closed.
      // Only the stale UI mutation is suppressed.
      return sale
    } finally {
      if (generation === sessionGeneration) loading.value = false
    }
  }

  async function loadClients(search?: string) {
    const generation = sessionGeneration, request = ++clientsRequest
    const result = await pdvAPI.getClients({ search, tipo: 'atacadista' })
    if (generation === sessionGeneration && request === clientsRequest) clients.value = result
  }

  return {
    cart, payments, discountGs, clienteId, clienteNome, notas,
    loading, lastSale, clients,
    subtotal, total, totalPaid, troco, remaining, cartCount,
    addItem, removeItem, updateItemQty, updateItemPrice, updateItemDiscount, updateItemOriginalPrice,
    addPayment, removePayment, clearCart, completeSale, loadClients,
  }
})
