/** Restart the application so caches from the previous account cannot survive login. */
export function navigateAfterLogin(destination: string) {
  if (destination.startsWith('#')) {
    window.location.replace(destination)
    window.location.reload()
  } else window.location.assign(destination)
}
