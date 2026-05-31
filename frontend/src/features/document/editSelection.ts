import type { DocTreeNode, DocumentRefRemap, Page, PageElement } from '../../shared/types'

export function reconcileSelectedDraftRef(
  selectedDraftRef: string | null,
  selectedSelfRef: string | null,
  tree: readonly DocTreeNode[],
  pages: readonly Page[],
  refRemaps: readonly DocumentRefRemap[],
): string | null {
  if (!selectedDraftRef) return null
  if (hasDraftOrRawRef(tree, pages, selectedDraftRef)) return selectedDraftRef

  if (selectedSelfRef) {
    const remap = refRemaps.find((entry) => entry.selfRef === selectedSelfRef)
    if (remap?.draftRef) return remap.draftRef
    if (hasDraftOrRawRef(tree, pages, selectedSelfRef)) return selectedSelfRef
  }

  return null
}

export function resolveSelectedSelfRef(
  selectedDraftRef: string | null,
  tree: readonly DocTreeNode[],
  pages: readonly Page[],
): string | null {
  if (!selectedDraftRef) return null

  const treeRef = treeSelfRefBySelectedRef(tree, selectedDraftRef)
  if (treeRef) return treeRef

  for (const page of pages) {
    const element = page.elements.find((entry) => elementTargetRef(entry) === selectedDraftRef)
    if (element) return element.self_ref ?? null
  }

  return null
}

function hasDraftOrRawRef(
  tree: readonly DocTreeNode[],
  pages: readonly Page[],
  targetRef: string,
): boolean {
  return Boolean(resolveSelectedSelfRef(targetRef, tree, pages))
}

function treeSelfRefBySelectedRef(
  nodes: readonly DocTreeNode[],
  selectedRef: string,
): string | null {
  for (const node of nodes) {
    const nodeRef = node.draftRef ?? node.ref
    if (nodeRef === selectedRef) return node.ref
    const childRef = treeSelfRefBySelectedRef(node.children, selectedRef)
    if (childRef) return childRef
  }
  return null
}

function elementTargetRef(element: Pick<PageElement, 'draftRef' | 'self_ref'>): string | null {
  return element.draftRef ?? element.self_ref ?? null
}
