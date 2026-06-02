import { describe, expect, it } from 'vitest'
import type { DocTreeNode, DocumentEditCommandInput, DocumentRefRemap, Page, PageElement } from '../../shared/types'
import {
  postCommandSelectionState,
  reconcileSelectionState,
  selectionStateFromRef,
} from './parseTabSelection'

describe('parseTabSelection', () => {
  it('builds selection state from the selected ref', () => {
    expect(selectionStateFromRef('draft-1', [mkNode('#/texts/12', 'draft-1')], [mkPage([mkElement('#/texts/12', 'draft-1')], 3)])).toEqual({
      selectedRef: 'draft-1',
      selectedSelfRef: '#/texts/12',
      selectedPageNumber: 3,
    })
  })

  it('reconciles selection to a remapped draft ref', () => {
    const selection = {
      selectedRef: 'draft-old',
      selectedSelfRef: '#/texts/12',
      selectedPageNumber: 1,
    }
    const refRemaps: DocumentRefRemap[] = [{ draftRef: 'draft-new', selfRef: '#/texts/12', nodeKind: 'TextItem' }]

    expect(
      reconcileSelectionState(
        selection,
        [mkNode('#/texts/12', 'draft-new')],
        [mkPage([mkElement('#/texts/12', 'draft-new')])],
        refRemaps,
      ),
    ).toEqual({
      selectedRef: 'draft-new',
      selectedSelfRef: '#/texts/12',
      selectedPageNumber: 1,
    })
  })

  it('clears reconciled selection when the target disappears', () => {
    expect(
      reconcileSelectionState(
        { selectedRef: 'draft-old', selectedSelfRef: '#/texts/12', selectedPageNumber: 1 },
        [],
        [],
        [],
      ),
    ).toEqual({ selectedRef: null, selectedSelfRef: null, selectedPageNumber: null })
  })

  it('derives post-command selection state for inserted nodes', () => {
    const commands: DocumentEditCommandInput[] = [
      { action: 'insert_item', targetRef: 'draft-1', payload: { content: 'Inserted' } },
    ]
    const previousTree = [mkNode('#/texts/12', 'draft-1'), mkNode('#/texts/13', 'draft-2')]
    const nextTree = [mkNode('#/texts/12', 'draft-1'), mkNode('#/texts/14', 'draft-3'), mkNode('#/texts/13', 'draft-2')]
    const pages = [mkPage([mkElement('#/texts/12', 'draft-1'), mkElement('#/texts/14', 'draft-3'), mkElement('#/texts/13', 'draft-2')], 2)]

    expect(postCommandSelectionState(commands, previousTree, nextTree, pages)).toEqual({
      selectedRef: 'draft-3',
      selectedSelfRef: '#/texts/14',
      selectedPageNumber: 2,
    })
  })

  it('returns null when a command has no follow-up selection intent', () => {
    const commands: DocumentEditCommandInput[] = [
      { action: 'move_item_after', targetRef: 'draft-1', payload: { afterTargetRef: 'draft-2' } },
    ]

    expect(postCommandSelectionState(commands, [], [], [])).toBeNull()
  })
})

function mkNode(ref: string, draftRef = ref, children: DocTreeNode[] = []): DocTreeNode {
  return { ref, draftRef, type: 'text', label: ref, children }
}

function mkPage(elements: PageElement[], pageNumber = 1): Page {
  return { page_number: pageNumber, width: 600, height: 800, elements }
}

function mkElement(selfRef: string, draftRef = selfRef): PageElement {
  return {
    self_ref: selfRef,
    draftRef,
    type: 'text',
    content: 'content',
    bbox: [0, 0, 10, 10],
    level: 0,
  }
}
