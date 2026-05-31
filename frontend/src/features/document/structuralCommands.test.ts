import { describe, expect, it } from 'vitest'
import {
  buildDeleteItemCommand,
  buildInsertItemAfterCommand,
  buildMergeItemsCommand,
  buildMoveItemAfterCommand,
  buildMoveItemBeforeCommand,
  buildSplitItemCommand,
} from './structuralCommands'

describe('structuralCommands', () => {
  it('builds a delete_item command', () => {
    expect(buildDeleteItemCommand('draft-1')).toEqual({
      action: 'delete_item',
      targetRef: 'draft-1',
      payload: {},
    })
  })

  it('builds an insert_item command', () => {
    expect(buildInsertItemAfterCommand('draft-1', 'Inserted')).toEqual({
      action: 'insert_item',
      targetRef: 'draft-1',
      payload: { content: 'Inserted' },
    })
  })

  it('builds a split_item command', () => {
    expect(buildSplitItemCommand('draft-1', 3)).toEqual({
      action: 'split_item',
      targetRef: 'draft-1',
      payload: { splitIndex: 3 },
    })
  })

  it('builds a move_item_before command', () => {
    expect(buildMoveItemBeforeCommand('draft-1', 'draft-2')).toEqual({
      action: 'move_item_before',
      targetRef: 'draft-1',
      payload: { beforeTargetRef: 'draft-2' },
    })
  })

  it('builds a move_item_after command', () => {
    expect(buildMoveItemAfterCommand('draft-1', 'draft-2')).toEqual({
      action: 'move_item_after',
      targetRef: 'draft-1',
      payload: { afterTargetRef: 'draft-2' },
    })
  })

  it('builds a merge_items command', () => {
    expect(buildMergeItemsCommand('draft-1', 'draft-2')).toEqual({
      action: 'merge_items',
      targetRef: 'draft-1',
      payload: { trailingTargetRef: 'draft-2', separator: ' ' },
    })
  })
})
