export type LabelField = 'title' | 'name' | 'size' | 'color' | 'code' | 'price' | 'barcode' | 'text'
interface ElementPosition {
  id: string
  x: number
  y: number
}
export interface LabelTextElement extends ElementPosition {
  type: 'text'
  field: LabelField
  width: number
  height: number
  font_size: number
  font: 'arimo' | 'barlow'
  bold: boolean
  align: 'left' | 'center' | 'right'
  uppercase: boolean
  lines: number
  text: string
  visible: boolean
}
export interface LabelQrElement extends ElementPosition {
  type: 'qr'
  module_size: number
}
export interface LabelLineElement extends ElementPosition {
  type: 'line'
  width: number
  height: number
  visible: boolean
}
export type LabelElement = LabelTextElement | LabelQrElement | LabelLineElement
export interface LabelDesign {
  schema_version: 1
  elements: LabelElement[]
}
export interface ProductLabelLayout {
  id: string
  name: string
  version: number
  builtin: boolean
  config: LabelDesign
}
export interface LabelLayoutReference {
  layout_id: string
  layout_revision: number
}
export const LABEL_WIDTH = 480,
  LABEL_HEIGHT = 240,
  DOTS_PER_MM = 8

export function elementSize(element: LabelElement) {
  return element.type === 'qr'
    ? { width: 37 * element.module_size, height: 37 * element.module_size }
    : { width: element.width, height: element.height }
}
export function moveLabelElement(element: LabelElement, x: number, y: number) {
  const { width, height } = elementSize(element)
  element.x = Math.max(0, Math.min(LABEL_WIDTH - width, Math.round(x)))
  element.y = Math.max(0, Math.min(LABEL_HEIGHT - height, Math.round(y)))
}
export function designIssue(config: LabelDesign): string {
  const qr = config.elements.filter((e) => e.type === 'qr')
  const codes = config.elements.filter((e) => e.type === 'text' && e.field === 'code' && e.visible)
  if (qr.length !== 1 || codes.length !== 1)
    return 'Mantenha um QR e um código interno visível na etiqueta.'
  const q = qr[0]!,
    qs = elementSize(q)
  for (const e of config.elements) {
    const size = elementSize(e)
    if (
      ![e.x, e.y, size.width, size.height].every(Number.isFinite) ||
      e.x < 0 ||
      e.y < 0 ||
      e.x + size.width > LABEL_WIDTH ||
      e.y + size.height > LABEL_HEIGHT
    )
      return 'Todos os campos devem ficar dentro do papel de 60 × 30 mm.'
    if (
      e.type !== 'qr' &&
      e.visible &&
      e.x < q.x + qs.width &&
      e.x + size.width > q.x &&
      e.y < q.y + qs.height &&
      e.y + size.height > q.y
    )
      return 'Os campos não podem cobrir a área de leitura do QR.'
  }
  return ''
}
export function cloneDesign(config: LabelDesign): LabelDesign {
  return JSON.parse(JSON.stringify(config))
}
export function labelLayoutReference(
  layout: ProductLabelLayout | undefined,
): LabelLayoutReference | undefined {
  return layout && !layout.builtin
    ? { layout_id: layout.id, layout_revision: layout.version }
    : undefined
}
