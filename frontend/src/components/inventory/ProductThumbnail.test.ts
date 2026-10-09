import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import ProductThumbnail from './ProductThumbnail.vue'
const getThumbnail = vi.hoisted(() => vi.fn())
vi.mock('@/services/api', () => ({ inventoryAPI: { getThumbnails: async (ids: string[]) => ({ thumbnails: Object.fromEntries(await Promise.all(ids.map(async id => [id, await getThumbnail(id)]))), retry_ids: [] }) } }))
let app: App | undefined, root: HTMLDivElement
let visible: (entries: { isIntersecting: boolean }[]) => void
beforeEach(() => {
  vi.useFakeTimers()
  vi.resetAllMocks()
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: typeof visible) { visible = callback }
    observe() {} disconnect() {}
  })
  root = document.createElement('div'); document.body.append(root)
})
afterEach(async () => {
  app?.unmount(); root.remove()
  await vi.runAllTimersAsync()
  vi.useRealTimers(); vi.unstubAllGlobals()
})
async function mount(item: {id:string; has_image:boolean; image_data:string|null; updated_at:string}) {
  app = createApp({ render: () => h(ProductThumbnail, { item }) }); app.mount(root); await nextTick()
}
it('loads only when visible and does not fetch twice for repeated intersection callbacks', async () => {
  await mount({id:'a',has_image:true,image_data:null,updated_at:'1'})
  expect(getThumbnail).not.toHaveBeenCalled()
  getThumbnail.mockResolvedValue({image_data:'data:image/jpeg;base64,small'})
  visible([{isIntersecting:true}]); visible([{isIntersecting:true}]); await nextTick()
  await vi.waitFor(() => expect(getThumbnail).toHaveBeenCalledTimes(1))
  await vi.waitFor(() => expect(root.querySelector('img')?.getAttribute('src')).toBe('data:image/jpeg;base64,small'))
})
it('keeps supplied originals and avoids fetching missing photos', async () => {
  const item = reactive({id:'a',has_image:true,image_data:'data:image/jpeg;base64,original' as string|null,updated_at:'1'})
  await mount(item)
  expect(root.querySelector('img')?.getAttribute('src')).toContain('original')
  item.image_data=null; item.has_image=false; await nextTick()
  expect(root.querySelector('img')?.getAttribute('src')).toContain('image/svg+xml')
  expect(getThumbnail).not.toHaveBeenCalled()
})
it('discards stale responses when a photo is replaced and keeps a placeholder on failure', async () => {
  const item = reactive({id:'stale',has_image:true,image_data:null as string|null,updated_at:'1'})
  let resolve!: (value: unknown) => void
  getThumbnail.mockReturnValueOnce(new Promise(yes => { resolve=yes }))
  await mount(item); visible([{isIntersecting:true}]); await vi.waitFor(() => expect(getThumbnail).toHaveBeenCalledOnce())
  item.updated_at='2'; item.image_data='data:image/jpeg;base64,replacement'; await nextTick()
  resolve({image_data:'data:image/jpeg;base64,stale'}); await nextTick()
  expect(root.querySelector('img')?.getAttribute('src')).toContain('replacement')
  item.image_data=null; item.updated_at='3'; await nextTick()
  getThumbnail.mockRejectedValueOnce(new Error('offline')); visible([{isIntersecting:true}]); await nextTick()
  await vi.waitFor(() => expect(getThumbnail).toHaveBeenCalledTimes(2))
  await vi.runAllTimersAsync()
  expect(root.querySelector('img')?.getAttribute('src')).toContain('image/svg+xml')
})
