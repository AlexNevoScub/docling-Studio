import type { DocumentEditCommitResult } from '../../shared/types'
import type { ParseTabSelectionState } from './parseTabSelection'
import {
  docChangeUiState,
  nextPageAfterSelection,
  shouldReloadTreeAfterCommit,
  shouldReloadTreeForAnalysisChange,
} from './parseTabWorkflow'

export interface ParseTabEventState {
  clearPreview: boolean
  currentPageNumber?: number
  clearSelection?: boolean
  clearFilter?: boolean
  reloadTree?: boolean
}

export function treeSelectEventState(
  currentPageNumber: number,
  selection: ParseTabSelectionState,
): ParseTabEventState {
  return {
    clearPreview: false,
    currentPageNumber: nextPageAfterSelection(currentPageNumber, selection),
  }
}

export function applyCommandsEventState(): ParseTabEventState {
  return { clearPreview: true }
}

export function commitDocumentEditsEventState(
  result: DocumentEditCommitResult | null,
): ParseTabEventState {
  return {
    clearPreview: true,
    reloadTree: shouldReloadTreeAfterCommit(result),
  }
}

export function discardDocumentEditsEventState(): ParseTabEventState {
  return { clearPreview: true }
}

export function docIdChangeEventState(
  pageNumbers: readonly { page_number: number }[],
  currentPageNumber: number,
): ParseTabEventState {
  const nextState = docChangeUiState(pageNumbers, currentPageNumber)
  return {
    clearPreview: false,
    currentPageNumber: nextState.currentPageNumber,
    clearSelection: true,
    clearFilter: true,
  }
}

export function analysisChangeEventState(
  nextAnalysisId: string | null | undefined,
  previousAnalysisId: string | null | undefined,
): ParseTabEventState {
  const reloadTree = shouldReloadTreeForAnalysisChange(nextAnalysisId, previousAnalysisId)
  return {
    clearPreview: false,
    clearSelection: reloadTree,
    reloadTree,
  }
}
