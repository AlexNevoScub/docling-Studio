import type { ElementType, PageElement } from '../../shared/types'

export interface PageElementDraft {
  content: string
  type: ElementType
  bbox: [number, number, number, number]
}

export interface PageElementPanelInputs {
  element: PageElement | null
  targetRef: string | null
  draftContent: string
  draftType: ElementType
  draftBbox: [number, number, number, number]
  documentSaving: boolean
}

export interface PageElementPanelState {
  hasChanges: boolean
  canSave: boolean
  payload: {
    content?: string
    bbox?: [number, number, number, number]
    type?: ElementType
  }
}

export function pageElementDraftFromElement(element: PageElement | null): PageElementDraft {
  return {
    content: element?.content ?? '',
    type: (element?.type as ElementType | undefined) ?? 'text',
    bbox: element?.bbox ? [...element.bbox] as [number, number, number, number] : [0, 0, 0, 0],
  }
}

export function pageElementPanelState(inputs: PageElementPanelInputs): PageElementPanelState {
  const payload = pageElementPayload(inputs)
  const hasChanges = Object.keys(payload).length > 0

  return {
    hasChanges,
    canSave: Boolean(inputs.targetRef) && !inputs.documentSaving && hasChanges,
    payload,
  }
}

function pageElementPayload(inputs: PageElementPanelInputs): PageElementPanelState['payload'] {
  const payload: PageElementPanelState['payload'] = {}
  if (!inputs.element) return payload

  if (inputs.draftContent !== inputs.element.content) payload.content = inputs.draftContent
  if (inputs.draftType !== inputs.element.type) payload.type = inputs.draftType
  if (inputs.draftBbox.some((value, index) => value !== inputs.element?.bbox[index])) {
    payload.bbox = [...inputs.draftBbox] as [number, number, number, number]
  }

  return payload
}
