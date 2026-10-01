export type OcrCurrency = 'PYG' | 'BRL' | 'USD' | 'EUR'
export interface OcrParsedLabel {
  nome: string | null
  marca: string | null
  tamanho: string | null
  cor: string | null
  codigo_barras: string | null
  preco: number | null
  moeda: OcrCurrency | null
  texto_bruto: string
  qualidade: 'legivel' | 'parcial' | 'ilegivel'
  evidencias: Record<string, string>
  avisos: string[]
  requires_review: true
  matches: Array<{ id: string; name: string; sku_internal: string }>
  matches_total: number
}
export interface OcrAppliedFields {
  name?: string
  brand?: string
  size?: string
  color?: string
  barcode?: string
  sale_price?: number
  currency?: OcrCurrency
}
