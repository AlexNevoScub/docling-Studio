import { describe, expect, it } from 'vitest'
import type { DocChunk } from '../../shared/types'
import { chunkDraftFromChunk, chunkPanelState } from './chunkPanel'

describe('chunkPanel', () => {
  it('builds the initial draft text from the linked chunk', () => {
    expect(chunkDraftFromChunk(mkChunk())).toBe('Original chunk')
  })

  it('returns an empty draft when no chunk is linked', () => {
    expect(chunkDraftFromChunk(null)).toBe('')
  })

  it('treats unchanged text as unsaveable', () => {
    expect(chunkPanelState(mkChunk(), 'Original chunk', false)).toEqual({
      hasChanges: false,
      canSave: false,
      shouldCloseAfterSave: true,
    })
  })

  it('allows save when the draft text changed', () => {
    expect(chunkPanelState(mkChunk(), 'Updated chunk', false)).toEqual({
      hasChanges: true,
      canSave: true,
      shouldCloseAfterSave: false,
    })
  })

  it('disables save while a chunk save is in progress', () => {
    expect(chunkPanelState(mkChunk(), 'Updated chunk', true)).toEqual({
      hasChanges: true,
      canSave: false,
      shouldCloseAfterSave: false,
    })
  })

  it('stays closed and unsaveable without a linked chunk', () => {
    expect(chunkPanelState(null, 'Draft', false)).toEqual({
      hasChanges: false,
      canSave: false,
      shouldCloseAfterSave: false,
    })
  })
})

function mkChunk(): DocChunk {
  return {
    id: 'c1',
    docId: 'd1',
    sequence: 1,
    text: 'Original chunk',
    headings: [],
    sourcePage: 1,
    tokenCount: 12,
    bboxes: [],
    docItems: [],
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  }
}
