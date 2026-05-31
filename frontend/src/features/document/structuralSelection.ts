import type { DocTreeNode, DocumentEditCommandInput } from '../../shared/types'
import { adjacentSiblingRefs } from './siblingTargets'

export function postCommandSelectionRef(
  commands: readonly DocumentEditCommandInput[],
  tree: readonly DocTreeNode[],
): string | null {
  if (commands.length !== 1) return null

  const command = commands[0]
  if (command.action === 'merge_items') {
    return hasTargetRef(tree, command.targetRef) ? command.targetRef : null
  }

  if (command.action !== 'insert_item' && command.action !== 'split_item') return null

  return adjacentSiblingRefs(tree, command.targetRef).nextSiblingRef
}

function hasTargetRef(tree: readonly DocTreeNode[], targetRef: string): boolean {
  for (const node of tree) {
    const nodeRef = node.draftRef ?? node.ref
    if (nodeRef === targetRef) return true
    if (hasTargetRef(node.children, targetRef)) return true
  }
  return false
}
