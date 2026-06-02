import { describe, expect, it } from 'vitest'
import type { DocumentEditCommitResult, Page } from '../../shared/types'
import {
  docChangeUiState,
  firstWorkspacePageNumber,
  nextPageAfterSelection,
  shouldReloadTreeAfterCommit,
  shouldReloadTreeForAnalysisChange,
} from './parseTabWorkflow'

describe('parseTabWorkflow', () => {
  it('uses the first workspace page number when available', () => {
    expect(firstWorkspacePageNumber([mkPage(3), mkPage(4)])).toBe(3)
  })

  it('falls back to page 1 when the workspace has no pages', () => {
    expect(firstWorkspacePageNumber([])).toBe(1)
    expect(firstWorkspacePageNumber([], 7)).toBe(7)
  })

  it('moves current page to the selected page when present', () => {
    expect(
      nextPageAfterSelection(1, {
        selectedRef: 'draft-1',
        selectedSelfRef: '#/texts/12',
        selectedPageNumber: 4,
      }),
    ).toBe(4)
  })

  it('keeps the current page when selection has no page number', () => {
    expect(
      nextPageAfterSelection(2, {
        selectedRef: 'draft-1',
        selectedSelfRef: '#/texts/12',
        selectedPageNumber: null,
      }),
    ).toBe(2)
  })

  it('reloads the tree only when the analysis id actually changes', () => {
    expect(shouldReloadTreeForAnalysisChange('a2', 'a1')).toBe(true)
    expect(shouldReloadTreeForAnalysisChange('a1', 'a1')).toBe(false)
    expect(shouldReloadTreeForAnalysisChange(null, 'a1')).toBe(false)
  })

  it('reloads the tree only after a committed draft edit result', () => {
    expect(shouldReloadTreeAfterCommit(mkCommitResult(true))).toBe(true)
    expect(shouldReloadTreeAfterCommit(mkCommitResult(false))).toBe(false)
    expect(shouldReloadTreeAfterCommit(null)).toBe(false)
  })

  it('builds the UI reset state for document changes', () => {
    expect(docChangeUiState([mkPage(5)], 1)).toEqual({
      currentPageNumber: 5,
      filter: '',
      selection: {
        selectedRef: null,
        selectedSelfRef: null,
        selectedPageNumber: null,
      },
    })
  })
})

function mkPage(pageNumber: number): Page {
  return {
    page_number: pageNumber,
    width: 600,
    height: 800,
    elements: [],
  }
}

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
