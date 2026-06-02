<template>
  <aside class="element-properties" data-e2e="element-properties">
    <header class="element-properties-header">
      <h2 class="element-properties-title">{{ t('properties.title') }}</h2>
      <span v-if="element" class="element-properties-type" :style="typeStyle">
        {{ element.type }}
      </span>
    </header>

    <div v-if="!element" class="element-properties-empty" data-e2e="element-properties-empty">
      {{ t('properties.empty') }}
    </div>

    <div v-else class="element-properties-body">
      <!-- Identity -->
      <section class="props-section">
        <h3 class="props-section-title">{{ t('properties.identity') }}</h3>
        <dl class="props-list">
          <dt>{{ t('properties.id') }}</dt>
          <dd class="mono">{{ element.draftRef || element.self_ref || '—' }}</dd>
          <dt>{{ t('properties.type') }}</dt>
          <dd>{{ element.type }}</dd>
          <dt>{{ t('properties.level') }}</dt>
          <dd>{{ element.level }}</dd>
          <dt>{{ t('properties.page') }}</dt>
          <dd>{{ pageNumber }}</dd>
        </dl>
      </section>

      <section class="props-section">
        <h3 class="props-section-title">{{ t('properties.pageElementEdit') }}</h3>
        <div class="props-edit" data-e2e="properties-page-element-edit">
          <label class="props-field">
            <span class="props-field-label">{{ t('properties.type') }}</span>
            <select v-model="draftType" class="props-input" :disabled="documentSaving">
              <option v-for="option in typeOptions" :key="option" :value="option">{{ option }}</option>
            </select>
          </label>

          <label class="props-field">
            <span class="props-field-label">{{ t('properties.extractedText') }}</span>
            <textarea
              v-model="draftContent"
              class="props-edit-textarea"
              rows="6"
              :disabled="documentSaving"
            />
          </label>

          <div class="props-bbox-grid">
            <label class="props-field">
              <span class="props-field-label">x</span>
              <input v-model.number="draftBbox[0]" class="props-input mono" type="number" step="0.1" :disabled="documentSaving" />
            </label>
            <label class="props-field">
              <span class="props-field-label">y</span>
              <input v-model.number="draftBbox[1]" class="props-input mono" type="number" step="0.1" :disabled="documentSaving" />
            </label>
            <label class="props-field">
              <span class="props-field-label">r</span>
              <input v-model.number="draftBbox[2]" class="props-input mono" type="number" step="0.1" :disabled="documentSaving" />
            </label>
            <label class="props-field">
              <span class="props-field-label">b</span>
              <input v-model.number="draftBbox[3]" class="props-input mono" type="number" step="0.1" :disabled="documentSaving" />
            </label>
          </div>

          <dl class="props-list">
            <dt>x</dt>
            <dd class="mono">{{ bboxPct.x }}%</dd>
            <dt>y</dt>
            <dd class="mono">{{ bboxPct.y }}%</dd>
            <dt>{{ t('properties.width') }}</dt>
            <dd class="mono">{{ bboxPct.w }}%</dd>
            <dt>{{ t('properties.height') }}</dt>
            <dd class="mono">{{ bboxPct.h }}%</dd>
          </dl>

          <div class="props-edit-actions">
            <button class="props-btn props-btn--cancel" :disabled="documentSaving" @click="resetPageElementDraft">
              {{ t('properties.reset') }}
            </button>
            <button
              class="props-btn props-btn--primary"
              :disabled="!pageElementState.canSave"
              data-e2e="properties-save-page-element-btn"
              @click="savePageElement"
            >
              {{ documentSaving ? t('properties.saving') : t('properties.save') }}
            </button>
          </div>
        </div>
      </section>

      <section v-if="pageElementTargetRef" class="props-section">
        <h3 class="props-section-title">{{ t('properties.structureEdits') }}</h3>
        <div class="props-edit" data-e2e="properties-structure-edit">
          <label class="props-field">
            <span class="props-field-label">{{ t('properties.insertAfter') }}</span>
            <textarea
              v-model="insertAfterContent"
              class="props-edit-textarea"
              rows="3"
              :disabled="documentSaving"
            />
          </label>
          <div class="props-edit-actions">
            <button
              class="props-btn props-btn--primary"
              :disabled="!structuralState.canInsertAfter"
              data-e2e="properties-insert-after-btn"
              @click="insertAfter"
            >
              {{ documentSaving ? t('properties.saving') : t('properties.insertAfterAction') }}
            </button>
          </div>

          <label class="props-field">
            <span class="props-field-label">{{ t('properties.splitAt') }}</span>
            <input
              v-model.number="splitIndex"
              class="props-input mono"
              type="number"
              min="1"
              step="1"
              :max="maxSplitIndex"
              :disabled="documentSaving || maxSplitIndex < 1"
            />
          </label>
          <div class="props-edit-actions">
            <button
              class="props-btn props-btn--primary"
              :disabled="!structuralState.canSplit"
              data-e2e="properties-split-item-btn"
              @click="splitItem"
            >
              {{ documentSaving ? t('properties.saving') : t('properties.splitItem') }}
            </button>
            <button
              class="props-btn"
              :disabled="!structuralState.canMoveBefore"
              data-e2e="properties-move-before-btn"
              @click="moveBefore"
            >
              {{ t('properties.moveBefore') }}
            </button>
            <button
              class="props-btn"
              :disabled="!structuralState.canMoveAfter"
              data-e2e="properties-move-after-btn"
              @click="moveAfter"
            >
              {{ t('properties.moveAfter') }}
            </button>
            <button
              class="props-btn"
              :disabled="!structuralState.canMergeNext"
              data-e2e="properties-merge-next-btn"
              @click="mergeWithNext"
            >
              {{ t('properties.mergeNext') }}
            </button>
            <button
              class="props-btn"
              :disabled="!structuralState.canMoveIntoPreviousGroup"
              data-e2e="properties-move-into-previous-group-btn"
              @click="moveIntoPreviousGroup"
            >
              {{ t('properties.moveIntoPreviousGroup') }}
            </button>
            <button
              class="props-btn"
              :disabled="!structuralState.canMoveIntoNextGroup"
              data-e2e="properties-move-into-next-group-btn"
              @click="moveIntoNextGroup"
            >
              {{ t('properties.moveIntoNextGroup') }}
            </button>
            <button
              class="props-btn"
              :disabled="!structuralState.canMoveToParentGroup"
              data-e2e="properties-move-to-parent-group-btn"
              @click="moveToParentGroup"
            >
              {{ t('properties.moveToParentGroup') }}
            </button>
            <button
              class="props-btn props-btn--danger"
              :disabled="!structuralState.canDelete"
              data-e2e="properties-delete-item-btn"
              @click="deleteItem"
            >
              {{ documentSaving ? t('properties.saving') : t('properties.deleteItem') }}
            </button>
          </div>
        </div>
      </section>

      <section v-if="hasPendingDocumentEdits" class="props-section">
        <h3 class="props-section-title">{{ t('properties.pendingDocumentEdits') }}</h3>
        <div class="props-edit-actions">
          <button
            class="props-btn props-btn--cancel"
            :disabled="documentCommitting"
            data-e2e="properties-discard-document-edits-btn"
            @click="emit('discardDocumentEdits')"
          >
            {{ t('properties.discardDocumentEdits') }}
          </button>
          <button
            class="props-btn props-btn--primary"
            :disabled="documentCommitting"
            data-e2e="properties-commit-document-edits-btn"
            @click="emit('commitDocumentEdits')"
          >
            {{ documentCommitting ? t('properties.committingDocumentEdits') : t('properties.commitDocumentEdits') }}
          </button>
        </div>
      </section>

      <!-- Linked chunk -->
      <section v-if="linkedChunk" class="props-section">
        <h3 class="props-section-title">{{ t('properties.linkedChunk') }}</h3>
        <p class="props-linked-chunk" data-e2e="properties-linked-chunk">
          <span class="mono">#c{{ linkedChunk.sequence }}</span>
          <span v-if="linkedChunk.tokenCount" class="props-linked-tokens"
            >{{ linkedChunk.tokenCount }}t</span
          >
        </p>

        <!-- Edit mode -->
        <div v-if="editing" class="props-edit" data-e2e="properties-edit">
          <textarea
            ref="textareaRef"
            v-model="draftText"
            class="props-edit-textarea"
            rows="6"
            :disabled="saving"
            @keydown.escape.prevent="cancel"
          />
          <div class="props-edit-actions">
            <button class="props-btn props-btn--cancel" :disabled="saving" @click="cancel">
              {{ t('properties.cancel') }}
            </button>
            <button
              class="props-btn props-btn--primary"
              :disabled="!chunkState.canSave"
              data-e2e="properties-save-btn"
              @click="save"
            >
              {{ saving ? t('properties.saving') : t('properties.save') }}
            </button>
          </div>
        </div>
        <button
          v-else
          type="button"
          class="props-edit-btn"
          data-e2e="properties-edit-btn"
          @click="startEdit"
        >
          ✎ {{ t('properties.editChunk') }}
        </button>
      </section>
    </div>
  </aside>
</template>

<script setup lang="ts">
/**
 * Right-side Properties panel of the Parse view (#265).
 *
 * Driven by the currently selected element on the canvas / tree. When
 * the element has a linked chunk (computed by the parent via
 * `chunkForElement`), an inline-edit affordance is shown — pressing it
 * swaps the chunk metadata block for a textarea bound to the chunk's
 * text. Save calls back through `@save-chunk` so the parent owns the
 * actual `chunksStore.updateText` invocation.
 *
 * OCR confidence / lang / model are intentionally omitted in this first
 * cut: the domain `PageElement` does not carry them today. A follow-up
 * issue can extend the domain + DTO when the data becomes available.
 */
import { computed, nextTick, ref, watch } from 'vue'
import type { DocChunk, DocumentEditCommandInput, ElementType, PageElement } from '../../../shared/types'
import { useI18n } from '../../../shared/i18n'
import { bboxToPercent } from '../bboxPercent'
import { chunkPanelState } from '../chunkPanel'
import {
  chunkDraftTextFromChunk,
  chunkSaveOutcome,
  elementPropertiesDraftStateFromElement,
  pageElementPreviewOutcome,
  pageElementSaveOutcome,
} from '../elementPropertiesLogic'
import { colorFor } from '../elementColors'
import { pageElementPanelState } from '../pageElementPanel'
import { structuralPanelCommand, structuralPanelState } from '../structuralPanel'

const props = defineProps<{
  element: PageElement | null
  pageWidth: number
  pageHeight: number
  pageNumber: number
  linkedChunk: DocChunk | null
  saving?: boolean
  documentSaving?: boolean
  documentCommitting?: boolean
  hasPendingDocumentEdits?: boolean
  previousSiblingTargetRef?: string | null
  nextSiblingTargetRef?: string | null
  previousGroupTargetRef?: string | null
  nextGroupTargetRef?: string | null
  parentGroupTargetRef?: string | null
}>()

const emit = defineEmits<{
  saveChunk: [chunkId: string, text: string]
  previewPageElement: [
    targetRef: string,
    payload: { content?: string; bbox?: [number, number, number, number]; type?: ElementType },
  ]
  clearPageElementPreview: []
  savePageElement: [
    targetRef: string,
    payload: { content?: string; bbox?: [number, number, number, number]; type?: ElementType },
  ]
  applyDocumentEditCommands: [commands: DocumentEditCommandInput[]]
  commitDocumentEdits: []
  discardDocumentEdits: []
}>()

const { t } = useI18n()

const editing = ref(false)
const draftText = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const draftContent = ref('')
const draftType = ref<ElementType>('text')
const draftBbox = ref<[number, number, number, number]>([0, 0, 0, 0])
const insertAfterContent = ref('')
const splitIndex = ref(1)

const chunkState = computed(() => chunkPanelState(props.linkedChunk, draftText.value, Boolean(props.saving)))
const pageElementTargetRef = computed(() => props.element?.draftRef ?? props.element?.self_ref ?? null)
const pageElementState = computed(() =>
  pageElementPanelState({
    element: props.element,
    targetRef: pageElementTargetRef.value,
    draftContent: draftContent.value,
    draftType: draftType.value,
    draftBbox: draftBbox.value,
    documentSaving: Boolean(props.documentSaving),
  }),
)
const structuralState = computed(() =>
  structuralPanelState({
    targetRef: pageElementTargetRef.value,
    draftContent: draftContent.value,
    insertAfterContent: insertAfterContent.value,
    splitIndex: splitIndex.value,
    documentSaving: Boolean(props.documentSaving),
    previousSiblingTargetRef: props.previousSiblingTargetRef,
    nextSiblingTargetRef: props.nextSiblingTargetRef,
    previousGroupTargetRef: props.previousGroupTargetRef,
    nextGroupTargetRef: props.nextGroupTargetRef,
    parentGroupTargetRef: props.parentGroupTargetRef,
  }),
)
const maxSplitIndex = computed(() => structuralState.value.maxSplitIndex)

const typeOptions: ElementType[] = [
  'text',
  'title',
  'section_header',
  'list',
  'code',
  'formula',
  'caption',
  'picture',
  'table',
  'floating',
]

const typeStyle = computed(() => {
  if (!props.element) return {}
  const c = colorFor(props.element.type)
  return { background: c + '22', color: c }
})

const bboxPct = computed(() => {
  if (!props.element) return { x: '0.0', y: '0.0', w: '0.0', h: '0.0' }
  return bboxToPercent(props.element.bbox, props.pageWidth, props.pageHeight)
})

function startEdit(): void {
  if (!props.linkedChunk) return
  draftText.value = chunkDraftTextFromChunk(props.linkedChunk)
  editing.value = true
  nextTick(() => textareaRef.value?.focus())
}

function cancel(): void {
  editing.value = false
  draftText.value = ''
}

function resetPageElementDraft(): void {
  const nextDraftState = elementPropertiesDraftStateFromElement(props.element)
  draftContent.value = nextDraftState.pageElementDraft.content
  draftType.value = nextDraftState.pageElementDraft.type
  draftBbox.value = [...nextDraftState.pageElementDraft.bbox]
  insertAfterContent.value = nextDraftState.insertAfterContent
  splitIndex.value = nextDraftState.splitIndex
}

function save(): void {
  const outcome = chunkSaveOutcome(props.linkedChunk, draftText.value, chunkState.value)
  if (outcome.kind === 'close') {
    cancel()
    return
  }
  if (outcome.kind !== 'save') return
  emit('saveChunk', outcome.chunkId, outcome.text)
}

function savePageElement(): void {
  const outcome = pageElementSaveOutcome(pageElementTargetRef.value, pageElementState.value)
  if (outcome.kind !== 'save') return
  emit('savePageElement', outcome.targetRef, outcome.payload)
}

function insertAfter(): void {
  const commands = structuralPanelCommand('insertAfter', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
  insertAfterContent.value = ''
}

function splitItem(): void {
  const commands = structuralPanelCommand('splitItem', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
}

function moveBefore(): void {
  const commands = structuralPanelCommand('moveBefore', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
}

function moveAfter(): void {
  const commands = structuralPanelCommand('moveAfter', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
}

function mergeWithNext(): void {
  const commands = structuralPanelCommand('mergeWithNext', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
}

function moveIntoPreviousGroup(): void {
  const commands = structuralPanelCommand('moveIntoPreviousGroup', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
}

function moveIntoNextGroup(): void {
  const commands = structuralPanelCommand('moveIntoNextGroup', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
}

function moveToParentGroup(): void {
  const commands = structuralPanelCommand('moveToParentGroup', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
}

function deleteItem(): void {
  const commands = structuralPanelCommand('deleteItem', structuralPanelInputs())
  if (!commands) return
  emit('applyDocumentEditCommands', commands)
}

function structuralPanelInputs() {
  return {
    targetRef: pageElementTargetRef.value,
    draftContent: draftContent.value,
    insertAfterContent: insertAfterContent.value,
    splitIndex: splitIndex.value,
    documentSaving: Boolean(props.documentSaving),
    previousSiblingTargetRef: props.previousSiblingTargetRef,
    nextSiblingTargetRef: props.nextSiblingTargetRef,
    previousGroupTargetRef: props.previousGroupTargetRef,
    nextGroupTargetRef: props.nextGroupTargetRef,
    parentGroupTargetRef: props.parentGroupTargetRef,
  }
}

// Exit edit mode when the parent reports the save is done (saving goes
// back to false after being true) and the chunk text matches the draft.
watch(
  () => props.saving,
  (now, prev) => {
    if (prev && !now && props.linkedChunk?.text === draftText.value) {
      editing.value = false
    }
  },
)

// Switching to a different element discards the in-progress edit. The
// design call (#265 acceptance §11): drop the draft silently to keep
// the interaction snappy; users can re-open Edit chunk if needed.
watch(
  () => pageElementTargetRef.value,
  () => {
    if (editing.value) cancel()
    resetPageElementDraft()
  },
  { immediate: true },
)

watch(
  [draftContent, draftType, draftBbox],
  () => {
    const outcome = pageElementPreviewOutcome(pageElementTargetRef.value, pageElementState.value)
    if (outcome.kind !== 'preview') {
      emit('clearPageElementPreview')
      return
    }
    emit('previewPageElement', outcome.targetRef, outcome.payload)
  },
  { deep: true },
)
</script>

<style scoped>
.element-properties {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-surface);
  border-left: 1px solid var(--border);
  overflow: hidden;
}

.element-properties-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.element-properties-title {
  font-size: 13px;
  font-weight: 600;
  margin: 0;
  color: var(--text);
}

.element-properties-type {
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  font-family: 'IBM Plex Mono', monospace;
  letter-spacing: 0.04em;
}

.element-properties-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 12px;
  padding: 20px;
  text-align: center;
}

.element-properties-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px 16px;
}

.props-section + .props-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.props-section-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-family: 'IBM Plex Mono', monospace;
  margin: 0 0 8px;
}

.props-list {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 12px;
  margin: 0;
  font-size: 12px;
}

.props-list dt {
  color: var(--text-muted);
  font-weight: 400;
}

.props-list dd {
  margin: 0;
  color: var(--text);
  text-align: right;
}

.mono {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
}

.props-text {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.props-linked-chunk {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0 0 8px;
  font-size: 12px;
}

.props-linked-tokens {
  color: var(--text-muted);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
}

.props-edit {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.props-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.props-field-label {
  font-size: 11px;
  color: var(--text-muted);
}

.props-input {
  width: 100%;
  padding: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 12px;
}

.props-bbox-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.props-edit-textarea {
  width: 100%;
  padding: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 12px;
  line-height: 1.5;
  resize: vertical;
  font-family: inherit;
}

.props-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.props-btn {
  padding: 4px 12px;
  font-size: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  cursor: pointer;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  transition: all var(--transition);
}

.props-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.props-btn--cancel:hover:not(:disabled) {
  color: var(--text);
}

.props-btn--primary {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.props-btn--primary:hover:not(:disabled) {
  filter: brightness(1.1);
}

.props-btn--danger {
  border-color: #c43d3d;
  color: #c43d3d;
}

.props-btn--danger:hover:not(:disabled) {
  background: rgba(196, 61, 61, 0.08);
}

.props-edit-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition);
}

.props-edit-btn:hover {
  background: var(--bg-hover);
  color: var(--accent);
  border-color: var(--accent);
}
</style>
