import { Capacitor, registerPlugin } from '@capacitor/core'

export type NativeSecretKey = 'session' | 'notification-installation'
export interface NativeSecureStoragePlugin {
  get(options: { key: NativeSecretKey }): Promise<{ value: string | null }>
  set(options: { key: NativeSecretKey; value: string }): Promise<void>
  remove(options: { key: NativeSecretKey }): Promise<void>
  getVolatileSession(): Promise<{ value: string | null }>
  setVolatileSession(options: { value: string }): Promise<void>
  clearVolatileSession(): Promise<void>
}
export const nativeSecureStorage = registerPlugin<NativeSecureStoragePlugin>('ElevenSecureStorage')
export const isNativeSession = () => Capacitor.isNativePlatform()
export const NATIVE_SESSION_GUARD = 'eleven_native_session_guard'
export const NATIVE_VOLATILE_SESSION_GUARD = 'eleven_native_volatile_session_guard'

export class NativeSessionStorageError extends Error {
  constructor() { super('native_secure_session_unavailable'); this.name = 'NativeSessionStorageError' }
}
export const isNativeSessionStorageError = (error: unknown): error is NativeSessionStorageError => error instanceof NativeSessionStorageError
export function nativeSessionStorageMessage(locale = 'pt'): string {
  if (locale.startsWith('es')) return 'No fue posible acceder al almacenamiento seguro del dispositivo. Desbloquéalo e inténtalo de nuevo.'
  if (locale.startsWith('en')) return 'The device secure storage is unavailable. Unlock the device and try again.'
  return 'Não foi possível acessar o armazenamento seguro do aparelho. Desbloqueie-o e tente novamente.'
}
interface NativeSessionRecord { version: 1; token: string; expiresAt: number | null; nonce: string }

/** Only a random marker is stored in WebStorage. It prevents an older Keychain
 * entry from restoring an account after an interrupted logout or reinstall. */
export class NativeSessionVault {
  private record: NativeSessionRecord | null = null
  private remembered = false
  private ready = false
  private initializing: Promise<void> | null = null
  private sequence = 0
  private pending: Promise<void> = Promise.resolve()

  constructor(private plugin: NativeSecureStoragePlugin, private marker: Storage, private nonce: () => string = () => crypto.randomUUID(), private volatileMarker: Storage = sessionStorage) {}

  get token() { return this.record?.token || null }
  get expiresAt() { return this.record?.expiresAt ?? null }
  get isRemembered() { return this.remembered }

  async initialize(): Promise<void> {
    if (this.ready) return
    if (this.initializing) return this.initializing
    const sequence = this.sequence
    const initialization = (async () => {
      try {
        const volatileExpected = this.volatileMarker.getItem(NATIVE_VOLATILE_SESSION_GUARD)
        const expected = volatileExpected || this.marker.getItem(NATIVE_SESSION_GUARD)
        const value = volatileExpected ? (await this.plugin.getVolatileSession()).value : expected ? (await this.plugin.get({ key: 'session' })).value : null
        if (sequence !== this.sequence) { await this.pending; this.ready = true; return }
        let parsed: NativeSessionRecord | null = null
        if (value && value.length <= 32768) {
          try { parsed = JSON.parse(value) } catch { /* Invalid record is discarded below. */ }
        }
        if (parsed?.version === 1 && parsed.nonce === expected && typeof parsed.token === 'string' && parsed.token.length > 0 && parsed.token.length <= 16384 &&
            (parsed.expiresAt === null || (typeof parsed.expiresAt === 'number' && Number.isFinite(parsed.expiresAt)))) {
          this.record = parsed
          this.remembered = !volatileExpected
        } else {
          // Keychain survives iOS uninstall. Never adopt it without this install's marker.
          this.marker.removeItem(NATIVE_SESSION_GUARD)
          this.volatileMarker.removeItem(NATIVE_VOLATILE_SESSION_GUARD)
          await this.plugin.clearVolatileSession()
          await this.plugin.remove({ key: 'session' })
        }
        this.ready = true
      } catch {
        this.record = null
        this.remembered = false
        throw new NativeSessionStorageError()
      }
    })()
    this.initializing = initialization.finally(() => { this.initializing = null })
    return this.initializing
  }

  save(token: string, remember: boolean) {
    if (!this.ready || !token || token.length > 16384) throw new NativeSessionStorageError()
    this.replace({ version: 1, token, expiresAt: null, nonce: this.nonce() }, remember)
  }

  shorten(token: string, expiresAt: number) {
    if (!this.record || this.record.token !== token) return
    this.replace({ ...this.record, expiresAt, nonce: this.nonce() }, this.remembered)
  }

  clear() {
    this.record = null
    this.remembered = false
    let markerFailed = false
    try { this.marker.removeItem(NATIVE_SESSION_GUARD) } catch { markerFailed = true }
    try { this.volatileMarker.removeItem(NATIVE_VOLATILE_SESSION_GUARD) } catch { markerFailed = true }
    this.enqueue(async () => {
      await this.plugin.clearVolatileSession()
      await this.plugin.remove({ key: 'session' })
      if (markerFailed) throw new NativeSessionStorageError()
    })
  }

  flush() { return this.pending }

  private replace(record: NativeSessionRecord, remember: boolean) {
    try {
      // Changing the marker first makes any stale native write unusable after a crash.
      if (remember) {
        this.volatileMarker.removeItem(NATIVE_VOLATILE_SESSION_GUARD)
        this.marker.setItem(NATIVE_SESSION_GUARD, record.nonce)
      } else {
        this.marker.removeItem(NATIVE_SESSION_GUARD)
        this.volatileMarker.setItem(NATIVE_VOLATILE_SESSION_GUARD, record.nonce)
      }
    } catch { throw new NativeSessionStorageError() }
    this.record = record
    this.remembered = remember
    this.enqueue(async () => {
      if (remember) {
        await this.plugin.clearVolatileSession()
        await this.plugin.set({ key: 'session', value: JSON.stringify(record) })
      } else {
        await this.plugin.remove({ key: 'session' })
        await this.plugin.setVolatileSession({ value: JSON.stringify(record) })
      }
    })
  }

  private enqueue(operation: () => Promise<void>) {
    const sequence = ++this.sequence
    this.pending = this.pending.catch(() => undefined).then(async () => {
      if (sequence !== this.sequence) return
      try { await operation() } catch {
        if (sequence === this.sequence) {
          this.record = null
          this.remembered = false
          try { this.marker.removeItem(NATIVE_SESSION_GUARD) } catch { /* Authentication remains closed. */ }
          try { this.volatileMarker.removeItem(NATIVE_VOLATILE_SESSION_GUARD) } catch { /* Authentication remains closed. */ }
        }
        throw new NativeSessionStorageError()
      }
    })
    // Expiry must clear UI synchronously. Callers that need durable confirmation
    // await flush(); background expiry must not create an unhandled rejection.
    void this.pending.catch(() => undefined)
  }
}

let vault: NativeSessionVault | undefined
export function nativeSessionVault() {
  return vault ||= new NativeSessionVault(nativeSecureStorage, localStorage)
}
