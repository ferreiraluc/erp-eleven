import 'vue'
declare module 'vue' {
  interface ComponentCustomProperties {
    $tr: (source: string, params?: Record<string, string | number>) => string
  }
}
export {}
