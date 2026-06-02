import type { DocTreeNode, ElementType, Page, PageElement } from '../../shared/types'

export interface PageElementPreview {
  targetRef: string
  payload: { content?: string; bbox?: [number, number, number, number]; type?: ElementType }
}

export function elementTargetRef(element: Pick<PageElement, 'draftRef' | 'self_ref'>): string | null {
  return element.draftRef ?? element.self_ref ?? null
}

export function countTreeNodes(nodes: readonly DocTreeNode[]): number {
  let count = 0
  for (const node of nodes) {
    count += 1 + countTreeNodes(node.children)
  }
  return count
}

export function filterTreeNodes(nodes: readonly DocTreeNode[], needle: string): DocTreeNode[] {
  const filtered: DocTreeNode[] = []
  for (const node of nodes) {
    const childMatches = filterTreeNodes(node.children, needle)
    const selfMatches =
      node.label.toLowerCase().includes(needle) || node.type.toLowerCase().includes(needle)
    if (selfMatches || childMatches.length > 0) {
      filtered.push({ ...node, children: childMatches })
    }
  }
  return filtered
}

export function applyPageElementPreview(
  pages: readonly Page[],
  preview: PageElementPreview | null,
): Page[] {
  if (!preview) return [...pages]

  return pages.map((page) => ({
    ...page,
    elements: page.elements.map((element) =>
      elementTargetRef(element) === preview.targetRef
        ? {
            ...element,
            content: preview.payload.content ?? element.content,
            bbox: preview.payload.bbox ?? element.bbox,
            type: preview.payload.type ?? element.type,
          }
        : element,
    ),
  }))
}

export function findPageNumberForRef(
  pages: readonly Pick<Page, 'page_number' | 'elements'>[],
  ref: string,
): number | null {
  for (const page of pages) {
    if (page.elements.some((element) => elementTargetRef(element) === ref)) return page.page_number
  }
  return null
}

export function findElementByRef(
  pages: readonly Pick<Page, 'elements'>[],
  ref: string | null,
): PageElement | null {
  if (!ref) return null
  for (const page of pages) {
    const element = page.elements.find((entry) => elementTargetRef(entry) === ref)
    if (element) return element
  }
  return null
}
