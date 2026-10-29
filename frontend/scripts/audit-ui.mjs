/** Interface contracts, checked across every Vue template without rendering data. */
import fs from 'node:fs'
import path from 'node:path'
import { parse } from '@vue/compiler-sfc'
import { parse as parseTemplate } from '@vue/compiler-dom'
const root = path.resolve(import.meta.dirname, '../src')
const issues = []
let components = 0,
  dialogs = 0,
  buttons = 0
const files = (dir) =>
  fs
    .readdirSync(dir, { withFileTypes: true })
    .flatMap((entry) =>
      entry.isDirectory()
        ? files(path.join(dir, entry.name))
        : entry.name.endsWith('.vue')
          ? [path.join(dir, entry.name)]
          : [],
    )
function meaningfulContent(node) {
  if (node.type === 5) return true // Rendered translated/dynamic label.
  if (node.type === 2)
    return !!node.content.trim() && !['×', '✕', '✖', 'x', 'X'].includes(node.content.trim())
  if (node.type === 1 && node.tag === 'svg') return false
  return (node.children || []).some(meaningfulContent)
}
for (const file of files(root)) {
  const relative = path.relative(root, file)
  const { descriptor, errors } = parse(fs.readFileSync(file, 'utf8'))
  if (errors.length) {
    issues.push(`${relative}: invalid SFC`)
    continue
  }
  if (!descriptor.template) continue
  components++
  let ast
  try {
    ast = parseTemplate(descriptor.template.content)
  } catch {
    issues.push(`${relative}: invalid template`)
    continue
  }
  function walk(node, inForm = false) {
    if (node.type === 1) {
      const prop = (name) =>
        node.props.some(
          (value) => value.name === name || (value.type === 7 && value.arg?.content === name),
        )
      const attr = (name) => node.props.find((value) => value.name === name)?.value?.content
      const location = `${relative}:${node.loc.start.line + descriptor.template.loc.start.line - 1}`
      if (node.tag === 'select') issues.push(`${location}: use ErpSelect/ErpDropdown`)
      if (node.tag === 'button') {
        buttons++
        if (
          !meaningfulContent(node) &&
          !prop('aria-label') &&
          !prop('aria-labelledby') &&
          !prop('title')
        )
          issues.push(`${location}: icon button needs an accessible name`)
        if (inForm && !prop('type'))
          issues.push(`${location}: declare button/submit explicitly inside a form`)
      }
      const isDialog =
        ['dialog', 'alertdialog'].includes(attr('role')) ||
        /(^| )erp-dialog( |$)/.test(attr('class') || '')
      if (isDialog) {
        dialogs++
        const notificationPopover =
          relative === 'components/notifications/NotificationBell.vue' &&
          attr('aria-modal') === 'false'
        if (!prop('erp-dialog') && !notificationPopover)
          issues.push(`${location}: modal needs the shared keyboard/scroll lifecycle`)
      }
      inForm ||= node.tag === 'form'
    }
    for (const child of node.children || []) walk(child, inForm)
  }
  walk(ast)
}
console.log(
  `UI audit: ${components} Vue components, ${dialogs} dialog surfaces, ${buttons} buttons`,
)
if (issues.length) {
  console.error(issues.join('\n'))
  process.exitCode = 1
} else
  console.log('Selectors, dialog lifecycle, named icon controls and explicit form actions verified')
