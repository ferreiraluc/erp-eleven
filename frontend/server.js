// Optional container server. Render serves dist/ as a static site.
import express from 'express'
import compression from 'compression'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { existsSync } from 'node:fs'

const distPath = fileURLToPath(new URL('./dist/', import.meta.url))
const indexPath = path.join(distPath, 'index.html')
const app = express()
const port = Number(process.env.PORT) || 3000

app.disable('x-powered-by')
app.use(compression())
app.use((_req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff')
  next()
})
app.get('/health', (_req, res) => {
  const ready = existsSync(indexPath)
  res.status(ready ? 200 : 503).json({ status: ready ? 'ok' : 'build_missing' })
})
app.use(express.static(distPath))
app.get('*', (_req, res) => {
  if (!existsSync(indexPath)) {
    res.status(503).json({ error: 'Application not built. Run npm run build first.' })
    return
  }
  res.sendFile(indexPath)
})

const server = app.listen(port, '0.0.0.0', () => {
  console.info(`Eleven frontend listening on port ${port}`)
})
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.on(signal, () => server.close(() => process.exit(0)))
}
