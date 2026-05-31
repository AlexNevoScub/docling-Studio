import { describe, expect, it } from 'vitest'
import { structuralPanelCommand, structuralPanelState } from './structuralPanel'

describe('structuralPanel', () => {
  it('enables and trims insert-after commands', () => {
    const inputs = mkInputs({ insertAfterContent: '  New sibling  ' })

    expect(structuralPanelState(inputs).canInsertAfter).toBe(true)
    expect(structuralPanelCommand('insertAfter', inputs)).toEqual([
      { action: 'insert_item', targetRef: 'draft-1', payload: { content: 'New sibling' } },
    ])
  })

  it('disables split when the index exceeds the content length', () => {
    const inputs = mkInputs({ draftContent: 'abc', splitIndex: 3 })

    expect(structuralPanelState(inputs).maxSplitIndex).toBe(2)
    expect(structuralPanelState(inputs).canSplit).toBe(false)
    expect(structuralPanelCommand('splitItem', inputs)).toBeNull()
  })

  it('enables sibling and group actions only when their target refs exist', () => {
    const inputs = mkInputs({
      previousSiblingTargetRef: 'draft-prev',
      nextSiblingTargetRef: 'draft-next',
      previousGroupTargetRef: 'draft-group-prev',
      nextGroupTargetRef: 'draft-group-next',
      parentGroupTargetRef: 'draft-group-parent',
    })
    const state = structuralPanelState(inputs)

    expect(state.canMoveBefore).toBe(true)
    expect(state.canMoveAfter).toBe(true)
    expect(state.canMergeNext).toBe(true)
    expect(state.canMoveIntoPreviousGroup).toBe(true)
    expect(state.canMoveIntoNextGroup).toBe(true)
    expect(state.canMoveToParentGroup).toBe(true)
    expect(structuralPanelCommand('moveToParentGroup', inputs)).toEqual([
      { action: 'reparent_item', targetRef: 'draft-1', payload: { parentTargetRef: 'draft-group-parent' } },
    ])
  })

  it('disables every structural action while saving', () => {
    const inputs = mkInputs({
      documentSaving: true,
      insertAfterContent: 'Inserted',
      previousSiblingTargetRef: 'draft-prev',
      nextSiblingTargetRef: 'draft-next',
      previousGroupTargetRef: 'draft-group-prev',
      nextGroupTargetRef: 'draft-group-next',
      parentGroupTargetRef: 'draft-group-parent',
    })
    const state = structuralPanelState(inputs)

    expect(state.canInsertAfter).toBe(false)
    expect(state.canSplit).toBe(false)
    expect(state.canMoveBefore).toBe(false)
    expect(state.canMoveAfter).toBe(false)
    expect(state.canMergeNext).toBe(false)
    expect(state.canMoveIntoPreviousGroup).toBe(false)
    expect(state.canMoveIntoNextGroup).toBe(false)
    expect(state.canMoveToParentGroup).toBe(false)
    expect(state.canDelete).toBe(false)
  })
})

function mkInputs(overrides: Partial<Parameters<typeof structuralPanelState>[0]> = {}) {
  return {
    targetRef: 'draft-1',
    draftContent: 'hello',
    insertAfterContent: '',
    splitIndex: 1,
    documentSaving: false,
    previousSiblingTargetRef: null,
    nextSiblingTargetRef: null,
    previousGroupTargetRef: null,
    nextGroupTargetRef: null,
    parentGroupTargetRef: null,
    ...overrides,
  }
}
