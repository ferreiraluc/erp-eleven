import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { PdvCartError, stockAt, validateLocation, validateQuantity, type CatalogStockSnapshot } from '@/services/pdvCart'
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
  const stockSnapshots = ref<Record<string, CatalogStockSnapshot>>({})
  const payments = ref<CartPayment[]>([])
  const discountGs = ref(0)
  const clienteId = ref<string | null>(null)
  const clienteNome = ref<string | null>(null)
  const notas = ref('')

  // UI state
  const loading = ref(false)
  const checkoutUncertain = ref(false)
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

  function ensureEditable() {
    if (loading.value) throw new PdvCartError('busy')
  }

  function rememberStock(items: CatalogStockSnapshot[]) {
    for (const item of items) stockSnapshots.value[item.id] = { id: item.id, current_stock: item.current_stock,
      stock_loja: item.stock_loja, stock_deposito: item.stock_deposito, is_active: item.is_active }
  }

  function reservedStock(itemId: string, location: string, excludeId?: string) {
    return cart.value.filter(line => !line.is_avulso && line.item_id === itemId && line.location === location && line.id !== excludeId)
      .reduce((sum, line) => sum + line.quantity, 0)
  }

  function availableStock(itemId: string, location: string, excludeId?: string): number | null {
    try { return Math.max(0, stockAt(stockSnapshots.value[itemId], location) - reservedStock(itemId, location, excludeId)) }
    catch { return null }
  }

  function validateLine(item: Omit<CartItem, 'id'>, excludeId?: string) {
    validateQuantity(item.quantity, !item.is_avulso)
    validateLocation(item.location)
    if (item.is_avulso) return
    if (!item.item_id) throw new PdvCartError('missingProduct')
    const available = stockAt(stockSnapshots.value[item.item_id], item.location)
    const requested = reservedStock(item.item_id, item.location, excludeId) + item.quantity
    if (!Number.isFinite(requested) || requested > available) throw new PdvCartError('insufficientStock', { available, requested })
  }

  function addItem(item: Omit<CartItem, 'id'>, snapshot?: CatalogStockSnapshot) {
    ensureEditable()
    if (snapshot) rememberStock([snapshot])
    validateLine(item)
    // Price variants share availability; only identical local/price lines merge.
    const existing = !item.is_avulso && item.item_id ? cart.value.find(c => !c.is_avulso &&
      c.item_id === item.item_id && c.unit_price_gs === item.unit_price_gs && c.location === item.location) : undefined
    if (existing) {
      validateQuantity(existing.quantity + item.quantity, true)
      existing.quantity += item.quantity
    } else cart.value.push({ ...item, id: crypto.randomUUID() })
  }

  function removeItem(id: string) {
    ensureEditable()
    const idx = cart.value.findIndex(i => i.id === id)
    if (idx !== -1) cart.value.splice(idx, 1)
  }

  function updateItemQty(id: string, qty: number) {
    ensureEditable()
    const item = cart.value.find(i => i.id === id)
    if (!item) return
    validateLine({ ...item, quantity: qty }, id)
    item.quantity = qty
  }

  function updateItemPrice(id: string, price: number) {
    ensureEditable()
    const item = cart.value.find(i => i.id === id)
    if (item) item.unit_price_gs = Math.max(0, price)
  }

  function updateItemDiscount(id: string, discount: number) {
    ensureEditable()
    const item = cart.value.find(i => i.id === id)
    if (item) item.discount_gs = Math.max(0, discount)
  }

  // Update price in native currency and recalculate G$ equivalent
  function updateItemOriginalPrice(id: string, originalPrice: number, rateToGs: number) {
    ensureEditable()
    const item = cart.value.find(i => i.id === id)
    if (!item) return
    item.original_price = Math.max(0, originalPrice)
    item.unit_price_gs = Math.round(originalPrice * rateToGs)
  }

  function addPayment(payment: Omit<CartPayment, 'id'>) {
    ensureEditable()
    payments.value.push({ ...payment, id: crypto.randomUUID() })
  }

  function removePayment(id: string) {
    ensureEditable()
    const idx = payments.value.findIndex(p => p.id === id)
    if (idx !== -1) payments.value.splice(idx, 1)
  }

  function clearCart() {
    ensureEditable()
    resetCart()
  }

  function resetCart() {
    checkoutUncertain.value = false
    stockSnapshots.value = {}
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
    resetCart()
    lastSale.value = null
    clients.value = []
    loading.value = false
  }

  // Pinia survives hash navigation. Clear financial drafts and cached balances
  // synchronously when identity, token or the user's financial scope changes.
  watch([() => auth.user?.id, () => auth.token, () => auth.user?.sales_scope,
         () => auth.user?.vendedor_id, () => auth.user?.sales_seller], resetSessionState, { flush: 'sync' })

  async function completeSale(vendedorId?: string): Promise<PdvSaleResponse> {
    ensureEditable()
    if (checkoutUncertain.value) throw new PdvCartError('uncertain')
    if (!cart.value.length) throw new PdvCartError('emptyCart')
    for (const item of cart.value) validateLine(item, item.id)
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
        resetCart()
      }
      // A committed sale remains successful, even if its original view closed.
      // Only the stale UI mutation is suppressed.
      return sale
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (generation === sessionGeneration && (!status || status >= 500)) checkoutUncertain.value = true
      throw error
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
    loading, checkoutUncertain, lastSale, clients,
    subtotal, total, totalPaid, troco, remaining, cartCount,
    rememberStock, availableStock, addItem, removeItem, updateItemQty, updateItemPrice, updateItemDiscount, updateItemOriginalPrice,
    addPayment, removePayment, clearCart, completeSale, loadClients,
  }
})
