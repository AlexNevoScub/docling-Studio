import type { DocumentEditCommitResult, Page } from '../../shared/types'
import type { ParseTabSelectionState } from './parseTabSelection'

export function firstWorkspacePageNumber(
  pages: readonly Page[],
  fallbackPageNumber = 1,
): number {
  return pages[0]?.page_number ?? fallbackPageNumber
}

export function nextPageAfterSelection(
  currentPageNumber: number,
  selection: ParseTabSelectionState,
): number {
  return selection.selectedPageNumber ?? currentPageNumber
}

export function shouldReloadTreeForAnalysisChange(
  nextAnalysisId: string | null | undefined,
  previousAnalysisId: string | null | undefined,
): boolean {
  return Boolean(nextAnalysisId && nextAnalysisId !== previousAnalysisId)
}

export function shouldReloadTreeAfterCommit(
  result: DocumentEditCommitResult | null,
): boolean {
  return Boolean(result?.committed)
}

export function docChangeUiState(pages: readonly Page[], fallbackPageNumber = 1): {
  currentPageNumber: number
  filter: string
  selection: ParseTabSelectionState
} {
  return {
    currentPageNumber: firstWorkspacePageNumber(pages, fallbackPageNumber),
    filter: '',
    selection: {
      selectedRef: null,
      selectedSelfRef: null,
      selectedPageNumber: null,
    },
  }
}
