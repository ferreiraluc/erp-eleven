import { describe, expect, it } from 'vitest'
import { notificationDestination, notificationPreview } from './notificationAuthoring'
import type { NotificationSaleDetail } from './notifications'
const sale: NotificationSaleDetail = {
  id: 'sale-one',
  code: '8B316EBBCA',
  created_at: '2026-10-27T12:00:00Z',
  seller_id: 'sol',
  seller_name: 'Sol',
  status: 'completed',
  items: [],
  items_total: 0,
  items_truncated: false,
}
const users = [
  { id: 'sol', nome: 'Sol' },
  { id: 'lucas', nome: 'Lucas' },
]
const moment = new Date('2026-10-27T13:15:00Z')
describe('Owner notification preview', () => {
  it('fills the selected sale, seller, BRT clock and status without changing authored text', () => {
    const source = {
      title: 'Conferir #{sale_code}',
      body: '{user_name} · {date} {time} · {status}',
      user_ids: ['lucas'],
      context: { sale_id: sale.id, target: 'sale' as const },
    }
    expect(notificationPreview(source, users, sale, moment)).toEqual({
      title: 'Conferir #8B316EBBCA',
      body: 'Sol · 27/10/2026 10:15 · concluída',
      problem: null,
    })
    expect(source.title).toBe('Conferir #{sale_code}')
  })
  it('uses one selected recipient or equipe when no sale was linked', () => {
    expect(
      notificationPreview(
        { title: 'Olá {user_name}', body: 'Confira.', user_ids: ['sol'] },
        users,
        null,
        moment,
      ).title,
    ).toBe('Olá Sol')
    expect(
      notificationPreview(
        { title: 'Olá {user_name}', body: 'Confira.', user_ids: ['sol', 'lucas'] },
        users,
        null,
        moment,
      ).title,
    ).toBe('Olá equipe')
  })
  it('requires real context for sale and manual tracking variables', () => {
    expect(
      notificationPreview(
        { title: 'Venda {sale_code}', body: 'Conferir', user_ids: ['sol'] },
        users,
        null,
      ).problem,
    ).toBe('contextVariablesMissing')
    expect(
      notificationPreview(
        { title: 'Rastreio {tracking_code}', body: 'Conferir', user_ids: ['sol'] },
        users,
        sale,
      ).problem,
    ).toBe('contextVariablesMissing')
  })
  it('preserves literal product details and JSON while handling escaped braces in one pass', () => {
    expect(
      notificationPreview(
        {
          title: 'Kit {P,M,L}',
          body: '{"erro":true} · {{sale_code}} · {cliente}',
          user_ids: ['sol'],
        },
        users,
        null,
        moment,
      ),
    ).toEqual({
      title: 'Kit {P,M,L}',
      body: '{"erro":true} · {sale_code} · {cliente}',
      problem: null,
    })
  })
  it('rejects access, formatting and incomplete syntax for known variables', () => {
    for (const title of [
      '{sale_code.foo}',
      '{sale_code[0]}',
      '{sale_code:4}',
      '{sale_code!r}',
      '{sale_code',
    ]) {
      expect(
        notificationPreview({ title, body: 'Conferir', user_ids: ['sol'] }, users, null).problem,
      ).toBe('contextUnknownVariable')
    }
    expect(
      notificationPreview(
        { title: '{sale_code_extra}', body: 'Conferir', user_ids: ['sol'] },
        users,
        null,
      ).problem,
    ).toBeNull()
  })
  it('permits an explicitly selected reference product outside the avulso sale', () => {
    const context = { sale_id: sale.id, item_id: 'reference-product', target: 'product' as const }
    expect(
      notificationPreview(
        {
          title: 'Conferir {sale_code}',
          body: 'Produto de referência',
          context,
          user_ids: ['sol'],
        },
        users,
        sale,
      ).problem,
    ).toBeNull()
    expect(notificationDestination(context)).toBe('/inventory?item_id=reference-product')
    expect(sale.items).toEqual([])
  })
  it('blocks unselected products, stale sale data and messages exceeding rendered limits', () => {
    expect(
      notificationPreview(
        { title: 'Conferir', body: 'Item', user_ids: ['sol'], context: { target: 'product' } },
        users,
        sale,
      ).problem,
    ).toBe('contextProductNeeded')
    expect(
      notificationPreview(
        {
          title: 'Conferir',
          body: 'Item',
          user_ids: ['sol'],
          context: { target: 'sale', sale_id: 'changed' },
        },
        users,
        sale,
      ).problem,
    ).toBe('contextSaleNeeded')
    expect(
      notificationPreview(
        { title: 'x'.repeat(119) + '{user_name}', body: 'Item', user_ids: ['sol'] },
        users,
        null,
      ).problem,
    ).toBe('contextTooLong')
  })
})
