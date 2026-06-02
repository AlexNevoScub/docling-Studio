import type { DocChunk, ElementType, PageElement } from '../../shared/types'
import type { ChunkPanelState } from './chunkPanel'
import { chunkDraftFromChunk } from './chunkPanel'
import type { PageElementDraft, PageElementPanelState } from './pageElementPanel'
import { pageElementDraftFromElement } from './pageElementPanel'

export interface ElementPropertiesDraftState {
  pageElementDraft: PageElementDraft
  insertAfterContent: string
  splitIndex: number
}

export type PageElementPreviewOutcome =
  | { kind: 'clear' }
  | {
      kind: 'preview'
      targetRef: string
      payload: {
        content?: string
        bbox?: [number, number, number, number]
        type?: ElementType
      }
    }

export type PageElementSaveOutcome =
  | { kind: 'noop' }
  | {
      kind: 'save'
      targetRef: string
      payload: {
        content?: string
        bbox?: [number, number, number, number]
        type?: ElementType
      }
    }

export type ChunkSaveOutcome =
  | { kind: 'noop' }
  | { kind: 'close' }
  | { kind: 'save'; chunkId: string; text: string }

export function elementPropertiesDraftStateFromElement(
  element: PageElement | null,
): ElementPropertiesDraftState {
  return {
    pageElementDraft: pageElementDraftFromElement(element),
    insertAfterContent: '',
    splitIndex: 1,
  }
}

export function chunkDraftTextFromChunk(chunk: DocChunk | null): string {
  return chunkDraftFromChunk(chunk)
}

export function pageElementPreviewOutcome(
  targetRef: string | null,
  state: PageElementPanelState,
): PageElementPreviewOutcome {
  if (!targetRef || !state.hasChanges) return { kind: 'clear' }
  return {
    kind: 'preview',
    targetRef,
    payload: state.payload,
  }
}

export function pageElementSaveOutcome(
  targetRef: string | null,
  state: PageElementPanelState,
): PageElementSaveOutcome {
  if (!targetRef || !state.hasChanges) return { kind: 'noop' }
  return {
    kind: 'save',
    targetRef,
    payload: state.payload,
  }
}

export function chunkSaveOutcome(
  chunk: DocChunk | null,
  draftText: string,
  state: ChunkPanelState,
): ChunkSaveOutcome {
  if (!chunk) return { kind: 'noop' }
  if (!state.hasChanges) return { kind: 'close' }
  return {
    kind: 'save',
    chunkId: chunk.id,
    text: draftText,
  }
}
