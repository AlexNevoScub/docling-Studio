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
