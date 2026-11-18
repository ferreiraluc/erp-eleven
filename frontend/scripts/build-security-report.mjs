import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'

export const reportName = 'security-build-report.json'
export const sha256 = (value) => createHash('sha256').update(value).digest('hex')

export function modulePackage(id) {
  const normalized = id.replaceAll('\\', '/')
  const tail = normalized.slice(normalized.lastIndexOf('/node_modules/') + 14)
  if (!normalized.includes('/node_modules/')) return null
  const parts = tail.split('/')
  return parts[0]?.startsWith('@') ? parts.slice(0, 2).join('/') : parts[0]
}

// Only emitted chunk modules count: build plugins themselves are not shipped.
export function makeBuildReport(bundle, lockContent, now = new Date(), workers = []) {
  const chunks = Object.values(bundle).filter((entry) => entry.type === 'chunk')
  const modules = chunks.flatMap((entry) => Object.keys(entry.modules))
  return {
    version: 1,
    builtAt: now.toISOString(),
    packageLockSha256: sha256(lockContent),
    chunksAnalyzed: chunks.length,
    modulesAnalyzed: modules.length,
    packages: [...new Set(modules.map(modulePackage).filter(Boolean))].sort(),
    externals: [...new Set(chunks.flatMap((chunk) => [...chunk.imports, ...chunk.dynamicImports])
      .filter((id) => !bundle[id]))].sort(),
    workers,
  }
}

export function buildSecurityReports() {
  const workers = []
  const lock = () => readFileSync(new URL('../package-lock.json', import.meta.url))
  const main = {
    name: 'eleven-build-security-report',
    apply: 'build',
    generateBundle(_options, bundle) {
      this.emitFile({ type: 'asset', fileName: reportName,
        source: JSON.stringify(makeBuildReport(bundle, lock(), new Date(), workers), null, 2) })
    },
  }
  return { main, worker: () => ({
    name: 'eleven-worker-security-report',
    generateBundle(_options, bundle) {
      // Vite emits worker bundles as assets of the parent build. Their actual
      // Rollup modules must be inspected in the independent worker compilation.
      workers.push(makeBuildReport(bundle, lock()))
    },
  }) }
}
