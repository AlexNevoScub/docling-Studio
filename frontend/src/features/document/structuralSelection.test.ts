import { describe, expect, it } from 'vitest'
import type { DocTreeNode, DocumentEditCommandInput } from '../../shared/types'
import { postCommandSelectionRef } from './structuralSelection'

describe('structuralSelection', () => {
  it('selects the inserted sibling after insert_item', () => {
    const commands: DocumentEditCommandInput[] = [
      { action: 'insert_item', targetRef: 'draft-1', payload: { content: 'Inserted' } },
    ]
    const tree = [mkNode('#/texts/11', 'draft-1'), mkNode('#/texts/18', 'draft-new')]

    expect(postCommandSelectionRef(commands, tree)).toBe('draft-new')
  })

  it('selects the trailing split sibling after split_item', () => {
    const commands: DocumentEditCommandInput[] = [
      { action: 'split_item', targetRef: 'draft-1', payload: { splitIndex: 2 } },
    ]
    const tree = [mkNode('#/texts/11', 'draft-1'), mkNode('#/texts/18', 'draft-new')]

    expect(postCommandSelectionRef(commands, tree)).toBe('draft-new')
  })

  it('keeps selection on the surviving node after merge_items', () => {
    const commands: DocumentEditCommandInput[] = [
      { action: 'merge_items', targetRef: 'draft-1', payload: { trailingTargetRef: 'draft-2', separator: ' ' } },
    ]
    const tree = [mkNode('#/texts/11', 'draft-1')]

    expect(postCommandSelectionRef(commands, tree)).toBe('draft-1')
  })

  it('clears merge selection intent when the surviving target is missing', () => {
    const commands: DocumentEditCommandInput[] = [
      { action: 'merge_items', targetRef: 'draft-1', payload: { trailingTargetRef: 'draft-2', separator: ' ' } },
    ]

    expect(postCommandSelectionRef(commands, [])).toBeNull()
  })

  it('returns null for commands without selection intent', () => {
    const commands: DocumentEditCommandInput[] = [
      { action: 'move_item_after', targetRef: 'draft-1', payload: { afterTargetRef: 'draft-2' } },
    ]

    expect(postCommandSelectionRef(commands, [mkNode('#/texts/11', 'draft-1')])).toBeNull()
  })

  it('returns null for multi-command batches', () => {
    const commands: DocumentEditCommandInput[] = [
      { action: 'insert_item', targetRef: 'draft-1', payload: { content: 'Inserted' } },
      { action: 'split_item', targetRef: 'draft-2', payload: { splitIndex: 2 } },
    ]

    expect(postCommandSelectionRef(commands, [mkNode('#/texts/11', 'draft-1')])).toBeNull()
  })
})

function mkNode(ref: string, draftRef?: string, children: DocTreeNode[] = [], type = 'text'): DocTreeNode {
  return {
    ref,
    draftRef,
    type,
    label: ref,
    children,
  }
}
