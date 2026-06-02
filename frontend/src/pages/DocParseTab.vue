<template>
  <div class="parse-tab" data-e2e="parse-tab">
    <LayersBar
      :elements="currentPageElements"
      :hidden-types="hiddenTypes"
      @update:hidden-types="(next) => (hiddenTypes = next)"
    >
      <template #action>
        <button
          type="button"
          class="tab-action-cta"
          :disabled="analysisStore.running"
          :title="t('newAnalysis.title')"
          data-e2e="parse-new-analysis"
          @click="onLaunchAnalysis"
        >
          <span v-if="analysisStore.running" class="tab-action-spinner" />
          <span v-else>+</span>
          {{ analysisStore.running ? t('newAnalysis.running') : t('newAnalysis.title') }}
        </button>
      </template>
    </LayersBar>
    <div class="parse-body">
      <aside class="parse-structure">
        <header class="parse-structure-header">
          <h2 class="parse-structure-title">{{ t('parse.structureTitle') }}</h2>
          <span class="parse-structure-count">
            {{ t('parse.structureNodes', { n: nodeCount }) }}
          </span>
          <div class="parse-structure-actions">
            <button
              type="button"
              class="tree-action-btn"
              :title="t('parse.expandAll')"
              :aria-label="t('parse.expandAll')"
              data-e2e="tree-expand-all"
              @click="onExpandAll"
            >
              ⊕
            </button>
            <button
              type="button"
              class="tree-action-btn"
              :title="t('parse.collapseAll')"
              :aria-label="t('parse.collapseAll')"
              data-e2e="tree-collapse-all"
              @click="onCollapseAll"
            >
              ⊖
            </button>
          </div>
        </header>
        <input
          v-model="filter"
          type="text"
          class="parse-structure-filter"
          :placeholder="t('parse.filterPlaceholder')"
          data-e2e="structure-filter"
        />
        <DocTreeRail
          :key="treeRemountKey"
          :nodes="filteredNodes"
          :loading="treeLoading"
          :error="treeError"
          :selected="selectedNodeRef"
          :highlight="selectedNodeRef"
          :default-open="treeDefaultOpen"
          @select="onTreeSelect"
          @reload="loadTree"
        />
      </aside>
      <div class="parse-stage">
        <PagePreviewWithOverlay
          v-if="displayedPages.length"
          :document-id="docId"
          :pages="displayedPages"
          :current-page="currentPage"
          :hidden-types="hiddenTypes"
          :show-labels="true"
          :highlighted-refs="highlightedRefs"
          @update:current-page="(p) => (currentPage = p)"
          @hover-element="onHoverElement"
          @click-element="onClickElement"
        />
        <div v-else-if="documentStore.workspaceLoading" class="parse-state">
          <span class="spinner" />
        </div>
        <div v-else class="parse-state parse-state--empty">
          <p>{{ t('parse.noAnalysis') }}</p>
        </div>
      </div>
      <ElementProperties
        :element="selectedElement"
        :page-width="currentPageWidth"
        :page-height="currentPageHeight"
        :page-number="currentPage"
        :linked-chunk="linkedChunk"
        :document-saving="documentStore.documentEditSaving"
        :document-committing="documentStore.documentEditCommitting"
        :has-pending-document-edits="documentStore.pendingDocumentCommands.length > 0"
        :previous-sibling-target-ref="selectedSiblingRefs.previousSiblingRef"
        :next-sibling-target-ref="selectedSiblingRefs.nextSiblingRef"
        :previous-group-target-ref="selectedGroupSiblingRefs.previousGroupRef"
        :next-group-target-ref="selectedGroupSiblingRefs.nextGroupRef"
        :parent-group-target-ref="selectedParentGroupTargetRef"
        :saving="chunksStore.saving"
        @preview-page-element="onPreviewPageElement"
        @clear-page-element-preview="clearPageElementPreview"
        @save-page-element="onSavePageElement"
        @apply-document-edit-commands="onApplyDocumentEditCommands"
        @commit-document-edits="onCommitDocumentEdits"
        @discard-document-edits="onDiscardDocumentEdits"
        @save-chunk="onSaveChunk"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Parse view (#264). Shows the Docling extraction graph for a document:
 *
 *   - LAYERS bar (chip filters per element type + Show labels toggle)
 *   - Structure tree (left rail — element hierarchy per page)
 *   - Page preview with bbox overlay (center)
 *
 * Two-way link between tree and overlay:
 *   - Selecting a node in the tree → highlight its bbox on the preview
 *   - Clicking a bbox → select the matching node in the tree
 */
import { computed, onMounted, ref, watch } from 'vue'
import type { DocChunk, DocTreeNode, DocumentEditCommandInput, ElementType, PageElement } from '../shared/types'
import { useAnalysisStore } from '../features/analysis/store'
import { useChunksStore } from '../features/chunks/store'
import { fetchDocumentTree } from '../features/document/api'
import {
  applyPageElementPreview,
  countTreeNodes,
  elementTargetRef,
  filterTreeNodes,
  findElementByRef,
  findPageNumberForRef,
} from '../features/document/parseTabState'
import {
  postCommandSelectionState,
  reconcileSelectionState,
  selectionStateFromRef,
} from '../features/document/parseTabSelection'
import {
  docChangeUiState,
  firstWorkspacePageNumber,
  nextPageAfterSelection,
  shouldReloadTreeAfterCommit,
  shouldReloadTreeForAnalysisChange,
} from '../features/document/parseTabWorkflow'
import {
  adjacentGroupSiblingRefs,
  adjacentSiblingRefs,
  parentGroupTargetRef,
} from '../features/document/siblingTargets'
import { useDocumentStore } from '../features/document/store'
import { chunkForElement } from '../features/document/linkedView'
import DocTreeRail from '../features/document/ui/DocTreeRail.vue'
import ElementProperties from '../features/document/ui/ElementProperties.vue'
import LayersBar from '../features/document/ui/LayersBar.vue'
import PagePreviewWithOverlay from '../features/document/ui/PagePreviewWithOverlay.vue'
import { useI18n } from '../shared/i18n'

const props = defineProps<{ docId: string }>()

const { t } = useI18n()
const documentStore = useDocumentStore()
const chunksStore = useChunksStore()
const analysisStore = useAnalysisStore()

async function onLaunchAnalysis(): Promise<void> {
  if (analysisStore.running) return
  await analysisStore.run(props.docId)
}

const currentPage = ref(1)
const hiddenTypes = ref<Set<string>>(new Set())

// Expand/Collapse all — bumping `treeRemountKey` re-keys the rail so every
// DocTreeNode mounts fresh and picks up the new `treeDefaultOpen` value.
const treeRemountKey = ref(0)
const treeDefaultOpen = ref<boolean | null>(null)
function onExpandAll(): void {
  treeDefaultOpen.value = true
  treeRemountKey.value++
}
function onCollapseAll(): void {
  treeDefaultOpen.value = false
  treeRemountKey.value++
}

const tree = ref<DocTreeNode[]>([])
const treeLoading = ref(false)
const treeError = ref<string | null>(null)
const filter = ref('')
const selectedNodeRef = ref<string | null>(null)
const selectedNodeSelfRef = ref<string | null>(null)
const transientPageElementPreview = ref<{
  targetRef: string
  payload: { content?: string; bbox?: [number, number, number, number]; type?: ElementType }
} | null>(null)
const effectiveTree = computed<DocTreeNode[]>(() => documentStore.workspaceDraftTree ?? tree.value)
const displayedPages = computed(() =>
  applyPageElementPreview(documentStore.workspacePages, transientPageElementPreview.value),
)

const currentPageData = computed(() => {
  return displayedPages.value.find((p) => p.page_number === currentPage.value) ?? null
})

const currentPageElements = computed<PageElement[]>(() => currentPageData.value?.elements ?? [])
const currentPageWidth = computed(() => currentPageData.value?.width ?? 0)
const currentPageHeight = computed(() => currentPageData.value?.height ?? 0)

const selectedElement = computed<PageElement | null>(() =>
  findElementByRef(documentStore.workspacePages, selectedNodeRef.value),
)

const linkedChunk = computed<DocChunk | null>(() => {
  if (!selectedElement.value) return null
  return chunkForElement(selectedElement.value, currentPage.value, chunksStore.chunks)
})

const nodeCount = computed(() => countTreeNodes(effectiveTree.value))
const selectedSiblingRefs = computed(() => adjacentSiblingRefs(effectiveTree.value, selectedNodeRef.value))
const selectedGroupSiblingRefs = computed(() => adjacentGroupSiblingRefs(effectiveTree.value, selectedNodeRef.value))
const selectedParentGroupTargetRef = computed(() => parentGroupTargetRef(effectiveTree.value, selectedNodeRef.value))

const filteredNodes = computed<DocTreeNode[]>(() => {
  const needle = filter.value.trim().toLowerCase()
  if (!needle) return effectiveTree.value
  return filterTreeNodes(effectiveTree.value, needle)
})

const highlightedRefs = computed<ReadonlySet<string>>(() => {
  if (!selectedNodeRef.value) return new Set()
  return new Set([selectedNodeRef.value])
})

async function loadTree(): Promise<void> {
  treeLoading.value = true
  treeError.value = null
  try {
    tree.value = await fetchDocumentTree(props.docId)
  } catch (e) {
    treeError.value = (e as Error).message || 'Failed to load tree'
  } finally {
    treeLoading.value = false
  }
}

function onPreviewPageElement(
  targetRef: string,
  payload: { content?: string; bbox?: [number, number, number, number]; type?: ElementType },
): void {
  transientPageElementPreview.value = { targetRef, payload }
}

function clearPageElementPreview(): void {
  transientPageElementPreview.value = null
}

function onTreeSelect(ref: string): void {
  setSelectedNodeRef(ref)
  currentPage.value = nextPageAfterSelection(currentPage.value, currentSelectionState())
}

function onHoverElement(_el: PageElement | null): void {
  // Hover is informational only — selection drives the tree highlight.
}

function onClickElement(el: PageElement): void {
  const ref = elementTargetRef(el)
  if (ref) setSelectedNodeRef(ref)
}

async function onSaveChunk(chunkId: string, text: string): Promise<void> {
  await chunksStore.updateText(props.docId, chunkId, text)
}

async function onSavePageElement(
  targetRef: string,
  payload: { content?: string; bbox?: [number, number, number, number]; type?: ElementType },
): Promise<void> {
  await documentStore.updatePageElement(props.docId, targetRef, payload)
  clearPageElementPreview()
}

async function onApplyDocumentEditCommands(commands: DocumentEditCommandInput[]): Promise<void> {
  const previousTree = effectiveTree.value
  await documentStore.applyDocumentEditCommands(props.docId, commands)
  const nextSelection = postCommandSelectionState(
    commands,
    previousTree,
    effectiveTree.value,
    documentStore.workspacePages,
  )
  if (nextSelection) {
    applySelectionState(nextSelection)
  }
  clearPageElementPreview()
}

async function onCommitDocumentEdits(): Promise<void> {
  const result = await documentStore.commitPendingDocumentEdits(props.docId)
  clearPageElementPreview()
  if (shouldReloadTreeAfterCommit(result)) {
    await loadTree()
  }
}

async function onDiscardDocumentEdits(): Promise<void> {
  await documentStore.discardPendingDocumentEdits(props.docId)
  clearPageElementPreview()
}

onMounted(async () => {
  await Promise.all([
    documentStore.loadWorkspace(props.docId),
    chunksStore.load(props.docId),
    loadTree(),
  ])
  currentPage.value = firstWorkspacePageNumber(documentStore.workspacePages, currentPage.value)
})

watch(
  () => props.docId,
  async (id) => {
    await Promise.all([documentStore.loadWorkspace(id), chunksStore.load(id), loadTree()])
    const nextState = docChangeUiState(documentStore.workspacePages, currentPage.value)
    applySelectionState(nextState.selection)
    filter.value = nextState.filter
    currentPage.value = nextState.currentPageNumber
  },
)

// Refetch the tree when the active analysis changes (#266 / #267).
// Triggered after an in-place analysis completes or after the user
// restores a different version from the History drawer — the tree
// is built server-side from the active analysis's `document_json`,
// so it has to be reloaded.
watch(
  () => documentStore.workspaceActiveAnalysis?.id,
  (newId, oldId) => {
    if (shouldReloadTreeForAnalysisChange(newId, oldId)) {
      clearSelection()
      loadTree()
    }
  },
)

watch(
  [
    () => documentStore.documentEditDraftVersion,
    () => documentStore.documentEditRefRemaps,
    effectiveTree,
    () => documentStore.workspacePages,
  ],
  () => {
    reconcileSelection()
  },
)

function setSelectedNodeRef(ref: string | null): void {
  applySelectionState(selectionStateFromRef(ref, effectiveTree.value, documentStore.workspacePages))
}

function clearSelection(): void {
  applySelectionState({ selectedRef: null, selectedSelfRef: null, selectedPageNumber: null })
}

function reconcileSelection(): void {
  if (!selectedNodeRef.value) return
  const nextSelection = reconcileSelectionState(
    {
      selectedRef: selectedNodeRef.value,
      selectedSelfRef: selectedNodeSelfRef.value,
      selectedPageNumber: selectedNodePageNumber.value,
    },
    effectiveTree.value,
    documentStore.workspacePages,
    documentStore.documentEditRefRemaps,
  )
  applySelectionState(nextSelection)
}

const selectedNodePageNumber = ref<number | null>(null)

function currentSelectionState() {
  return {
    selectedRef: selectedNodeRef.value,
    selectedSelfRef: selectedNodeSelfRef.value,
    selectedPageNumber: selectedNodePageNumber.value,
  }
}

function applySelectionState(selection: {
  selectedRef: string | null
  selectedSelfRef: string | null
  selectedPageNumber: number | null
}): void {
  selectedNodeRef.value = selection.selectedRef
  selectedNodeSelfRef.value = selection.selectedSelfRef
  selectedNodePageNumber.value = selection.selectedPageNumber
  if (selection.selectedPageNumber !== null && selection.selectedPageNumber !== currentPage.value) {
    currentPage.value = selection.selectedPageNumber
  }
}
</script>

<style scoped>
.parse-tab {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.parse-body {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 360px;
  flex: 1;
  min-height: 0;
}

.parse-structure {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-surface);
  min-height: 0;
  overflow: hidden;
}

.parse-structure-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.parse-structure-title {
  font-size: 13px;
  font-weight: 600;
  margin: 0;
  color: var(--text);
}

.parse-structure-count {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'IBM Plex Mono', monospace;
}

.parse-structure-actions {
  margin-left: auto;
  display: inline-flex;
  gap: 4px;
}

.tree-action-btn {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  line-height: 1;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.tree-action-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.parse-structure-filter {
  margin: 8px 14px;
  padding: 6px 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 12px;
}

.parse-stage {
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
  overflow: hidden;
  min-height: 0;
}

.parse-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 13px;
}

.parse-state--empty {
  flex-direction: column;
  gap: 12px;
}

.tab-action-cta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  color: white;
  font-size: 12px;
  cursor: pointer;
  transition: filter var(--transition);
}

.tab-action-cta:hover:not(:disabled) {
  filter: brightness(1.1);
}

.tab-action-cta:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.tab-action-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(255, 255, 255, 0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 2px solid var(--border-light);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
