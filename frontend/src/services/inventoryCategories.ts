/** Category names are user data: compare normalized text without changing the saved spelling. */
export function categoryKey(value: string): string {
  return value.normalize('NFKD').replace(/\p{M}/gu, '').trim().toLowerCase().replace(/\s+/g, ' ')
}

export function splitCategoryPath(value: string): { parent: string; child: string } {
  const [parent, ...children] = value.split('>').map(part => part.trim())
  return { parent, child: children.join('>') }
}

export function categoryOptions(paths: string[]) {
  const parents = new Map<string, string>()
  const children = new Map<string, Map<string, string>>()
  for (const path of paths) {
    const { parent, child } = splitCategoryPath(path)
    const key = categoryKey(parent)
    if (!key) continue
    // Retired catch-all choices remain valid on old items, but are not proposed for new ones.
    if (!['outros', 'outra', 'outra...'].includes(key) && !parents.has(key)) parents.set(key, parent)
    if (child) {
      const siblings = children.get(key) || new Map<string, string>()
      const childKey = categoryKey(child)
      if (!siblings.has(childKey)) siblings.set(childKey, child)
      children.set(key, siblings)
    }
  }
  const sorted = (values: Iterable<string>) => [...values].sort((a, b) => a.localeCompare(b))
  return {
    parents: sorted(parents.values()),
    children: new Map([...children].map(([key, values]) => [key, sorted(values.values())])),
  }
}
