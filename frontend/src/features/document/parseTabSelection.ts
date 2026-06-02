import type { DocTreeNode, DocumentEditCommandInput, DocumentRefRemap, Page } from '../../shared/types'
import { reconcileSelectedDraftRef, resolveSelectedSelfRef } from './editSelection'
import { findPageNumberForRef } from './parseTabState'
import { postCommandSelectionRef } from './structuralSelection'

export interface ParseTabSelectionState {
  selectedRef: string | null
  selectedSelfRef: string | null
  selectedPageNumber: number | null
}

export function selectionStateFromRef(
  selectedRef: string | null,
  tree: readonly DocTreeNode[],
  pages: readonly Page[],
): ParseTabSelectionState {
  const selectedSelfRef = resolveSelectedSelfRef(selectedRef, tree, pages)
  return {
    selectedRef,
    selectedSelfRef,
    selectedPageNumber: selectedRef ? findPageNumberForRef(pages, selectedRef) : null,
  }
}

export function reconcileSelectionState(
  selection: ParseTabSelectionState,
  tree: readonly DocTreeNode[],
  pages: readonly Page[],
  refRemaps: readonly DocumentRefRemap[],
): ParseTabSelectionState {
  if (!selection.selectedRef) return selection

  const nextSelectedRef = reconcileSelectedDraftRef(
    selection.selectedRef,
    selection.selectedSelfRef,
    tree,
    pages,
    refRemaps,
  )

  if (!nextSelectedRef) {
    return {
      selectedRef: null,
      selectedSelfRef: null,
      selectedPageNumber: null,
    }
  }

  return selectionStateFromRef(nextSelectedRef, tree, pages)
}

export function postCommandSelectionState(
  commands: readonly DocumentEditCommandInput[],
  previousTree: readonly DocTreeNode[],
  nextTree: readonly DocTreeNode[],
  pages: readonly Page[],
): ParseTabSelectionState | null {
  const nextSelectedRef = postCommandSelectionRef(commands, previousTree, nextTree)
  if (!nextSelectedRef) return null
  return selectionStateFromRef(nextSelectedRef, nextTree, pages)
}
