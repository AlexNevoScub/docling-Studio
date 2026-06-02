import { describe, expect, it } from 'vitest'
import type { DocTreeNode, Page, PageElement } from '../../shared/types'
import {
  applyPageElementPreview,
  countTreeNodes,
  elementTargetRef,
  filterTreeNodes,
  findElementByRef,
  findPageNumberForRef,
} from './parseTabState'

describe('parseTabState', () => {
  it('prefers draftRef for element identity', () => {
    expect(elementTargetRef(mkElement({ draftRef: 'draft-1', self_ref: '#/texts/12' }))).toBe('draft-1')
    expect(elementTargetRef(mkElement({ draftRef: undefined, self_ref: '#/texts/12' }))).toBe('#/texts/12')
  })

  it('counts tree nodes recursively', () => {
    expect(countTreeNodes([mkNode('#/groups/0', [mkNode('#/texts/1'), mkNode('#/texts/2')])])).toBe(3)
  })

  it('filters tree nodes while preserving matching ancestors', () => {
    const filtered = filterTreeNodes(
      [mkNode('#/groups/0', [mkNode('#/texts/1', [], 'Alpha'), mkNode('#/texts/2', [], 'Beta')], 'Group')],
      'beta',
    )

    expect(filtered).toEqual([
      mkNode('#/groups/0', [mkNode('#/texts/2', [], 'Beta')], 'Group'),
    ])
  })

  it('applies transient preview changes only to the targeted element', () => {
    const pages = [mkPage([mkElement({ draftRef: 'draft-1', content: 'Old' }), mkElement({ draftRef: 'draft-2', content: 'Keep' })])]

    expect(
      applyPageElementPreview(pages, {
        targetRef: 'draft-1',
        payload: { content: 'Patched', type: 'title', bbox: [9, 9, 9, 9] },
      }),
    ).toEqual([
      mkPage([
        mkElement({ draftRef: 'draft-1', content: 'Patched', type: 'title', bbox: [9, 9, 9, 9] }),
        mkElement({ draftRef: 'draft-2', content: 'Keep' }),
      ]),
    ])
  })

  it('finds the page number for a selected ref', () => {
    const pages = [mkPage([mkElement({ draftRef: 'draft-1' })], 1), mkPage([mkElement({ draftRef: 'draft-2' })], 2)]
    expect(findPageNumberForRef(pages, 'draft-2')).toBe(2)
    expect(findPageNumberForRef(pages, 'missing')).toBeNull()
  })

  it('finds the selected element across all pages', () => {
    const target = mkElement({ draftRef: 'draft-2', content: 'Found me' })
    const pages = [mkPage([mkElement({ draftRef: 'draft-1' })], 1), mkPage([target], 2)]

    expect(findElementByRef(pages, 'draft-2')).toEqual(target)
    expect(findElementByRef(pages, null)).toBeNull()
  })
})

function mkNode(ref: string, children: DocTreeNode[] = [], label = ref): DocTreeNode {
  return { ref, draftRef: ref, type: 'text', label, children }
}

function mkPage(elements: PageElement[], pageNumber = 1): Page {
  return { page_number: pageNumber, width: 600, height: 800, elements }
}

function mkElement(overrides: Partial<PageElement> = {}): PageElement {
  return {
    self_ref: '#/texts/12',
    draftRef: 'draft-1',
    type: 'text',
    content: 'Original',
    bbox: [1, 2, 3, 4],
    level: 0,
    ...overrides,
  }
}
