import type { DocumentEditCommandInput } from '../../shared/types'
import {
  buildDeleteItemCommand,
  buildInsertItemAfterCommand,
  buildMergeItemsCommand,
  buildMoveItemAfterCommand,
  buildMoveItemBeforeCommand,
  buildReparentItemCommand,
  buildSplitItemCommand,
} from './structuralCommands'

export interface StructuralPanelInputs {
  targetRef: string | null
  draftContent: string
  insertAfterContent: string
  splitIndex: number
  documentSaving: boolean
  previousSiblingTargetRef?: string | null
  nextSiblingTargetRef?: string | null
  previousGroupTargetRef?: string | null
  nextGroupTargetRef?: string | null
  parentGroupTargetRef?: string | null
}

export interface StructuralPanelState {
  maxSplitIndex: number
  canInsertAfter: boolean
  canSplit: boolean
  canMoveBefore: boolean
  canMoveAfter: boolean
  canMergeNext: boolean
  canMoveIntoPreviousGroup: boolean
  canMoveIntoNextGroup: boolean
  canMoveToParentGroup: boolean
  canDelete: boolean
}

export type StructuralPanelAction =
  | 'insertAfter'
  | 'splitItem'
  | 'moveBefore'
  | 'moveAfter'
  | 'mergeWithNext'
  | 'moveIntoPreviousGroup'
  | 'moveIntoNextGroup'
  | 'moveToParentGroup'
  | 'deleteItem'

export function structuralPanelState(inputs: StructuralPanelInputs): StructuralPanelState {
  const maxSplitIndex = Math.max(0, inputs.draftContent.length - 1)
  const hasTargetRef = Boolean(inputs.targetRef)
  const saving = inputs.documentSaving

  return {
    maxSplitIndex,
    canInsertAfter: hasTargetRef && !saving && Boolean(inputs.insertAfterContent.trim()),
    canSplit: hasTargetRef && !saving && inputs.splitIndex > 0 && inputs.splitIndex <= maxSplitIndex,
    canMoveBefore: hasTargetRef && !saving && Boolean(inputs.previousSiblingTargetRef),
    canMoveAfter: hasTargetRef && !saving && Boolean(inputs.nextSiblingTargetRef),
    canMergeNext: hasTargetRef && !saving && Boolean(inputs.nextSiblingTargetRef),
    canMoveIntoPreviousGroup: hasTargetRef && !saving && Boolean(inputs.previousGroupTargetRef),
    canMoveIntoNextGroup: hasTargetRef && !saving && Boolean(inputs.nextGroupTargetRef),
    canMoveToParentGroup: hasTargetRef && !saving && Boolean(inputs.parentGroupTargetRef),
    canDelete: hasTargetRef && !saving,
  }
}

export function structuralPanelCommand(
  action: StructuralPanelAction,
  inputs: StructuralPanelInputs,
): DocumentEditCommandInput[] | null {
  const state = structuralPanelState(inputs)
  const targetRef = inputs.targetRef
  if (!targetRef) return null

  switch (action) {
    case 'insertAfter': {
      const content = inputs.insertAfterContent.trim()
      return state.canInsertAfter ? [buildInsertItemAfterCommand(targetRef, content)] : null
    }
    case 'splitItem':
      return state.canSplit ? [buildSplitItemCommand(targetRef, inputs.splitIndex)] : null
    case 'moveBefore':
      return state.canMoveBefore && inputs.previousSiblingTargetRef
        ? [buildMoveItemBeforeCommand(targetRef, inputs.previousSiblingTargetRef)]
        : null
    case 'moveAfter':
      return state.canMoveAfter && inputs.nextSiblingTargetRef
        ? [buildMoveItemAfterCommand(targetRef, inputs.nextSiblingTargetRef)]
        : null
    case 'mergeWithNext':
      return state.canMergeNext && inputs.nextSiblingTargetRef
        ? [buildMergeItemsCommand(targetRef, inputs.nextSiblingTargetRef)]
        : null
    case 'moveIntoPreviousGroup':
      return state.canMoveIntoPreviousGroup && inputs.previousGroupTargetRef
        ? [buildReparentItemCommand(targetRef, inputs.previousGroupTargetRef)]
        : null
    case 'moveIntoNextGroup':
      return state.canMoveIntoNextGroup && inputs.nextGroupTargetRef
        ? [buildReparentItemCommand(targetRef, inputs.nextGroupTargetRef)]
        : null
    case 'moveToParentGroup':
      return state.canMoveToParentGroup && inputs.parentGroupTargetRef
        ? [buildReparentItemCommand(targetRef, inputs.parentGroupTargetRef)]
        : null
    case 'deleteItem':
      return state.canDelete ? [buildDeleteItemCommand(targetRef)] : null
  }
}
