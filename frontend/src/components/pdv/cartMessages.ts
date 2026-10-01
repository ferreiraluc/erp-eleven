import { useI18n } from 'vue-i18n'
import { PdvCartError } from '@/services/pdvCart'
import { useInventoryI18n } from '@/components/inventory/i18n'

const messages: Record<string, [string, string, string]> = {
  catalogQuantity: ['Informe uma quantidade inteira de 1 a 9.999.999 para produtos do estoque.', 'Indique una cantidad entera de 1 a 9.999.999 para productos del stock.', 'Enter a whole quantity from 1 to 9,999,999 for inventory products.'],
  manualQuantity: ['Informe uma quantidade positiva, até 9.999.999,999 e com no máximo 3 casas decimais.', 'Indique una cantidad positiva, hasta 9.999.999,999 y con un máximo de 3 decimales.', 'Enter a positive quantity up to 9,999,999.999 with at most 3 decimal places.'],
  invalidLocation: ['Selecione Loja ou Depósito para a baixa.', 'Seleccione Tienda o Depósito para la salida.', 'Select Store or Warehouse for the stock withdrawal.'],
  missingProduct: ['Selecione um produto do estoque válido.', 'Seleccione un producto válido del stock.', 'Select a valid inventory product.'],
  unknownStock: ['Há saldo desconhecido neste produto. Nenhuma movimentação foi registrada; confira os dados do estoque.', 'Hay un saldo desconocido en este producto. No se registró ningún movimiento; revise los datos del stock.', 'This product has an unknown balance. No stock movement was recorded; review the inventory data.'],
  invalidStock: ['Os saldos deste produto divergem ou são inválidos. Confira o estoque antes de vender.', 'Los saldos de este producto no coinciden o son inválidos. Revise el stock antes de vender.', 'This product has inconsistent or invalid balances. Review inventory before selling.'],
  inactiveProduct: ['Este produto está inativo. Atualize a consulta antes de vender.', 'Este producto está inactivo. Actualice la consulta antes de vender.', 'This product is inactive. Refresh the search before selling.'],
  insufficientStock: ['Saldo insuficiente no local: disponível {available}, solicitado {requested} somando o carrinho.', 'Saldo insuficiente en el local: disponible {available}, solicitado {requested} sumando el carrito.', 'Insufficient stock at this location: {available} available, {requested} requested across the cart.'],
  busy: ['A venda está sendo processada. Aguarde a resposta antes de continuar.', 'La venta se está procesando. Espere la respuesta antes de continuar.', 'The sale is processing. Wait for the response before continuing.'],
  emptyCart: ['Adicione itens antes de concluir a venda.', 'Agregue artículos antes de completar la venta.', 'Add items before completing the sale.'],
  uncertain: ['Não foi possível confirmar o resultado. A venda pode ter sido registrada. Confira o histórico antes de reenviar; a conclusão deste carrinho está bloqueada até você limpá-lo explicitamente.', 'No se pudo confirmar el resultado. La venta puede haberse registrado. Revise el historial antes de reenviar; la finalización de este carrito está bloqueada hasta que lo vacíe explícitamente.', 'The result could not be confirmed. The sale may have been recorded. Check the history before resubmitting; checkout for this cart is blocked until you explicitly clear it.'],
  unknownNamed: ['Estoque não informado para "{name}". Confira os três saldos antes de concluir esta operação.', 'Stock no informado para "{name}". Revise los tres saldos antes de completar esta operación.', 'Stock is missing for "{name}". Check all three balances before completing this operation.'],
  inactiveNamed: ['Produto inativo: "{name}". Selecione um produto ativo para vender.', 'Producto inactivo: "{name}". Seleccione un producto activo para vender.', 'Inactive product: "{name}". Select an active product to sell.'],
  missingLink: ['Produto de catálogo sem vínculo no item da venda. Confira o cadastro antes de continuar.', 'Producto de catálogo sin vínculo en el artículo de la venta. Revise el registro antes de continuar.', 'A sale line is missing its catalog product link. Check the product record before continuing.'],
  productRemoved: ['Um produto de catálogo da venda não existe. Confira o cadastro antes de continuar.', 'Un producto del catálogo de la venta no existe. Revise el registro antes de continuar.', 'A catalog product in this sale does not exist. Check the product record before continuing.'],
  originalLocation: ['Local inválido no item da venda. Confira o local original; use loja ou deposito.', 'Local inválido en el artículo de la venta. Revise el local original; use Tienda o Depósito.', 'Invalid stock location on the sale line. Check the original location; use Store or Warehouse.'],
  legacyQuantity: ['Quantidade inválida no item da venda.', 'Cantidad inválida en el artículo de la venta.', 'Invalid quantity on the sale line.'],
  location: ['Local da baixa', 'Local de salida', 'Stock location'],
  loja: ['Loja', 'Tienda', 'Store'],
  deposito: ['Depósito', 'Depósito', 'Warehouse'],
  available: ['Disponível: {quantity}', 'Disponible: {quantity}', 'Available: {quantity}'],
  snapshot: ['Saldos consultados são indicativos; o servidor confere novamente ao concluir.', 'Los saldos consultados son indicativos; el servidor vuelve a verificarlos al finalizar.', 'Displayed balances are snapshots; the server checks them again at checkout.'],
  searchFailed: ['Não foi possível consultar o estoque. Tente a busca novamente.', 'No se pudo consultar el stock. Intente la búsqueda nuevamente.', 'Could not search inventory. Try the search again.'],
  checkoutFailed: ['Não foi possível concluir a venda. Carrinho e pagamentos foram mantidos para revisão.', 'No se pudo completar la venta. El carrito y los pagos se conservaron para revisión.', 'Could not complete the sale. The cart and payments were kept for review.'],
  conflict: ['O servidor recusou a operação. Confira os dados antes de tentar novamente.', 'El servidor rechazó la operación. Revise los datos antes de intentarlo nuevamente.', 'The server rejected the operation. Review the data before trying again.'],
  validationFailed: ['Revise os campos da venda antes de tentar novamente.', 'Revise los campos de la venta antes de intentarlo nuevamente.', 'Review the sale fields before trying again.'],
}
export function usePdvCartText() {
  const { locale } = useI18n({ useScope: 'global' })
  const { tr: inventoryText } = useInventoryI18n()
  function text(key: string, params: Record<string, string | number> = {}) {
    const value = messages[key]?.[locale.value === 'es' ? 1 : locale.value === 'en' ? 2 : 0] || key
    return value.replace(/\{(\w+)\}/g, (all, name) => Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : all)
  }
  function errorText(error: unknown): string {
    if (error instanceof PdvCartError) return text(error.code, error.params)
    const detail = (error as { response?: { status?: number; data?: { detail?: unknown } } })?.response?.data?.detail
    if (typeof detail === 'string') {
      const missing = /^Estoque não informado para "([\s\S]*)"\. Confira os três saldos antes de concluir esta operação\.$/.exec(detail)
      if (missing) return text('unknownNamed', { name: missing[1] })
      const inactive = /^Produto inativo: "([\s\S]*)"\. Selecione um produto ativo para vender\.$/.exec(detail)
      if (inactive) return text('inactiveNamed', { name: inactive[1] })
      const known: Record<string, string> = {
        'Produto de catálogo sem vínculo no item da venda. Confira o cadastro antes de continuar.': 'missingLink',
        'Um produto de catálogo da venda não existe. Confira o cadastro antes de continuar.': 'productRemoved',
        'Local inválido no item da venda. Confira o local original; use loja ou deposito.': 'originalLocation',
      }
      if (known[detail]) return text(known[detail])
      if (detail.startsWith('Quantidade inválida no item da venda. ')) return `${text('legacyQuantity')} ${text('catalogQuantity')}`
      return `${text('conflict')} ${inventoryText(detail)}`
    }
    if (Array.isArray(detail)) return text('validationFailed')
    return text('checkoutFailed')
  }
  return { cartText: text, cartErrorText: errorText }
}
