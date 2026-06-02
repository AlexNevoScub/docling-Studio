import { describe, expect, it } from 'vitest'
import type { DocumentEditCommitResult } from '../../shared/types'
import {
  analysisChangeEventState,
  applyCommandsEventState,
  commitDocumentEditsEventState,
  discardDocumentEditsEventState,
  docIdChangeEventState,
  treeSelectEventState,
} from './parseTabEvents'

describe('parseTabEvents', () => {
  it('moves current page after tree selection when the selection has a page', () => {
    expect(
      treeSelectEventState(1, {
        selectedRef: 'draft-1',
        selectedSelfRef: '#/texts/12',
        selectedPageNumber: 4,
      }),
    ).toEqual({ clearPreview: false, currentPageNumber: 4 })
  })

  it('marks command apply and discard handlers to clear the preview', () => {
    expect(applyCommandsEventState()).toEqual({ clearPreview: true })
    expect(discardDocumentEditsEventState()).toEqual({ clearPreview: true })
  })

  it('reloads tree after committed draft edits only', () => {
    expect(commitDocumentEditsEventState(mkCommitResult(true))).toEqual({
      clearPreview: true,
      reloadTree: true,
    })
    expect(commitDocumentEditsEventState(mkCommitResult(false))).toEqual({
      clearPreview: true,
      reloadTree: false,
    })
  })

  it('clears selection and filter on document changes while choosing the first page', () => {
    expect(docIdChangeEventState([{ page_number: 7 }], 1)).toEqual({
      clearPreview: false,
      currentPageNumber: 7,
      clearSelection: true,
      clearFilter: true,
    })
  })

  it('reloads tree and clears selection only for real analysis changes', () => {
    expect(analysisChangeEventState('a2', 'a1')).toEqual({
      clearPreview: false,
      clearSelection: true,
      reloadTree: true,
    })
    expect(analysisChangeEventState('a1', 'a1')).toEqual({
      clearPreview: false,
      clearSelection: false,
      reloadTree: false,
    })
  })
})

function mkCommitResult(committed: boolean): DocumentEditCommitResult {
  return {
    committed,
    analysisId: 'a1',
    pages: [],
    tree: [],
    pagePatches: [],
    treePatches: [],
    refRemaps: [],
  }
}
