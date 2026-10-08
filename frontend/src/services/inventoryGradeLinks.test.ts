import { describe, expect, it } from 'vitest'
import { gradeLinks, type GradeCardRect } from './inventoryGradeLinks'
const card = (id: string, group: string | null, left: number, top: number): GradeCardRect => ({ id, group, left, right: left + 100, top, bottom: top + 80 })
describe('Explicit grade connections', () => {
  it('connects neighbors horizontally, across a responsive row wrap and vertically in list view', () => {
    expect(gradeLinks([card('a','g',0,0), card('b','g',110,0), card('c','g',0,90)])).toEqual([
      { id: 'a:b', path: 'M 100 40 H 110' }, { id: 'b:c', path: 'M 160 80 V 85 H 50 V 90' },
    ])
    expect(gradeLinks([card('a','g',0,0), card('b','g',0,90)])[0]?.path).toBe('M 50 80 V 85 H 50 V 90')
  })
  it('never connects ungrouped items, different grades or a grade across unrelated products', () => {
    expect(gradeLinks([card('a','g',0,0), card('b','other',110,0), card('c','g',0,90)])).toEqual([])
    expect(gradeLinks([card('a',null,0,0), card('b',null,110,0)])).toEqual([])
  })
})
