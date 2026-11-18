import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import ts from 'typescript'
import { reportName, sha256 } from './build-security-report.mjs'

export const temporaryPicomatchRisk = Object.freeze({
  advisory: 'https://github.com/advisories/GHSA-fc5q-39xc-vjpf',
  expiresAt: '2026-12-01T00:00:00.000Z',
  reviewedVersions: ['2.3.2', '4.0.4', '4.0.7'],
  latestReviewed: '4.0.7',
})
const globPackages = new Set(['picomatch', 'micromatch', 'fast-glob', 'tinyglobby', 'fdir'])

export function runtimeImports(source) {
  const parsed = ts.createSourceFile('server.js', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS)
  if (parsed.parseDiagnostics.length) throw new Error('Código do servidor não pôde ser analisado.')
  const imports = new Set()
  function visit(node) {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier) {
      if (!ts.isStringLiteral(node.moduleSpecifier)) throw new Error('Import de runtime não verificável.')
      imports.add(node.moduleSpecifier.text)
    }
    if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword
      || ts.isIdentifier(node.expression) && node.expression.text === 'require')) {
      if (node.arguments.length !== 1 || !ts.isStringLiteral(node.arguments[0])) {
        throw new Error('Import dinâmico de runtime não verificável.')
      }
      imports.add(node.arguments[0].text)
    }
    ts.forEachChild(node, visit)
  }
  visit(parsed)
  if (imports.has('node:module')) throw new Error('Carregador de módulos dinâmicos requer revisão de segurança.')
  return [...imports].filter((name) => !name.startsWith('node:'))
}

function runtimeDependencyNames(lock, serverSource) {
  const names = new Set()
  function resolve(name, from = '', optional = false) {
    let parent = from
    while (parent) {
      const candidate = `${parent}/node_modules/${name}`
      if (lock.packages[candidate]) return candidate
      parent = parent.includes('/node_modules/') ? parent.slice(0, parent.lastIndexOf('/node_modules/')) : ''
    }
    const candidate = `node_modules/${name}`
    if (!lock.packages[candidate]) {
      if (optional) return null
      throw new Error(`Dependência de runtime ausente no lock: ${name}`)
    }
    return candidate
  }
  const visited = new Set()
  function traverse(name, from, optional = false) {
    if (name.startsWith('.') || name.startsWith('/')) throw new Error('Novo módulo local no servidor requer revisão de segurança.')
    const path = resolve(name, from, optional)
    if (!path) return
    names.add(name)
    if (visited.has(path)) return
    visited.add(path)
    for (const child of Object.keys(lock.packages[path].dependencies || {})) traverse(child, path)
    for (const child of Object.keys(lock.packages[path].optionalDependencies || {})) traverse(child, path)
    for (const peer of Object.keys(lock.packages[path].peerDependencies || {})) {
      traverse(peer, path, lock.packages[path].peerDependenciesMeta?.[peer]?.optional === true)
    }
  }
  for (const name of runtimeImports(serverSource)) traverse(name)
  return names
}

export function validateExposure({ lockContent, build, serverSource, renderSource, now = new Date() }) {
  const lock = JSON.parse(lockContent)
  if (!lock.packages || lock.lockfileVersion !== 3) throw new Error('Formato do lock não suportado pela revisão.')
  const emittedPackages = new Set()
  function inspect(report) {
    if (report?.version !== 1 || report.packageLockSha256 !== sha256(lockContent)) {
      throw new Error('Faça um build com o lock atual antes da auditoria.')
    }
    const age = now.getTime() - new Date(report.builtAt).getTime()
    if (!Number.isFinite(age) || age < -60_000 || age > 30 * 60_000) throw new Error('Relatório do build ausente, antigo ou inválido.')
    if (!(report.modulesAnalyzed > 0 && report.chunksAnalyzed > 0) || !Array.isArray(report.packages)
      || !Array.isArray(report.externals) || !Array.isArray(report.workers)) throw new Error('Relatório de módulos do build inválido.')
    if (report.externals.length) throw new Error(`Imports externos no bundle requerem revisão: ${report.externals.join(', ')}`)
    for (const name of report.packages) emittedPackages.add(name)
    for (const worker of report.workers) inspect(worker)
  }
  inspect(build)
  const runtimeNames = runtimeDependencyNames(lock, serverSource)
  const shipped = [...emittedPackages, ...runtimeNames].filter((name) => globPackages.has(name))
  if (shipped.length) throw new Error(`Pacote de glob alcançável no runtime: ${[...new Set(shipped)].join(', ')}`)
  const service = renderSource.split(/\n(?=  - type:)/).find((block) => /name: erp-eleven-frontend\s*(?:\n|$)/.test(block))
  if (!service || !/runtime: static\s*(?:\n|$)/.test(service)
    || !/staticPublishPath: \.\/frontend\/dist\s*(?:\n|$)/.test(service)) {
    throw new Error('A exceção foi revisada somente para o frontend estático do Render.')
  }
  return lock
}

export function evaluateAudit(audit, { lock, now = new Date(), latestPicomatch }) {
  if (audit?.auditReportVersion !== 2 || audit.error || !audit.vulnerabilities
    || typeof audit.vulnerabilities !== 'object' || Array.isArray(audit.vulnerabilities) || !audit.metadata?.vulnerabilities) {
    throw new Error('Auditoria npm incompleta ou inválida; nenhum alerta pode ser dispensado.')
  }
  const findings = Object.entries(audit.vulnerabilities)
  if (audit.metadata.vulnerabilities.total !== findings.length) throw new Error('Auditoria npm inconsistente.')
  if (findings.length === 0) {
    return { findings: 0, temporary: false }
  }
  if (now.getTime() >= new Date(temporaryPicomatchRisk.expiresAt).getTime()) {
    throw new Error('Exceção temporária de picomatch expirou. Atualize ou faça nova revisão explícita.')
  }
  if (latestPicomatch !== temporaryPicomatchRisk.latestReviewed) {
    throw new Error('Há outra versão publicada de picomatch; reveja a correção antes de usar a exceção.')
  }
  let advisorySeen = false
  function check(name, ancestors = new Set()) {
    const finding = audit.vulnerabilities[name]
    if (!finding || ancestors.has(name) || !Array.isArray(finding.via) || !finding.via.length) {
      throw new Error(`Cadeia de auditoria não verificável: ${name}`)
    }
    if (!Array.isArray(finding.nodes) || !finding.nodes.length
      || finding.nodes.some((path) => !lock.packages[path])) throw new Error(`Dependência fora do lock: ${name}`)
    const path = new Set([...ancestors, name])
    for (const cause of finding.via) {
      if (typeof cause === 'string') check(cause, path)
      else if (cause?.name === 'picomatch' && cause.dependency === 'picomatch'
        && cause.url === temporaryPicomatchRisk.advisory && cause.severity === 'high'
        && cause.range === '<=4.0.7' && name === 'picomatch') {
        if (finding.nodes.some((node) => !temporaryPicomatchRisk.reviewedVersions.includes(lock.packages[node].version))) {
          throw new Error('Versão picomatch não incluída na revisão temporária.')
        }
        advisorySeen = true
      } else throw new Error(`Vulnerabilidade exige correção: ${name} — ${cause?.url || 'advisory desconhecido'}`)
    }
  }
  for (const [name] of findings) check(name)
  if (!advisorySeen) throw new Error('Nenhuma causa conhecida para a exceção temporária.')
  return { findings: findings.length, temporary: true }
}

function npmJson(args, root) {
  const result = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', args,
    { cwd: root, encoding: 'utf8', timeout: 60_000, maxBuffer: 8 * 1024 * 1024 })
  // Keep the original npm report visible, including all advisory chains.
  if (result.stdout) process.stdout.write(result.stdout)
  if (result.stderr) process.stderr.write(result.stderr)
  if (result.error || result.signal || ![0, 1].includes(result.status)) throw new Error('Falha ao consultar a auditoria npm; verificação bloqueada.')
  try { return JSON.parse(result.stdout) } catch { throw new Error('Resposta npm não é JSON válido; verificação bloqueada.') }
}

export function main() {
  const root = fileURLToPath(new URL('../', import.meta.url))
  const lockContent = readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8')
  const build = JSON.parse(readFileSync(new URL(`../dist/${reportName}`, import.meta.url), 'utf8'))
  const lock = validateExposure({ lockContent, build,
    serverSource: readFileSync(new URL('../server.js', import.meta.url), 'utf8'),
    renderSource: readFileSync(new URL('../../render.yaml', import.meta.url), 'utf8') })
  const audit = npmJson(['audit', '--include=dev', '--json'], root)
  const latestPicomatch = Object.keys(audit.vulnerabilities || {}).length
    ? npmJson(['view', 'picomatch', 'version', '--json'], root) : undefined
  const result = evaluateAudit(audit, { lock, latestPicomatch })
  if (result.temporary) {
    console.warn(`RISCO TEMPORARIAMENTE ACEITO, NÃO CORRIGIDO: ${temporaryPicomatchRisk.advisory}`)
    console.warn(`ReDoS em glob definido pelo autor do build; não presente no bundle ou servidor. ${result.findings} alertas transitivos continuam visíveis. Expira ${temporaryPicomatchRisk.expiresAt}.`)
  } else console.info('Auditoria completa: nenhuma vulnerabilidade reportada pelo npm.')
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { main() } catch (error) { console.error(error.message); process.exitCode = 1 }
}
