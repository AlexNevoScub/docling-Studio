import type { DocTreeNode, DocumentEditCommandInput } from '../../shared/types'
import { adjacentSiblingRefs } from './siblingTargets'

export function postCommandSelectionRef(
  commands: readonly DocumentEditCommandInput[],
  previousTree: readonly DocTreeNode[],
  nextTree: readonly DocTreeNode[],
): string | null {
  if (commands.length !== 1) return null

  const command = commands[0]
  if (command.action === 'merge_items') {
    return hasTargetRef(nextTree, command.targetRef) ? command.targetRef : null
  }

  if (command.action === 'delete_item') {
    const siblings = adjacentSiblingRefs(previousTree, command.targetRef)
    if (siblings.previousSiblingRef && hasTargetRef(nextTree, siblings.previousSiblingRef)) {
      return siblings.previousSiblingRef
    }
    if (siblings.nextSiblingRef && hasTargetRef(nextTree, siblings.nextSiblingRef)) {
      return siblings.nextSiblingRef
    }
    return null
  }

  if (command.action !== 'insert_item' && command.action !== 'split_item') return null

  return adjacentSiblingRefs(nextTree, command.targetRef).nextSiblingRef
}

function hasTargetRef(tree: readonly DocTreeNode[], targetRef: string): boolean {
  for (const node of tree) {
    const nodeRef = node.draftRef ?? node.ref
    if (nodeRef === targetRef) return true
    if (hasTargetRef(node.children, targetRef)) return true
  }
  return false
}
