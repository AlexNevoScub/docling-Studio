# Design: Structural document edits with low-payload draft sessions

- **Issue:** n/a
- **Title on issue:** Structural document editing with stable draft identities and small frontend/backend payloads
- **Author:** OpenCode
- **Date:** 2026-05-30
- **Status:** Draft
- **Target milestone:** n/a
- **Impacted layers:** backend (`domain`, `persistence`, `services`, `api`) · frontend (`features/document`, `shared`, parse tree UI) · docs
- **Audit dimensions likely touched:** DDD · Decoupling · KISS · Tests · Documentation
- **ADR spawned?:** no

---

## 1. Problem

The current V1 document-edit workflow is clean for ref-stable field edits on existing page elements, but it does not yet provide a clean foundation for structural document operations such as:

- reparenting an item
- reordering siblings within a parent
- merging adjacent text items
- later insert/delete/split operations

The main limitation is that the current editing identity is still centered on Docling `self_ref`, while structural Docling mutations can renumber refs. At the same time, the current protocol still returns full regenerated `pages` and `tree`, and commit still depends on shipping large derived state between frontend and backend.

We need a design that:

- keeps `document_json` canonical on the backend
- supports structural edits safely
- preserves stable frontend editing identity across ref churn
- reduces the amount of data exchanged between frontend and backend

## 2. Goals

- [ ] Add a backend-managed draft session model for document edits.
- [ ] Introduce stable draft identities that do not break when Docling `self_ref`s shift.
- [ ] Support structural commands cleanly in the backend command replay model.
- [ ] Reduce payload sizes by moving from full projection responses toward versioned deltas.
- [ ] Replace full frontend projection commit payloads with version- or digest-based verification.

## 3. Non-goals

- Rewriting V1 field editing before the migration path is clear.
- Pushing raw `document_json` to the frontend.
- Making the frontend authoritative for structural semantics.
- Solving collaborative multi-user editing in the first iteration.

## 4. Current constraints

### 4.1 What V1 already does well

The current implementation already establishes the right core invariant:

- `document_json` is canonical
- `pages_json` is derived
- tree projection is derived
- the backend replays commands and regenerates projections from Docling before commit

That should remain unchanged.

### 4.2 What breaks for structural edits

The current `self_ref`-centric workflow gets weaker when edits can mutate structure.

Problems:

- Docling insert/delete/replace flows can renumber `self_ref`s.
- Frontend selection and command targeting become fragile if identities shift.
- Returning full `pages` and full `tree` after every edit becomes expensive.
- Sending full `frontendPages` on commit is more data than necessary.

## 5. Proposed design

### 5.1 Backend-managed draft sessions

Introduce an explicit draft session model.

Suggested session state:

```python
@dataclass(frozen=True)
class DocumentEditSession:
    id: str
    document_id: str
    base_analysis_id: str
    draft_version: int
    actor: str
    created_at: datetime
    updated_at: datetime
```

Each session is anchored to one completed analysis snapshot.

The backend owns:

- current command log for the session
- current draft version
- current draft identity mapping

### 5.2 Stable draft identity layer

Add stable session-local node identities independent of raw Docling refs.

Suggested concept:

```python
@dataclass(frozen=True)
class DraftNodeBinding:
    session_id: str
    draft_ref: str
    self_ref: str | None
    node_kind: str
```
```

The key rule:

- frontend edits and selection use `draft_ref`
- backend maps `draft_ref -> current self_ref`

This allows structural edits to change Docling refs internally without breaking frontend references.

### 5.3 Command model evolution

Keep field edits and add structural edits under one command family.

Suggested command set:

```text
update_page_element
move_item_before
move_item_after
reparent_item
merge_items
```

Later:

```text
insert_item
delete_item
split_item
```

Field edit example:

```json
{
  "kind": "update_page_element",
  "draftRef": "node-123",
  "payload": {
    "content": "Updated content",
    "bbox": [10, 20, 110, 60],
    "type": "section_header"
  }
}
```

Structural edit examples:

```json
{
  "kind": "move_item_after",
  "draftRef": "node-123",
  "afterDraftRef": "node-124"
}
```

```json
{
  "kind": "reparent_item",
  "draftRef": "node-123",
  "parentDraftRef": "node-200",
  "index": 0
}
```

```json
{
  "kind": "merge_items",
  "leadingDraftRef": "node-123",
  "trailingDraftRef": "node-124",
  "separator": " "
}
```

### 5.4 Backend replay remains canonical

Structural edit semantics must live only in the backend.

Flow:

1. load canonical `document_json`
2. rebuild draft-ref bindings for the session if needed
3. replay all prior session commands
4. apply new commands
5. regenerate derived projections
6. compute response deltas

The frontend should not perform structural tree surgery as an authoritative algorithm.

### 5.5 Low-payload protocol

Requests should stay small.

Suggested request shape:

```json
{
  "sessionId": "sess-1",
  "draftVersion": 4,
  "commands": [ ... ]
}
```

Suggested response shape:

```json
{
  "sessionId": "sess-1",
  "draftVersion": 5,
  "pagePatches": [ ... ],
  "treePatches": [ ... ],
  "refRemaps": [ ... ],
  "selectionRemap": null
}
```

The goal is to stop returning full `pages` and full `tree` by default for every command round-trip.

### 5.6 Delta projections instead of full projections

Move toward patch responses.

Suggested patch types:

- `pagePatches`
  - changed page elements only
  - changed page metadata only when necessary
- `treePatches`
  - updated node label/type
  - moved child list entries
  - removed nodes
  - inserted nodes
- `refRemaps`
  - `draft_ref -> self_ref | null`

This keeps payloads small while still allowing backend-derived truth to drive the UI.

### 5.7 Commit protocol evolution

The current commit path sends full `frontendPages`. That should be replaced.

Suggested commit request:

```json
{
  "sessionId": "sess-1",
  "draftVersion": 5,
  "expectedDigest": "sha256:..."
}
```

Suggested backend behavior:

1. load current session state
2. verify `draftVersion`
3. optionally verify digest over canonical draft projections
4. persist replayed draft into analysis snapshot
5. mark commands committed
6. close or advance the draft session

This removes the need to send full frontend projections back during commit.

### 5.8 Frontend rendering model

The frontend should become thinner over time.

Recommended state layers:

- committed analysis-backed state
- backend-confirmed draft session state
- transient local preview state for in-progress form editing only

Recommended identity usage:

- selection uses `draftRef`
- command payloads use `draftRef`
- backend response patches update local draft state by `draftRef`

Recommended rendering precedence:

- transient preview
- backend-confirmed draft state
- committed state

### 5.9 First structural command to add

Start with sibling reordering:

- `move_item_before`
- or `move_item_after`

Why first:

- simpler than merge
- exposes the identity/remapping problem clearly
- validates tree patch application without requiring content merging semantics

## 6. Migration plan

### Slice 1: Session and identity foundation

- Add `document_edit_sessions` persistence.
- Add draft-ref binding persistence.
- Add `sessionId`, `baseAnalysisId`, and `draftVersion` to edit APIs.
- Keep existing `update_page_element` behavior but begin exposing `draftRef` alongside `self_ref`.

### Slice 2: Frontend identity migration

- Teach page elements and tree nodes to carry both `draftRef` and `self_ref`.
- Switch selection, command creation, and edit handling to `draftRef`.
- Keep `self_ref` as backend/internal Docling lookup only.

### Slice 3: Commit payload reduction

- Stop sending full `frontendPages` on commit.
- Commit by `sessionId` + `draftVersion`.
- Optionally add an `expectedDigest` if extra verification is needed.

### Slice 4: Delta responses

- Replace full `pages` / `tree` responses with patch responses.
- Add frontend patch application utilities.
- Keep a debug or fallback full-response mode while stabilizing.

### Slice 5: First structural command

- Implement `move_item_after` or `move_item_before`.
- Verify draft-ref stability and tree patch correctness.
- Add regression tests for reorder plus commit.

### Slice 6: Richer structural commands

- Add `reparent_item`.
- Add `merge_items`.
- Then consider insert/delete/split with explicit remapping behavior.

## 7. Risks

- Draft-ref mapping can become inconsistent if replay and remap logic are under-specified.
- Delta/patch logic is more complex than full projection replacement.
- Structural Docling edits may still require careful handling around page-level projections and parent/child invariants.
- Merge semantics can be ambiguous unless command payloads are explicit about separators, surviving node identity, and deleted node behavior.

## 8. Testing strategy

- Backend tests for draft session versioning and identity remapping.
- Backend tests for structural replay semantics per command.
- API tests for version mismatch, stale session detection, and patch responses.
- Frontend store tests for draft-ref based patch application.
- Component tests for selection continuity after structural edits.

## 9. Decision

Proceed by evolving the current V1 workflow into a backend-owned draft-session architecture with stable `draftRef` identities, versioned commands, and patch-based responses. Keep `document_json` canonical, move structural semantics entirely into backend replay, and reduce payload size by removing full projection transfers wherever possible.
