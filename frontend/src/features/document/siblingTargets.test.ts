import { describe, expect, it } from 'vitest'
import type { DocTreeNode } from '../../shared/types'
import { adjacentGroupSiblingRefs, adjacentSiblingRefs } from './siblingTargets'

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

  it('finds adjacent group siblings for reparent targets', () => {
    const tree = [
      mkNode('#/groups/0', 'draft-group-0', [], 'group'),
      mkNode('#/texts/12', 'draft-2'),
      mkNode('#/groups/1', 'draft-group-1', [], 'group'),
    ]

    expect(adjacentGroupSiblingRefs(tree, 'draft-2')).toEqual({
      previousGroupRef: 'draft-group-0',
      nextGroupRef: 'draft-group-1',
    })
  })
})

function mkNode(ref: string, draftRef?: string, children: DocTreeNode[] = [], type = 'text'): DocTreeNode {
  return {
    ref,
    draftRef,
    type,
    label: ref,
    children,
  }
}
