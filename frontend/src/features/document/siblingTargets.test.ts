import { describe, expect, it } from 'vitest'
import type { DocTreeNode } from '../../shared/types'
import { adjacentSiblingRefs } from './siblingTargets'

describe('siblingTargets', () => {
  it('finds adjacent root siblings', () => {
    const tree = [mkNode('#/texts/11', 'draft-1'), mkNode('#/texts/12', 'draft-2'), mkNode('#/texts/13', 'draft-3')]

    expect(adjacentSiblingRefs(tree, 'draft-2')).toEqual({
      previousSiblingRef: 'draft-1',
      nextSiblingRef: 'draft-3',
    })
  })

  it('finds adjacent nested siblings', () => {
    const tree = [
      mkNode('#/groups/0', 'draft-group', [
        mkNode('#/texts/11', 'draft-1'),
        mkNode('#/texts/12', 'draft-2'),
        mkNode('#/texts/13', 'draft-3'),
      ]),
    ]

    expect(adjacentSiblingRefs(tree, 'draft-2')).toEqual({
      previousSiblingRef: 'draft-1',
      nextSiblingRef: 'draft-3',
    })
  })

  it('returns null neighbors for the first or missing node', () => {
    const tree = [mkNode('#/texts/11', 'draft-1'), mkNode('#/texts/12', 'draft-2')]

    expect(adjacentSiblingRefs(tree, 'draft-1')).toEqual({
      previousSiblingRef: null,
      nextSiblingRef: 'draft-2',
    })
    expect(adjacentSiblingRefs(tree, 'draft-missing')).toEqual({
      previousSiblingRef: null,
      nextSiblingRef: null,
    })
  })
})

function mkNode(ref: string, draftRef?: string, children: DocTreeNode[] = []): DocTreeNode {
  return {
    ref,
    draftRef,
    type: 'text',
    label: ref,
    children,
  }
}
