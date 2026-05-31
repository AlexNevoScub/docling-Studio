import { describe, expect, it } from 'vitest'
import type { DocTreeNode, DocumentRefRemap, Page } from '../../shared/types'
import { reconcileSelectedDraftRef, resolveSelectedSelfRef } from './editSelection'

describe('editSelection', () => {
  it('keeps the selected draft ref when it is still present', () => {
    expect(
      reconcileSelectedDraftRef('draft-1', '#/texts/12', [], [mkPage('draft-1', '#/texts/12')], []),
    ).toBe('draft-1')
  })

  it('remaps the selection to the current draft ref for the same self ref', () => {
    const refRemaps: DocumentRefRemap[] = [
      { draftRef: 'draft-2', selfRef: '#/texts/12', nodeKind: 'TextItem' },
    ]

    expect(reconcileSelectedDraftRef('draft-1', '#/texts/12', [], [], refRemaps)).toBe('draft-2')
  })

  it('falls back to the raw self ref after commit clears draft refs', () => {
    expect(
      reconcileSelectedDraftRef('draft-1', '#/texts/12', [mkTreeNode('#/texts/12')], [], []),
    ).toBe('#/texts/12')
  })

  it('clears the selection when the selected self ref no longer exists', () => {
    expect(reconcileSelectedDraftRef('draft-1', '#/texts/12', [], [], [])).toBeNull()
  })

  it('resolves the selected self ref from tree draft refs', () => {
    const tree = [mkTreeNode('#/groups/0', 'draft-group', [mkTreeNode('#/texts/12', 'draft-1')])]

    expect(resolveSelectedSelfRef('draft-1', tree, [])).toBe('#/texts/12')
  })
})

function mkTreeNode(ref: string, draftRef?: string, children: DocTreeNode[] = []): DocTreeNode {
  return {
    ref,
    draftRef,
    label: ref,
    type: 'text',
    children,
  }
}

function mkPage(draftRef: string, selfRef: string): Page {
  return {
    page_number: 1,
    width: 600,
    height: 800,
    elements: [
      {
        self_ref: selfRef,
        draftRef,
        type: 'text',
        content: 'content',
        bbox: [0, 0, 10, 10],
        level: 0,
      },
    ],
  }
}
