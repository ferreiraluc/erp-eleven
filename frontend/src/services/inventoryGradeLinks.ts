export interface GradeCardRect { id: string; group: string | null; left: number; right: number; top: number; bottom: number }
export interface GradeLink { id: string; path: string }

/** Only adjacent visible cards with the same explicit grade are connected. */
export function gradeLinks(cards: GradeCardRect[]): GradeLink[] {
  const links: GradeLink[] = []
  for (let i = 1; i < cards.length; i++) {
    const a = cards[i - 1]!, b = cards[i]!
    if (!a.group || a.group !== b.group) continue
    const ax = (a.left + a.right) / 2, bx = (b.left + b.right) / 2
    let path: string
    if (Math.abs(a.top - b.top) < 2 && b.left >= a.right) {
      const y = (Math.max(a.top, b.top) + Math.min(a.bottom, b.bottom)) / 2
      path = `M ${a.right} ${y} H ${b.left}`
    } else if (b.top >= a.bottom) {
      const gap = (a.bottom + b.top) / 2
      path = `M ${ax} ${a.bottom} V ${gap} H ${bx} V ${b.top}`
    } else continue // Never draw through overlapping or non-adjacent rows.
    links.push({ id: `${a.id}:${b.id}`, path })
  }
  return links
}
