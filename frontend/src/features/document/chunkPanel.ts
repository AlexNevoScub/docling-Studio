import type { DocChunk } from '../../shared/types'

export interface ChunkPanelState {
  hasChanges: boolean
  canSave: boolean
  shouldCloseAfterSave: boolean
}

export function chunkDraftFromChunk(chunk: DocChunk | null): string {
  return chunk?.text ?? ''
}

export function chunkPanelState(
  chunk: DocChunk | null,
  draftText: string,
  saving: boolean,
): ChunkPanelState {
  const chunkText = chunk?.text ?? null
  const hasChanges = chunkText !== null && draftText !== chunkText

  return {
    hasChanges,
    canSave: chunkText !== null && !saving && hasChanges,
    shouldCloseAfterSave: chunkText !== null && !saving && chunkText === draftText,
  }
}
