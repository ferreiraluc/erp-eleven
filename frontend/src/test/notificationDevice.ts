/** Small asynchronous IndexedDB fixture: transactions complete after their request. */
export function notificationDeviceDB(initial: unknown = null) {
  const values = new Map<string, unknown>()
  if (initial) values.set('current', initial)
  const factory = {
    open() {
      const request = {
        result: null as unknown,
        onsuccess: null as (() => void) | null,
        onerror: null,
        onupgradeneeded: null,
      }
      const db = {
        close() {},
        createObjectStore() {},
        transaction() {
          const transaction = {
            oncomplete: null as (() => void) | null,
            onerror: null,
            onabort: null,
            objectStore: () => ({
              get(key: string) {
                return action(() => values.get(key))
              },
              put(value: unknown, key: string) {
                return action(() => {
                  values.set(key, value)
                })
              },
              delete(key: string) {
                return action(() => {
                  values.delete(key)
                })
              },
            }),
          }
          function action(operation: () => unknown) {
            const result = {
              result: undefined as unknown,
              onsuccess: null as (() => void) | null,
              onerror: null,
            }
            queueMicrotask(() => {
              result.result = operation()
              result.onsuccess?.()
              queueMicrotask(() => transaction.oncomplete?.())
            })
            return result
          }
          return transaction
        },
      }
      request.result = db
      queueMicrotask(() => request.onsuccess?.())
      return request
    },
  }
  return { values, factory: factory as unknown as IDBFactory }
}
