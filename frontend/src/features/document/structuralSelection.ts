import type { DocTreeNode, DocumentEditCommandInput } from '../../shared/types'
import { adjacentSiblingRefs } from './siblingTargets'

export function postCommandSelectionRef(
  commands: readonly DocumentEditCommandInput[],
  tree: readonly DocTreeNode[],
): string | null {
  if (commands.length !== 1) return null

  const command = commands[0]
  if (command.action !== 'insert_item' && command.action !== 'split_item') {
    return null
  }

  return adjacentSiblingRefs(tree, command.targetRef).nextSiblingRef
}
