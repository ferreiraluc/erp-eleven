import type { ProductLabelLayout, LabelTextElement } from '@/services/productLabelDesign'

export function standardLabelLayout(): ProductLabelLayout {
  const text = (
    id: string,
    field: LabelTextElement['field'],
    x: number,
    y: number,
    width = 270,
    height = 20,
  ): LabelTextElement => ({
    id,
    type: 'text',
    field,
    x,
    y,
    width,
    height,
    font_size: 16,
    font: 'arimo',
    bold: false,
    align: 'left',
    uppercase: true,
    lines: 1,
    text: field === 'title' ? 'ELEVEN' : '',
    visible: true,
  })
  return {
    id: 'standard',
    name: 'Padrão ELEVEN',
    builtin: true,
    version: 0,
    config: {
      schema_version: 1,
      elements: [
        text('title', 'title', 165, 20, 152, 32),
        text('name', 'name', 32, 60),
        text('size', 'size', 32, 87),
        text('color', 'color', 32, 112),
        text('code', 'code', 32, 143),
        { id: 'qr', type: 'qr', x: 336, y: 51, module_size: 3 },
        text('price', 'price', 32, 188, 270, 34),
        text('barcode', 'barcode', 324, 202, 145, 18),
      ],
    },
  }
}
