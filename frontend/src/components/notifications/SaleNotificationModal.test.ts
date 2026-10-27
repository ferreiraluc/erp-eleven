import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import SaleNotificationModal from './SaleNotificationModal.vue'
const mocks = vi.hoisted(() => ({
  auth: {} as { isOwner: boolean; isAuthenticated: boolean; token: string | null },
  admin: vi.fn(),
  contextSale: vi.fn(),
  contextSales: vi.fn(),
  contextProduct: vi.fn(),
  create: vi.fn(),
  getItems: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/services/notifications', async (original) => ({
  ...(await original<typeof import('@/services/notifications')>()),
  notificationsAPI: {
    admin: mocks.admin,
    contextSale: mocks.contextSale,
    contextSales: mocks.contextSales,
    contextProduct: mocks.contextProduct,
    create: mocks.create,
  },
}))
vi.mock('@/services/api', () => ({ inventoryAPI: { getItems: mocks.getItems } }))
let app: App | undefined, root: HTMLElement
const saleId = 'b11b8e8d-f4ab-4be7-8b31-6ebbca333333',
  productId = '75039acf-e137-4d84-b5e0-20956d2eccaa'
const selected = () => ({
  id: saleId,
  code: '8B316EBBCA',
  seller_id: 'sol',
  seller_name: 'Sol',
  status: 'completed',
  created_at: '2026-10-27T12:00:00Z',
  items: [
    {
      id: 'line-one',
      item_id: null,
      item_name: 'Camiseta avulsa',
      is_avulso: true,
      product_available: false,
      size: 'M',
      color: 'Black',
    },
  ],
  items_total: 1,
  items_truncated: false,
})
beforeEach(() => {
  vi.resetAllMocks()
  mocks.auth = reactive({ isOwner: true, isAuthenticated: true, token: 'owner-token' })
  mocks.admin.mockResolvedValue({
    items: [],
    total: 0,
    users: [
      { id: 'sol', nome: 'Sol' },
      { id: 'lucas', nome: 'Lucas' },
    ],
    templates: [],
    rules: [],
  })
  mocks.contextSale.mockResolvedValue(selected())
  mocks.create.mockResolvedValue({})
  mocks.getItems.mockResolvedValue({
    items: [
      {
        id: productId,
        name: 'Camiseta correta M',
        is_active: true,
        inventory_code: 'INV-ABC123',
        size: 'M',
        color: 'Black',
      },
    ],
  })
  mocks.contextProduct.mockResolvedValue({
    id: productId,
    name: 'Camiseta correta M',
    inventory_code: 'INV-ABC123',
    size: 'M',
    color: 'Black',
  })
})
afterEach(() => {
  app?.unmount()
  app = undefined
  root?.remove()
})
async function mount(props: { saleId: string; itemId?: string } = { saleId }) {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(SaleNotificationModal, props)
  app.mount(root)
  await vi.waitFor(() =>
    expect(document.querySelector('.notification-preview')?.textContent).toContain('Sol, confira'),
  )
  await nextTick()
}
async function choose(label: string, value: string) {
  document.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!.click()
  await nextTick()
  const option = Array.from(
    document.querySelectorAll<HTMLButtonElement>('button[role=option]'),
  ).find((button) => button.value === value)!
  expect(option).toBeTruthy()
  option.click()
  await nextTick()
}
describe('Sale notification authoring', () => {
  it('prefills Sol and a rendered preview but sends only after an explicit submit', async () => {
    await mount()
    expect(mocks.create).not.toHaveBeenCalled()
    expect(
      document.querySelector<HTMLInputElement>('input[type=checkbox][value=sol]')?.checked,
    ).toBe(true)
    expect(document.querySelector('.notification-preview')?.textContent).toContain('#8B316EBBCA')
    expect(document.querySelector('.notification-preview')?.textContent).not.toContain(
      '{sale_code}',
    )
    document
      .querySelector<HTMLButtonElement>('.sale-notification-dialog button[type=submit]')!
      .click()
    await vi.waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1))
    expect(mocks.create.mock.calls[0]).toEqual([
      expect.objectContaining({
        title: 'Conferir venda #{sale_code}',
        user_ids: ['sol'],
        context: { sale_id: saleId, target: 'sale' },
        requires_response: true,
        action_path: null,
      }),
      'owner-token',
    ])
  })
  it('keeps authored edits and the same request key after an uncertain network result', async () => {
    mocks.create.mockRejectedValueOnce(new Error('network'))
    await mount()
    const body = document.querySelector<HTMLTextAreaElement>('.notification-composer textarea')!
    body.value = 'Sol, conferir os dois itens avulsos.'
    body.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    const button = document.querySelector<HTMLButtonElement>(
      '.sale-notification-dialog button[type=submit]',
    )!
    button.click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Não foi possível salvar'))
    const request = mocks.create.mock.calls[0][0].request_id
    expect(body.value).toBe('Sol, conferir os dois itens avulsos.')
    button.click()
    await vi.waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(2))
    expect(mocks.create.mock.calls[1][0].request_id).toBe(request)
  })
  it('offers an explicit inventory reference for an avulso using a small image-free search', async () => {
    await mount()
    await choose('Ao abrir o aviso', 'product')
    expect(
      document.querySelector<HTMLButtonElement>('.sale-notification-dialog button[type=submit]')!
        .disabled,
    ).toBe(true)
    const search = document.querySelector<HTMLInputElement>(
      '.notification-context input[type=search]',
    )!
    search.value = 'INV-ABC123'
    search.dispatchEvent(new Event('input', { bubbles: true }))
    await vi.waitFor(() => expect(mocks.getItems).toHaveBeenCalled())
    expect(mocks.getItems.mock.calls[0][0]).toMatchObject({
      search: 'INV-ABC123',
      page_size: 20,
      include_images: false,
    })
    await choose('Escolha o produto', productId)
    expect(document.body.textContent).toContain('Não vincula nem altera os itens da venda')
    document
      .querySelector<HTMLButtonElement>('.sale-notification-dialog button[type=submit]')!
      .click()
    await vi.waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0].context).toEqual({
      sale_id: saleId,
      target: 'product',
      item_id: productId,
    })
  })
  it('does not expose or send the owner editor after switching accounts during lookup', async () => {
    let finish!: (value: unknown) => void
    mocks.contextSale.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    root = document.createElement('div')
    document.body.append(root)
    app = createApp(SaleNotificationModal, { saleId })
    app.mount(root)
    await nextTick()
    mocks.auth.isOwner = false
    mocks.auth.token = 'sol-token'
    await nextTick()
    finish(selected())
    await nextTick()
    await Promise.resolve()
    expect(document.querySelector('.sale-notification-dialog')).toBeNull()
    expect(mocks.create).not.toHaveBeenCalled()
  })
})
