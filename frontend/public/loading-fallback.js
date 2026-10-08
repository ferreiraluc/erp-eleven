// Keep the loading fallback compatible with a CSP that blocks inline scripts.
setTimeout(() => {
  const error = document.getElementById('loading-error')
  if (error) error.style.display = 'block'
}, 15000)
