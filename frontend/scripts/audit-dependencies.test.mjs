import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { evaluateAudit, runtimeImports, temporaryPicomatchRisk, validateExposure } from './audit-dependencies.mjs'
import { buildSecurityReports, makeBuildReport, modulePackage } from './build-security-report.mjs'

const now = new Date('2026-11-17T23:00:00.000Z')
const lock = { lockfileVersion: 3, packages: {
  'node_modules/picomatch': { version: '4.0.7' },
  'node_modules/vite': { version: '7.3.7', dependencies: { picomatch: '^4.0.4' } },
  'node_modules/express': { version: '4.22.1' },
} }
const lockContent = JSON.stringify(lock)
const bundle = { 'assets/app.js': { type: 'chunk', imports: [], dynamicImports: [], modules: {
  '/build/frontend/src/main.ts': {}, '/build/frontend/node_modules/vue/index.js': {},
} } }
const build = makeBuildReport(bundle, lockContent, now)
const exposure = { lockContent, build, now, serverSource: "import express from 'express'; import fs from 'node:fs'",
  renderSource: 'services:\n  - type: web\n    runtime: static\n    name: erp-eleven-frontend\n    staticPublishPath: ./frontend/dist\n' }
const advisory = { name: 'picomatch', dependency: 'picomatch', severity: 'high',
  range: '<=4.0.7', url: temporaryPicomatchRisk.advisory }
function audit() {
  return { auditReportVersion: 2, metadata: { vulnerabilities: { total: 2 } }, vulnerabilities: {
    picomatch: { nodes: ['node_modules/picomatch'], via: [{ ...advisory }] },
    vite: { nodes: ['node_modules/vite'], via: ['picomatch'] },
  } }
}
const context = { lock, now, latestPicomatch: '4.0.7' }

test('temporary acceptance preserves findings and covers only the reviewed root cause', () => {
  assert.deepEqual(evaluateAudit(audit(), context), { findings: 2, temporary: true })
  assert.deepEqual(validateExposure(exposure), lock)
})

test('any additional advisory, severity change or unreviewed package fails closed', () => {
  for (const change of [
    (report) => { report.vulnerabilities.picomatch.via.push({ ...advisory, url: 'https://github.com/advisories/GHSA-other' }) },
    (report) => { report.vulnerabilities.picomatch.via[0].severity = 'critical' },
    (report) => { report.vulnerabilities.vite.via.push('new-package') },
    (report) => { report.vulnerabilities.vite.nodes.push('node_modules/unreviewed/vite') },
    (report) => { report.vulnerabilities.picomatch.via = ['vite'] },
  ]) {
    const report = audit(); change(report)
    assert.throws(() => evaluateAudit(report, context))
  }
})

test('expiration or a new upstream version requires a new decision', () => {
  assert.throws(() => evaluateAudit(audit(), { ...context, now: new Date('2026-12-01') }), /expirou/)
  assert.throws(() => evaluateAudit(audit(), { ...context, latestPicomatch: '4.0.8' }), /outra versão/)
  const changed = structuredClone(lock); changed.packages['node_modules/picomatch'].version = '4.0.6'
  assert.throws(() => evaluateAudit(audit(), { ...context, lock: changed }), /Versão/)
})

test('network errors and incomplete npm reports cannot turn into success', () => {
  for (const report of [null, {}, { ...audit(), error: { code: 'ENOTFOUND' } },
    { ...audit(), vulnerabilities: {} }, { ...audit(), auditReportVersion: 3 }]) {
    assert.throws(() => evaluateAudit(report, context))
  }
  assert.deepEqual(evaluateAudit({ auditReportVersion: 2, metadata: { vulnerabilities: { total: 0 } },
    vulnerabilities: {} }, context), { findings: 0, temporary: false })
})

test('artifact must come from the current lock and a fresh nonempty bundle', () => {
  for (const changes of [
    { packageLockSha256: 'wrong' }, { builtAt: 'invalid' }, { modulesAnalyzed: 0 },
    { builtAt: '2026-11-17T20:00:00Z' }, { externals: ['picomatch'] },
    { packages: ['vue', 'picomatch'] },
  ]) assert.throws(() => validateExposure({ ...exposure, build: { ...build, ...changes } }))
  assert.throws(() => validateExposure({ ...exposure, renderSource: exposure.renderSource.replace('runtime: static', 'runtime: node') }))
})

test('direct, transitive and dynamic glob imports in the optional server block the exception', () => {
  for (const serverSource of ["import pm from 'picomatch'", "import vite from 'vite'",
    "const pm = require('picomatch')", "await import('picomatch')", 'await import(userInput)']) {
    assert.throws(() => validateExposure({ ...exposure, serverSource }))
  }
  assert.deepEqual(runtimeImports("import path from 'node:path'; import express from 'express'"), ['express'])
})

test('chunk evidence resolves both platform paths and nested node_modules without leaking paths', () => {
  assert.equal(modulePackage('/repo/node_modules/vite/node_modules/picomatch/index.js'), 'picomatch')
  assert.equal(modulePackage('C:\\repo\\node_modules\\@vue\\runtime-core\\index.js'), '@vue/runtime-core')
  assert.equal(modulePackage('/repo/src/views/PDV.vue'), null)
  assert.deepEqual(build.packages, ['vue'])
  assert.equal(build.modulesAnalyzed, 2)
  assert.equal(JSON.stringify(build).includes('/build/frontend'), false)
})

test('worker bundle modules are checked even when the parent only contains JS assets', () => {
  const worker = makeBuildReport({ 'worker.js': { ...bundle['assets/app.js'], modules: {
    '/repo/node_modules/picomatch/index.js': {},
  } } }, lockContent, now)
  const parent = makeBuildReport(bundle, lockContent, now, [worker])
  assert.deepEqual(parent.packages, ['vue'])
  assert.throws(() => validateExposure({ ...exposure, build: parent }), /picomatch/)
  assert.throws(() => validateExposure({ ...exposure, build: { ...build, workers: undefined } }), /inválido/)
})

test('Vite worker plugin shares its module evidence with the main report', () => {
  const plugins = buildSecurityReports()
  plugins.worker().generateBundle({}, bundle)
  let artifact
  plugins.main.generateBundle.call({ emitFile: (file) => { artifact = JSON.parse(file.source) } }, {}, bundle)
  assert.equal(artifact.workers.length, 1)
  assert.deepEqual(artifact.workers[0].packages, ['vue'])
})

test('a real Vite build cannot hide picomatch inside a worker asset', async () => {
  const { build: viteBuild } = await import('vite')
  const temporary = await mkdtemp(path.join(tmpdir(), 'eleven-worker-audit-'))
  try {
    const picomatch = fileURLToPath(new URL('../node_modules/picomatch/index.js', import.meta.url))
    await writeFile(path.join(temporary, 'main.js'), "new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });")
    await writeFile(path.join(temporary, 'worker.js'), `import picomatch from ${JSON.stringify(picomatch)}; postMessage(picomatch('*.js')('test.js'));`)
    const reports = buildSecurityReports()
    const result = await viteBuild({ root: temporary, configFile: false, logLevel: 'silent',
      plugins: [reports.main], worker: { format: 'es', plugins: () => [reports.worker()] },
      build: { write: false, rollupOptions: { input: path.join(temporary, 'main.js') } } })
    const report = JSON.parse(result.output.find((entry) => entry.fileName === 'security-build-report.json').source)
    assert.equal(report.packages.includes('picomatch'), false)
    assert.equal(report.workers.some((worker) => worker.packages.includes('picomatch')), true)
    const realLock = await readFile(new URL('../package-lock.json', import.meta.url), 'utf8')
    assert.throws(() => validateExposure({ ...exposure, lockContent: realLock, build: report, now: new Date() }), /picomatch/)
  } finally {
    await rm(temporary, { recursive: true, force: true })
  }
})
