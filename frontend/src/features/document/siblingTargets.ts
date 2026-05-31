import type { DocTreeNode } from '../../shared/types'

export function adjacentSiblingRefs(
  tree: readonly DocTreeNode[],
  selectedRef: string | null,
): { previousSiblingRef: string | null; nextSiblingRef: string | null } {
  if (!selectedRef) return { previousSiblingRef: null, nextSiblingRef: null }
  return findAdjacentSiblingRefs(tree, selectedRef) ?? {
    previousSiblingRef: null,
    nextSiblingRef: null,
  }
}

function findAdjacentSiblingRefs(
  nodes: readonly DocTreeNode[],
  selectedRef: string,
): { previousSiblingRef: string | null; nextSiblingRef: string | null } | null {
  const index = nodes.findIndex((node) => nodeTargetRef(node) === selectedRef)
  if (index >= 0) {
    return {
      previousSiblingRef: index > 0 ? nodeTargetRef(nodes[index - 1]) : null,
      nextSiblingRef: index < nodes.length - 1 ? nodeTargetRef(nodes[index + 1]) : null,
    }
  }

  for (const node of nodes) {
    const nested = findAdjacentSiblingRefs(node.children, selectedRef)
    if (nested) return nested
  }

  return null
}

function nodeTargetRef(node: Pick<DocTreeNode, 'draftRef' | 'ref'>): string {
  return node.draftRef ?? node.ref
}
