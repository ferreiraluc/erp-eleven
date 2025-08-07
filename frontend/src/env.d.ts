/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  // adicione outras envs se precisar
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
