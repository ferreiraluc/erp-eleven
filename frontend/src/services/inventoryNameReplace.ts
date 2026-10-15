/** Literal word/phrase replacement. Never interpret regexes or $ replacement syntax. */
export function replaceProductName(name: string, find: string, replacement: string): string {
  const source = find.trim(), target = replacement.trim()
  if (!source || !target) return name
  const escaped = source.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const pattern = new RegExp(`(^|[^\\p{L}\\p{N}])(${escaped})(?=$|[^\\p{L}\\p{N}])`, 'giu')
  return name.replace(pattern, (_match, prefix: string) => prefix + target)
}
