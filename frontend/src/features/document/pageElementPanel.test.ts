import { describe, expect, it } from 'vitest'
import type { PageElement } from '../../shared/types'
import { pageElementDraftFromElement, pageElementPanelState } from './pageElementPanel'

describe('pageElementPanel', () => {
  it('builds editable draft defaults from the selected element', () => {
    expect(pageElementDraftFromElement(mkElement())).toEqual({
      content: 'Original',
      type: 'text',
      bbox: [1, 2, 3, 4],
    })
  })

  it('returns empty defaults when no element is selected', () => {
    expect(pageElementDraftFromElement(null)).toEqual({
      content: '',
      type: 'text',
      bbox: [0, 0, 0, 0],
    })
  })

  it('detects unchanged drafts as unsaveable with empty payload', () => {
    expect(
      pageElementPanelState({
        element: mkElement(),
        targetRef: 'draft-1',
        draftContent: 'Original',
        draftType: 'text',
        draftBbox: [1, 2, 3, 4],
        documentSaving: false,
      }),
    ).toEqual({ hasChanges: false, canSave: false, payload: {} })
  })

  it('emits only changed content/type/bbox fields', () => {
    expect(
      pageElementPanelState({
        element: mkElement(),
        targetRef: 'draft-1',
        draftContent: 'Updated',
        draftType: 'title',
        draftBbox: [9, 2, 3, 4],
        documentSaving: false,
      }),
    ).toEqual({
      hasChanges: true,
      canSave: true,
      payload: {
        content: 'Updated',
        type: 'title',
        bbox: [9, 2, 3, 4],
      },
    })
  })

  it('disables save while document edits are saving', () => {
    expect(
      pageElementPanelState({
        element: mkElement(),
        targetRef: 'draft-1',
        draftContent: 'Updated',
        draftType: 'text',
        draftBbox: [1, 2, 3, 4],
        documentSaving: true,
      }).canSave,
    ).toBe(false)
  })

  it('disables save when there is no editable target ref', () => {
    expect(
      pageElementPanelState({
        element: mkElement(),
        targetRef: null,
        draftContent: 'Updated',
        draftType: 'text',
        draftBbox: [1, 2, 3, 4],
        documentSaving: false,
      }).canSave,
    ).toBe(false)
  })
})

function mkElement(): PageElement {
  return {
    self_ref: '#/texts/12',
    draftRef: 'draft-1',
    type: 'text',
    content: 'Original',
    bbox: [1, 2, 3, 4],
    level: 0,
  }
}
