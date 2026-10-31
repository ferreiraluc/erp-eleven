import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { CustomerWithActivity } from '@/services/customerLogistics'
import CustomerActivityCard from './CustomerActivityCard.vue'

const customer: CustomerWithActivity = {
  id: 'customer-whatsapp-qa', nome: 'Cliente sintético QA', telefone: '+595 981 234567',
  ativo: true, created_at: '', updated_at: '',
}
let app: App | undefined, root: HTMLDivElement

async function mount(phone: string | undefined = customer.telefone, locale = 'pt') {
  const props = reactive({ customer: { ...customer, telefone: phone }, expanded: false })
  const toggle = vi.fn(() => { props.expanded = !props.expanded })
  const bubble = vi.fn()
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] })
  await router.push('/'); await router.isReady()
  root = document.createElement('div'); document.body.append(root)
  app = createApp({ render: () => h('div', { onClick: bubble }, [h(CustomerActivityCard, { ...props, onToggle: toggle })]) })
  app.use(createI18n({ legacy: false, locale, messages: {} })).use(router).mount(root)
  await nextTick()
  return { props, toggle, bubble }
}

afterEach(() => { app?.unmount(); app = undefined; root?.remove() })

describe('Customer card WhatsApp action', () => {
  it('opens only the customer number in a safe new tab and never expands the card', async () => {
    const { toggle, bubble } = await mount()
    const link = root.querySelector<HTMLAnchorElement>('a.customer-whatsapp')!
    expect(link.href).toBe('https://wa.me/595981234567')
    expect(link.target).toBe('_blank')
    expect(link.rel.split(' ')).toEqual(expect.arrayContaining(['noopener', 'noreferrer']))
    expect(link.getAttribute('aria-label')).toBe('Abrir conversa com Cliente sintético QA no WhatsApp (nova aba)')
    expect(link.closest('button')).toBeNull()
    expect(link.parentElement?.querySelector('.customer-contact')?.textContent).toBe(customer.telefone)

    const click = new MouseEvent('click', { bubbles: true, cancelable: true })
    link.dispatchEvent(click)
    expect(click.defaultPrevented).toBe(false)
    expect(toggle).not.toHaveBeenCalled()
    expect(bubble).not.toHaveBeenCalled()
    expect(root.querySelector('.customer-expand')?.getAttribute('aria-expanded')).toBe('false')

    root.querySelector<HTMLButtonElement>('.customer-expand')!.click(); await nextTick()
    expect(toggle).toHaveBeenCalledTimes(1)
    expect(root.querySelector('.customer-expand')?.getAttribute('aria-expanded')).toBe('true')
    link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); await nextTick()
    expect(toggle).toHaveBeenCalledTimes(1)
    expect(root.querySelector('.historico-section')).not.toBeNull()
  })

  it('keeps an ambiguous local number visible with a disabled action and accessible correction hint', async () => {
    const { props } = await mount('(11) 91234-5678')
    expect(root.querySelector('a.customer-whatsapp')).toBeNull()
    expect(root.querySelector('.customer-contact')?.textContent).toBe('(11) 91234-5678')
    const action = root.querySelector<HTMLButtonElement>('button.customer-whatsapp')!
    expect(action.disabled).toBe(true)
    const hint = document.getElementById(action.getAttribute('aria-describedby')!)!
    expect(hint.textContent).toBe('Inclua o código do país e confira o telefone para abrir o WhatsApp.')
    props.customer.telefone = '+55 (11) 91234-5678'; await nextTick()
    expect(root.querySelector<HTMLAnchorElement>('a.customer-whatsapp')?.href).toBe('https://wa.me/5511912345678')
    expect(root.querySelector('.customer-phone-help')).toBeNull()
  })

  it('does not expose an action when only an email address is available', async () => {
    const { props } = await mount('')
    props.customer.email = 'cliente-qa@example.test'; await nextTick()
    expect(root.querySelector('.customer-contact')?.textContent).toBe('cliente-qa@example.test')
    expect(root.querySelector('.customer-whatsapp')).toBeNull()
  })

  it.each([
    ['es', 'Abrir conversación con Cliente sintético QA en WhatsApp (nueva pestaña)', 'Incluya el código de país y revise el teléfono para abrir WhatsApp.'],
    ['en', 'Open a WhatsApp conversation with Cliente sintético QA (new tab)', 'Include the country code and check the phone number to open WhatsApp.'],
  ])('translates the action and phone guidance to %s', async (locale, label, hint) => {
    const { props } = await mount(customer.telefone, locale)
    expect(root.querySelector('a.customer-whatsapp')?.getAttribute('aria-label')).toBe(label)
    props.customer.telefone = 'telefone inválido'; await nextTick()
    expect(root.querySelector('.customer-phone-help')?.textContent).toBe(hint)
  })
})
