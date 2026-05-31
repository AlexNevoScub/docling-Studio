import type { DocumentEditCommandInput } from '../../shared/types'

export function buildDeleteItemCommand(targetRef: string): DocumentEditCommandInput {
  return {
    action: 'delete_item',
    targetRef,
    payload: {},
  }
}

export function buildInsertItemAfterCommand(
  targetRef: string,
  content: string,
): DocumentEditCommandInput {
  return {
    action: 'insert_item',
    targetRef,
    payload: { content },
  }
}

export function buildSplitItemCommand(
  targetRef: string,
  splitIndex: number,
): DocumentEditCommandInput {
  return {
    action: 'split_item',
    targetRef,
    payload: { splitIndex },
  }
}

export function buildMoveItemBeforeCommand(
  targetRef: string,
  beforeTargetRef: string,
): DocumentEditCommandInput {
  return {
    action: 'move_item_before',
    targetRef,
    payload: { beforeTargetRef },
  }
}

export function buildMoveItemAfterCommand(
  targetRef: string,
  afterTargetRef: string,
): DocumentEditCommandInput {
  return {
    action: 'move_item_after',
    targetRef,
    payload: { afterTargetRef },
  }
}

export function buildMergeItemsCommand(
  targetRef: string,
  trailingTargetRef: string,
): DocumentEditCommandInput {
  return {
    action: 'merge_items',
    targetRef,
    payload: { trailingTargetRef, separator: ' ' },
  }
}
