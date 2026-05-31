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

export function adjacentGroupSiblingRefs(
  tree: readonly DocTreeNode[],
  selectedRef: string | null,
): { previousGroupRef: string | null; nextGroupRef: string | null } {
  if (!selectedRef) return { previousGroupRef: null, nextGroupRef: null }
  const siblings = findAdjacentSiblingNodes(tree, selectedRef)
  return {
    previousGroupRef: siblings?.previousSibling?.type === 'group' ? nodeTargetRef(siblings.previousSibling) : null,
    nextGroupRef: siblings?.nextSibling?.type === 'group' ? nodeTargetRef(siblings.nextSibling) : null,
  }
}

export function parentGroupTargetRef(
  tree: readonly DocTreeNode[],
  selectedRef: string | null,
): string | null {
  if (!selectedRef) return null
  return findParentGroupTargetRef(tree, selectedRef, [])
}

function findAdjacentSiblingRefs(
  nodes: readonly DocTreeNode[],
  selectedRef: string,
): { previousSiblingRef: string | null; nextSiblingRef: string | null } | null {
  const siblings = findAdjacentSiblingNodes(nodes, selectedRef)
  if (!siblings) return null
  return {
    previousSiblingRef: siblings.previousSibling ? nodeTargetRef(siblings.previousSibling) : null,
    nextSiblingRef: siblings.nextSibling ? nodeTargetRef(siblings.nextSibling) : null,
  }
}

function findAdjacentSiblingNodes(
  nodes: readonly DocTreeNode[],
  selectedRef: string,
): { previousSibling: DocTreeNode | null; nextSibling: DocTreeNode | null } | null {
  const index = nodes.findIndex((node) => nodeTargetRef(node) === selectedRef)
  if (index >= 0) {
    return {
      previousSibling: index > 0 ? nodes[index - 1] : null,
      nextSibling: index < nodes.length - 1 ? nodes[index + 1] : null,
    }
  }

  for (const node of nodes) {
    const nested = findAdjacentSiblingNodes(node.children, selectedRef)
    if (nested) return nested
  }

  return null
}

function findParentGroupTargetRef(
  nodes: readonly DocTreeNode[],
  selectedRef: string,
  groupAncestors: readonly DocTreeNode[],
): string | null {
  for (const node of nodes) {
    const nextAncestors = node.type === 'group' ? [...groupAncestors, node] : groupAncestors
    if (nodeTargetRef(node) === selectedRef) {
      return nextAncestors.length >= 2 ? nodeTargetRef(nextAncestors[nextAncestors.length - 2]) : null
    }
    const nested = findParentGroupTargetRef(node.children, selectedRef, nextAncestors)
    if (nested) return nested
  }

  return null
}

function nodeTargetRef(node: Pick<DocTreeNode, 'draftRef' | 'ref'>): string {
  return node.draftRef ?? node.ref
}
