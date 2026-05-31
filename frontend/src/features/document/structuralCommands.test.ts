import { describe, expect, it } from 'vitest'
import {
  buildDeleteItemCommand,
  buildInsertItemAfterCommand,
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
})
