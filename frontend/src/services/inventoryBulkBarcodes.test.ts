import { expect, it } from 'vitest'
import { barcodePreview, repeatedBarcodes } from './inventoryBulkBarcodes'
import { detailsError, inScope, setDetail } from './inventoryBulkDetails'
import type { InventoryItem } from './api'
const items = [{ id:'a',name:'Camiseta',size:'P',color:'Branca',barcode:'001' },
  { id:'b',name:'Camiseta',size:'XXL',color:'branca',barcode:'' }] as InventoryItem[]
it('keeps existing barcodes by default, and applies the same base across sizes on request', () => {
  expect(barcodePreview(items,{},'0007',true,true).map(r=>r.after)).toEqual(['00072XL'])
  expect(barcodePreview(items,{},'0007',false,false).map(r=>r.after)).toEqual(['0007','0007'])
  expect(repeatedBarcodes(items,{a:'001',b:'001'})).toEqual([['001',2]])
})
it('rejects an incomplete size or an oversized code before applying any row', () => {
  expect(()=>barcodePreview([...items,{...items[0],size:''}],{},'7',true,false)).toThrow('sem tamanho')
  expect(()=>barcodePreview(items,{},'7'.repeat(200),true,false)).toThrow('200')
})
it('scopes by canonical size/color, preserves multiline details and rejects invalid stock limits', () => {
  expect(inScope(items[0],'size:S')).toBe(true)
  expect(inScope(items[1],'color:branco')).toBe(true)
  const draft=setDetail({},items[0],'description','Metal\nBordado')
  expect(draft.a.description).toBe('Metal\nBordado')
  expect(setDetail(draft,items[0],'description','')).toEqual({})
  expect(detailsError({a:{min_stock:1.5}})).not.toBe('')
  expect(detailsError({a:{unit:''}})).not.toBe('')
})
