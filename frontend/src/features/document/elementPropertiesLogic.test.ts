import { describe, expect, it } from 'vitest'
import type { DocChunk, PageElement } from '../../shared/types'
import { chunkPanelState } from './chunkPanel'
import {
  chunkDraftTextFromChunk,
  chunkSaveOutcome,
  elementPropertiesDraftStateFromElement,
  pageElementPreviewOutcome,
  pageElementSaveOutcome,
} from './elementPropertiesLogic'
import { pageElementPanelState } from './pageElementPanel'

describe('elementPropertiesLogic', () => {
  it('builds reset draft state from the selected element', () => {
    const draftState = elementPropertiesDraftStateFromElement(mkElement())

    expect(draftState.pageElementDraft).toEqual({
      content: 'Hello',
      type: 'text',
      bbox: [1, 2, 3, 4],
    })
    expect(draftState.insertAfterContent).toBe('')
    expect(draftState.splitIndex).toBe(1)
  })

  it('returns a preview outcome only when there are page element changes', () => {
    const state = pageElementPanelState({
      element: mkElement(),
      targetRef: 'draft-1',
      draftContent: 'Updated',
      draftType: 'text',
      draftBbox: [1, 2, 3, 4],
      documentSaving: false,
    })

    expect(pageElementPreviewOutcome('draft-1', state)).toEqual({
      kind: 'preview',
      targetRef: 'draft-1',
      payload: { content: 'Updated' },
    })
  })

  it('clears the preview when nothing changed or no target ref exists', () => {
    const unchangedState = pageElementPanelState({
      element: mkElement(),
      targetRef: 'draft-1',
      draftContent: 'Hello',
      draftType: 'text',
      draftBbox: [1, 2, 3, 4],
      documentSaving: false,
    })

    expect(pageElementPreviewOutcome('draft-1', unchangedState)).toEqual({ kind: 'clear' })
    expect(pageElementPreviewOutcome(null, unchangedState)).toEqual({ kind: 'clear' })
  })

  it('returns a save outcome only when there are page element changes', () => {
    const state = pageElementPanelState({
      element: mkElement(),
      targetRef: 'draft-1',
      draftContent: 'Updated',
      draftType: 'text',
      draftBbox: [1, 2, 3, 4],
      documentSaving: false,
    })

    expect(pageElementSaveOutcome('draft-1', state)).toEqual({
      kind: 'save',
      targetRef: 'draft-1',
      payload: { content: 'Updated' },
    })
  })

  it('returns close when saving an unchanged chunk draft', () => {
    const chunk = mkChunk()
    const state = chunkPanelState(chunk, chunk.text, false)

    expect(chunkSaveOutcome(chunk, chunk.text, state)).toEqual({ kind: 'close' })
  })

  it('returns a save payload when chunk text changed', () => {
    const chunk = mkChunk()
    const state = chunkPanelState(chunk, 'Updated chunk', false)

    expect(chunkSaveOutcome(chunk, 'Updated chunk', state)).toEqual({
      kind: 'save',
      chunkId: 'c1',
      text: 'Updated chunk',
    })
  })

  it('derives initial chunk draft text from the linked chunk', () => {
    expect(chunkDraftTextFromChunk(mkChunk())).toBe('Chunk text')
    expect(chunkDraftTextFromChunk(null)).toBe('')
  })
})

function mkElement(overrides: Partial<PageElement> = {}): PageElement {
  return {
    self_ref: '#/texts/12',
    draftRef: 'draft-1',
    type: 'text',
    content: 'Hello',
    bbox: [1, 2, 3, 4],
    level: 0,
    ...overrides,
  }
}

function mkChunk(overrides: Partial<DocChunk> = {}): DocChunk {
  return {
    id: 'c1',
    sequence: 1,
    text: 'Chunk text',
    tokenCount: 3,
    ...overrides,
  }
}
