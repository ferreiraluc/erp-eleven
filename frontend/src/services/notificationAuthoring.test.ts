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
  it('fills a real tracking recipient only for the chosen code and blocks an absent tracking context', () => {
    const source = { title: 'Pacote de {cliente_username}', body: '{tracking_code} · {status}', user_ids: ['sol'], action_path: '/rastreamento?search=AA123456789BR' }
    const tracking = { id: 'fixture', code: 'AA123456789BR', cliente_username: 'Cliente destinatário', status: 'Em trânsito' }
    expect(notificationPreview(source, users, null, moment, tracking)).toMatchObject({ title: 'Pacote de Cliente destinatário', body: 'AA123456789BR · Em trânsito', problem: null })
    expect(notificationPreview(source, users, null, moment, { ...tracking, code: 'OUTRO' }).problem).toBe('contextVariablesMissing')
    expect(notificationPreview({ ...source, action_path: '/rastreamento?search=A&search=B' }, users, null, moment, tracking).problem).toBe('contextVariablesMissing')
  })
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


it('previews the frozen sale amount and requires a matching sale for the variable', () => {
  const users = [{id:'lucas',nome:'Lucas'}], moment = new Date('2026-10-27T13:15:00Z')
  const sale = {id:'sale-value',code:'TEST',created_at:'',seller_id:'sol',seller_name:'Sol',status:'completed',items:[],items_total:0,items_truncated:false}
  const source = {title:'Venda U$ {sale_total} concluída',body:'{user_name} concluiu a venda.',user_ids:['lucas'],context:{sale_id:sale.id,target:'sale' as const}}
  expect(notificationPreview(source,users,{...sale,sale_total:'800'},moment)).toMatchObject({title:'Venda U$ 800 concluída',body:'Sol concluiu a venda.',problem:null})
  expect(notificationPreview({...source,context:undefined},users,null,moment).problem).toBe('contextVariablesMissing')
})
