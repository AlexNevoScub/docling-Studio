"""Document edit service — optimistic document_json mutations with replay."""

from __future__ import annotations

import json
import uuid
import copy
from dataclasses import asdict
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from docling_core.types.doc import DocItem, DoclingDocument, SectionHeaderItem, TextItem, TitleItem
from docling_core.types.doc.base import BoundingBox, CoordOrigin
from docling_core.types.doc.labels import DocItemLabel

from domain.models import DocumentEdit, DocumentEditSession, DraftNodeBinding
from domain.ports import DocumentEditSessionRepository, DraftNodeBindingRepository
from domain.value_objects import DocumentEditAction, DocumentEditStatus
from infra.docling_tree import DoclingTreeReader
from infra.local_converter import _extract_pages_detail
from services.chunk_service import _build_tree_nodes

if TYPE_CHECKING:
    from domain.models import AnalysisJob, Document
    from domain.ports import (
        AnalysisRepository,
        DocumentEditRepository,
        DocumentEditSessionRepository,
        DocumentRepository,
        DocumentTreeReader,
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


class DocumentEditServiceError(Exception):
    http_status: int = 400

    def __init__(self, message: str, *, http_status: int | None = None):
        super().__init__(message)
        if http_status is not None:
            self.http_status = http_status


class DocumentEditNotFoundError(DocumentEditServiceError):
    http_status = 404


class DocumentEditConflictError(DocumentEditServiceError):
    http_status = 409


class DocumentEditService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        analysis_repo: AnalysisRepository,
        edit_repo: DocumentEditRepository,
        session_repo: DocumentEditSessionRepository,
        binding_repo: DraftNodeBindingRepository,
        tree_reader: DocumentTreeReader | None = None,
        actor: str = "user",
    ) -> None:
        self._documents = document_repo
        self._analyses = analysis_repo
        self._edits = edit_repo
        self._sessions = session_repo
        self._bindings = binding_repo
        self._tree = tree_reader or DoclingTreeReader()
        self._actor = actor

    async def get_session(self, document_id: str) -> dict[str, Any]:
        await self._require_document(document_id)
        analysis = await self._require_analysis(document_id)
        edits = await self._edits.find_pending_for_document(document_id)
        session = await self._get_or_create_session(document_id, analysis.id, edits=edits)
        document = self._load_doc(analysis.document_json)
        bindings = await self._ensure_bindings(session, document)
        document = self._apply_edits(document, edits, bindings)
        pages = self._render_pages(document, bindings)
        tree = self._render_tree(document, bindings)
        return {
            "sessionId": session.id,
            "analysisId": analysis.id,
            "baseAnalysisId": session.base_analysis_id,
            "draftVersion": session.draft_version,
            "pages": pages,
            "tree": tree,
            "pagePatches": [],
            "treePatches": [],
            "refRemaps": self._render_ref_remaps(bindings),
            "pendingCommands": [self._edit_to_dict(edit) for edit in edits],
        }

    async def apply_commands(
        self,
        document_id: str,
        *,
        session_id: str,
        draft_version: int,
        commands: list[dict[str, Any]],
        actor: str | None = None,
    ) -> dict[str, Any]:
        await self._require_document(document_id)
        analysis = await self._require_analysis(document_id)
        pending = await self._edits.find_pending_for_document(document_id)
        session = await self._require_session(
            document_id,
            analysis.id,
            session_id=session_id,
            draft_version=draft_version,
            edits=pending,
        )
        new_edits = [
            self._command_to_edit(document_id, analysis.id, command, actor=actor or self._actor)
            for command in commands
        ]
        base_document = self._load_doc(analysis.document_json)
        bindings = await self._ensure_bindings(session, base_document)
        previous_document = self._apply_edits(
            self._load_doc(analysis.document_json), pending, bindings
        )
        preview_document = self._apply_edits(base_document, [*pending, *new_edits], bindings)
        previous_pages = self._render_pages(previous_document, bindings)
        preview_pages = self._render_pages(preview_document, bindings)
        previous_tree = self._render_tree(previous_document, bindings)
        preview_tree = self._render_tree(preview_document, bindings)
        for edit in new_edits:
            await self._edits.insert(edit)
        session.draft_version += 1
        session.updated_at = _utcnow()
        await self._sessions.update(session)
        return {
            "sessionId": session.id,
            "analysisId": analysis.id,
            "baseAnalysisId": session.base_analysis_id,
            "draftVersion": session.draft_version,
            "pages": preview_pages,
            "tree": preview_tree,
            "pagePatches": self._build_page_patches(previous_pages, preview_pages),
            "treePatches": self._build_tree_patches(previous_tree, preview_tree),
            "refRemaps": self._render_ref_remaps(bindings),
            "pendingCommands": [self._edit_to_dict(cmd) for cmd in [*pending, *new_edits]],
        }

    async def commit(
        self,
        document_id: str,
        *,
        session_id: str,
        draft_version: int,
    ) -> dict[str, Any]:
        await self._require_document(document_id)
        analysis = await self._require_analysis(document_id)
        pending = await self._edits.find_pending_for_document(document_id)
        session = await self._require_session(
            document_id,
            analysis.id,
            session_id=session_id,
            draft_version=draft_version,
            edits=pending,
        )
        if not pending:
            await self._sessions.delete(session.id)
            return {
                "committed": True,
                "consistent": True,
                "differences": [],
                "pages": [],
                "tree": [],
            }

        document = self._load_doc(analysis.document_json)
        bindings = await self._ensure_bindings(session, document)
        previous_pages = self._render_pages(document, bindings)
        previous_tree = self._render_tree(document, bindings)
        document = self._apply_edits(document, pending, bindings)
        backend_pages = self._render_pages(document, bindings)
        backend_tree = self._render_tree(document, bindings)

        analysis.document_json = json.dumps(document.export_to_dict())
        analysis.pages_json = json.dumps(backend_pages)
        analysis.content_markdown = document.export_to_markdown()
        analysis.content_html = document.export_to_html()
        analysis.completed_at = _utcnow()
        await self._analyses.update_status(analysis)
        await self._edits.mark_committed([edit.id for edit in pending])
        await self._sessions.delete(session.id)
        return {
            "committed": True,
            "consistent": True,
            "differences": [],
            "pages": backend_pages,
            "tree": backend_tree,
            "pagePatches": self._build_page_patches(previous_pages, backend_pages),
            "treePatches": self._build_tree_patches(previous_tree, backend_tree),
            "refRemaps": self._render_ref_remaps(bindings),
        }

    async def discard(self, document_id: str) -> int:
        await self._require_document(document_id)
        session = await self._sessions.find_by_document(document_id)
        cleared = await self._edits.clear_pending_for_document(document_id)
        if session is not None:
            await self._sessions.delete(session.id)
        return cleared

    async def _require_document(self, document_id: str) -> Document:
        doc = await self._documents.find_by_id(document_id)
        if doc is None:
            raise DocumentEditNotFoundError(f"Document not found: {document_id}")
        return doc

    async def _require_analysis(self, document_id: str) -> AnalysisJob:
        job = await self._analyses.find_latest_completed_by_document(document_id)
        if job is None or not job.document_json:
            raise DocumentEditNotFoundError(
                f"No completed analysis with document_json for document {document_id}"
            )
        return job

    async def _get_or_create_session(
        self,
        document_id: str,
        analysis_id: str,
        *,
        edits: list[DocumentEdit],
    ) -> DocumentEditSession:
        session = await self._sessions.find_by_document(document_id)
        if session is None:
            session = DocumentEditSession(
                id=_new_id(),
                document_id=document_id,
                base_analysis_id=analysis_id,
                draft_version=0,
                actor=self._actor,
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
            await self._sessions.insert(session)
            return session
        if session.base_analysis_id == analysis_id:
            return session
        if edits:
            raise DocumentEditConflictError(
                "Draft session is stale: the active analysis changed while edits were pending",
            )
        session.base_analysis_id = analysis_id
        session.draft_version = 0
        session.updated_at = _utcnow()
        await self._sessions.update(session)
        return session

    async def _require_session(
        self,
        document_id: str,
        analysis_id: str,
        *,
        session_id: str,
        draft_version: int,
        edits: list[DocumentEdit],
    ) -> DocumentEditSession:
        session = await self._get_or_create_session(document_id, analysis_id, edits=edits)
        if session.id != session_id:
            raise DocumentEditConflictError("Draft session mismatch; refresh the document editor")
        if session.draft_version != draft_version:
            raise DocumentEditConflictError("Draft version mismatch; refresh the document editor")
        return session

    def _preview_document(
        self,
        analysis: AnalysisJob,
        edits: list[DocumentEdit],
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        document = self._load_doc(analysis.document_json)
        return self._apply_edits(document, edits, bindings)

    def _load_doc(self, raw_document_json: str | None) -> DoclingDocument:
        if not raw_document_json:
            raise DocumentEditNotFoundError("Missing document_json")
        return DoclingDocument.model_validate(json.loads(raw_document_json))

    def _apply_edits(
        self,
        document: DoclingDocument,
        edits: list[DocumentEdit],
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        for edit in edits:
            if edit.action is DocumentEditAction.UPDATE_PAGE_ELEMENT:
                self._apply_update_page_element(document, edit, bindings)
                continue
            if edit.action is DocumentEditAction.INSERT_ITEM:
                document = self._apply_insert_item(document, edit, bindings)
                continue
            if edit.action is DocumentEditAction.DELETE_ITEM:
                document = self._apply_delete_item(document, edit, bindings)
                continue
            if edit.action is DocumentEditAction.MERGE_ITEMS:
                document = self._apply_merge_items(document, edit, bindings)
                continue
            if edit.action is DocumentEditAction.SPLIT_ITEM:
                document = self._apply_split_item(document, edit, bindings)
                continue
            if edit.action is DocumentEditAction.MOVE_ITEM_BEFORE:
                document = self._apply_move_item_before(document, edit, bindings)
                continue
            if edit.action is DocumentEditAction.MOVE_ITEM_AFTER:
                document = self._apply_move_item_after(document, edit, bindings)
                continue
            if edit.action is DocumentEditAction.REPARENT_ITEM:
                document = self._apply_reparent_item(document, edit, bindings)
                continue
            raise DocumentEditConflictError(
                f"Unsupported document edit action: {edit.action.value}"
            )
        return document

    def _command_to_edit(
        self,
        document_id: str,
        analysis_id: str,
        command: dict[str, Any],
        *,
        actor: str,
    ) -> DocumentEdit:
        action = DocumentEditAction(command.get("action"))
        target_ref = str(command.get("targetRef") or command.get("target_ref") or "")
        payload = command.get("payload")
        if not isinstance(payload, dict):
            raise DocumentEditConflictError("Document edit command payload must be an object")
        if not target_ref:
            raise DocumentEditConflictError("Document edit command targetRef is required")
        self._validate_payload(action, payload)
        return DocumentEdit(
            id=_new_id(),
            document_id=document_id,
            analysis_id=analysis_id,
            action=action,
            target_ref=target_ref,
            payload=payload,
            actor=actor,
            at=_utcnow(),
            status=DocumentEditStatus.PENDING,
        )

    def _validate_payload(self, action: DocumentEditAction, payload: dict[str, Any]) -> None:
        if action is DocumentEditAction.UPDATE_PAGE_ELEMENT:
            allowed = {"content", "bbox", "type"}
            unknown = sorted(set(payload) - allowed)
            if unknown:
                raise DocumentEditConflictError(
                    f"Unsupported update_page_element payload fields: {', '.join(unknown)}"
                )
            if not payload:
                raise DocumentEditConflictError("update_page_element payload cannot be empty")
            if (
                "content" in payload
                and payload["content"] is not None
                and not isinstance(payload["content"], str)
            ):
                raise DocumentEditConflictError("payload.content must be a string")
            if (
                "type" in payload
                and payload["type"] is not None
                and not isinstance(payload["type"], str)
            ):
                raise DocumentEditConflictError("payload.type must be a string")
            if "bbox" in payload:
                bbox = payload["bbox"]
                if not isinstance(bbox, list) or len(bbox) != 4:
                    raise DocumentEditConflictError("payload.bbox must be a 4-number list")
                try:
                    [float(value) for value in bbox]
                except (TypeError, ValueError) as exc:
                    raise DocumentEditConflictError(
                        "payload.bbox must contain only numbers"
                    ) from exc
            return

        if action is DocumentEditAction.MOVE_ITEM_AFTER:
            allowed = {"afterTargetRef"}
            unknown = sorted(set(payload) - allowed)
            if unknown:
                raise DocumentEditConflictError(
                    f"Unsupported move_item_after payload fields: {', '.join(unknown)}"
                )
            after_target_ref = payload.get("afterTargetRef")
            if not isinstance(after_target_ref, str) or not after_target_ref:
                raise DocumentEditConflictError(
                    "move_item_after payload.afterTargetRef is required"
                )
            return

        if action is DocumentEditAction.INSERT_ITEM:
            allowed = {"content"}
            unknown = sorted(set(payload) - allowed)
            if unknown:
                raise DocumentEditConflictError(
                    f"Unsupported insert_item payload fields: {', '.join(unknown)}"
                )
            content = payload.get("content")
            if not isinstance(content, str):
                raise DocumentEditConflictError("insert_item payload.content is required")
            return

        if action is DocumentEditAction.DELETE_ITEM:
            unknown = sorted(payload)
            if unknown:
                raise DocumentEditConflictError(
                    f"Unsupported delete_item payload fields: {', '.join(unknown)}"
                )
            return

        if action is DocumentEditAction.MERGE_ITEMS:
            allowed = {"trailingTargetRef", "separator"}
            unknown = sorted(set(payload) - allowed)
            if unknown:
                raise DocumentEditConflictError(
                    f"Unsupported merge_items payload fields: {', '.join(unknown)}"
                )
            trailing_target_ref = payload.get("trailingTargetRef")
            if not isinstance(trailing_target_ref, str) or not trailing_target_ref:
                raise DocumentEditConflictError("merge_items payload.trailingTargetRef is required")
            separator = payload.get("separator")
            if separator is not None and not isinstance(separator, str):
                raise DocumentEditConflictError("merge_items payload.separator must be a string")
            return

        if action is DocumentEditAction.SPLIT_ITEM:
            allowed = {"splitIndex"}
            unknown = sorted(set(payload) - allowed)
            if unknown:
                raise DocumentEditConflictError(
                    f"Unsupported split_item payload fields: {', '.join(unknown)}"
                )
            split_index = payload.get("splitIndex")
            if not isinstance(split_index, int) or split_index < 1:
                raise DocumentEditConflictError(
                    "split_item payload.splitIndex must be a positive integer"
                )
            return

        if action is DocumentEditAction.MOVE_ITEM_BEFORE:
            allowed = {"beforeTargetRef"}
            unknown = sorted(set(payload) - allowed)
            if unknown:
                raise DocumentEditConflictError(
                    f"Unsupported move_item_before payload fields: {', '.join(unknown)}"
                )
            before_target_ref = payload.get("beforeTargetRef")
            if not isinstance(before_target_ref, str) or not before_target_ref:
                raise DocumentEditConflictError(
                    "move_item_before payload.beforeTargetRef is required"
                )
            return

        if action is DocumentEditAction.REPARENT_ITEM:
            allowed = {"parentTargetRef", "index"}
            unknown = sorted(set(payload) - allowed)
            if unknown:
                raise DocumentEditConflictError(
                    f"Unsupported reparent_item payload fields: {', '.join(unknown)}"
                )
            parent_target_ref = payload.get("parentTargetRef")
            if not isinstance(parent_target_ref, str) or not parent_target_ref:
                raise DocumentEditConflictError("reparent_item payload.parentTargetRef is required")
            index = payload.get("index")
            if index is not None and (not isinstance(index, int) or index < 0):
                raise DocumentEditConflictError(
                    "reparent_item payload.index must be a non-negative integer"
                )
            return

        raise DocumentEditConflictError(f"Unsupported document edit action: {action.value}")

    def _apply_update_page_element(
        self,
        document: DoclingDocument,
        edit: DocumentEdit,
        bindings: dict[str, DraftNodeBinding],
    ) -> None:
        target_ref = self._resolve_self_ref(edit.target_ref, bindings)
        item = self._find_item(document, target_ref)
        payload = edit.payload
        if "content" in payload:
            self._apply_content(item, target_ref, payload.get("content"))
        if "bbox" in payload:
            self._apply_bbox(document, item, payload["bbox"])
        if "type" in payload:
            self._apply_type(document, item, target_ref, payload.get("type"))

    def _apply_move_item_after(
        self,
        document: DoclingDocument,
        edit: DocumentEdit,
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        target_ref = self._resolve_self_ref(edit.target_ref, bindings)
        after_target_ref = self._resolve_self_ref(
            str(edit.payload.get("afterTargetRef") or ""),
            bindings,
        )
        if target_ref == after_target_ref:
            raise DocumentEditConflictError("move_item_after targetRef cannot equal afterTargetRef")
        return self._reorder_item_after(document, target_ref, after_target_ref)

    def _apply_insert_item(
        self,
        document: DoclingDocument,
        edit: DocumentEdit,
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        target_ref = self._resolve_self_ref(edit.target_ref, bindings)
        content = str(edit.payload.get("content") or "")
        return self._insert_item(document, target_ref, content=content)

    def _apply_delete_item(
        self,
        document: DoclingDocument,
        edit: DocumentEdit,
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        target_ref = self._resolve_self_ref(edit.target_ref, bindings)
        return self._delete_item(document, target_ref)

    def _apply_merge_items(
        self,
        document: DoclingDocument,
        edit: DocumentEdit,
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        target_ref = self._resolve_self_ref(edit.target_ref, bindings)
        trailing_target_ref = self._resolve_self_ref(
            str(edit.payload.get("trailingTargetRef") or ""),
            bindings,
        )
        if target_ref == trailing_target_ref:
            raise DocumentEditConflictError("merge_items targetRef cannot equal trailingTargetRef")
        separator = str(edit.payload.get("separator") or "")
        return self._merge_items(document, target_ref, trailing_target_ref, separator=separator)

    def _apply_split_item(
        self,
        document: DoclingDocument,
        edit: DocumentEdit,
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        target_ref = self._resolve_self_ref(edit.target_ref, bindings)
        split_index = int(edit.payload.get("splitIndex") or 0)
        return self._split_item(document, target_ref, split_index=split_index)

    def _apply_move_item_before(
        self,
        document: DoclingDocument,
        edit: DocumentEdit,
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        target_ref = self._resolve_self_ref(edit.target_ref, bindings)
        before_target_ref = self._resolve_self_ref(
            str(edit.payload.get("beforeTargetRef") or ""),
            bindings,
        )
        if target_ref == before_target_ref:
            raise DocumentEditConflictError(
                "move_item_before targetRef cannot equal beforeTargetRef"
            )
        return self._reorder_item_before(document, target_ref, before_target_ref)

    def _apply_reparent_item(
        self,
        document: DoclingDocument,
        edit: DocumentEdit,
        bindings: dict[str, DraftNodeBinding],
    ) -> DoclingDocument:
        target_ref = self._resolve_self_ref(edit.target_ref, bindings)
        parent_target_ref = self._resolve_self_ref(
            str(edit.payload.get("parentTargetRef") or ""),
            bindings,
        )
        if target_ref == parent_target_ref:
            raise DocumentEditConflictError("reparent_item targetRef cannot equal parentTargetRef")
        index = edit.payload.get("index")
        return self._reparent_item(document, target_ref, parent_target_ref, index=index)

    def _apply_content(self, item: DocItem, target_ref: str, content: Any) -> None:
        if not hasattr(item, "text"):
            raise DocumentEditConflictError(f"Item does not support content edits: {target_ref}")
        next_text = "" if content is None else str(content)
        item.text = next_text
        if hasattr(item, "orig"):
            item.orig = next_text

    def _apply_bbox(self, document: DoclingDocument, item: DocItem, bbox_values: list[Any]) -> None:
        if not getattr(item, "prov", None):
            raise DocumentEditConflictError(
                f"Item does not have provenance: {getattr(item, 'self_ref', '')}"
            )
        for prov in item.prov:
            page = document.pages.get(prov.page_no)
            if page is None:
                raise DocumentEditConflictError(f"Page not found for bbox update: {prov.page_no}")
            top_left_bbox = BoundingBox(
                l=float(bbox_values[0]),
                t=float(bbox_values[1]),
                r=float(bbox_values[2]),
                b=float(bbox_values[3]),
                coord_origin=CoordOrigin.TOPLEFT,
            )
            current_bbox = prov.bbox
            if current_bbox is not None and current_bbox.coord_origin is CoordOrigin.BOTTOMLEFT:
                prov.bbox = top_left_bbox.to_bottom_left_origin(page.size.height)
            else:
                prov.bbox = top_left_bbox

    def _apply_type(
        self, document: DoclingDocument, item: DocItem, target_ref: str, type_name: Any
    ) -> None:
        if type_name is None:
            return
        next_label = _TYPE_TO_LABEL.get(str(type_name))
        if next_label is None:
            raise DocumentEditConflictError(f"Unsupported page element type: {type_name}")
        allowed = _allowed_labels_for_item(item)
        if next_label not in allowed:
            supported = ", ".join(sorted(_label_to_type_name(label) for label in allowed))
            raise DocumentEditConflictError(
                f"Type change not supported for {target_ref}: {type_name} (allowed: {supported})"
            )
        if isinstance(item, TextItem):
            replacement = _build_text_family_item(item, next_label)
            if replacement is None:
                item.label = next_label
                return
            _replace_text_item_in_document(document, item, replacement)
            return
        item.label = next_label

    def _find_item(self, document: DoclingDocument, target_ref: str):
        for item, _level in document.iterate_items(with_groups=True):
            if getattr(item, "self_ref", "") == target_ref:
                return item
        raise DocumentEditNotFoundError(f"Document item not found: {target_ref}")

    def _render_pages(
        self,
        document: DoclingDocument,
        bindings: dict[str, DraftNodeBinding],
    ) -> list[dict[str, Any]]:
        pages, _skipped = _extract_pages_detail(SimpleNamespace(document=document))
        rendered = [asdict(page) for page in pages]
        bindings_by_self_ref = {
            binding.self_ref: binding.draft_ref for binding in bindings.values() if binding.self_ref
        }
        for page in rendered:
            for element in page.get("elements", []):
                draft_ref = bindings_by_self_ref.get(str(element.get("self_ref") or ""), "")
                if draft_ref:
                    element["draftRef"] = draft_ref
        return rendered

    def _render_tree(
        self,
        document: DoclingDocument,
        bindings: dict[str, DraftNodeBinding],
    ) -> list[dict[str, Any]]:
        tree = _build_tree_nodes(document.export_to_dict(), self._tree)
        bindings_by_self_ref = {
            binding.self_ref: binding.draft_ref for binding in bindings.values() if binding.self_ref
        }
        self._attach_tree_draft_refs(tree, bindings_by_self_ref)
        return tree

    def _attach_tree_draft_refs(
        self,
        nodes: list[dict[str, Any]],
        bindings_by_self_ref: dict[str, str],
    ) -> None:
        for node in nodes:
            ref = str(node.get("ref") or "")
            draft_ref = bindings_by_self_ref.get(ref, "")
            if draft_ref:
                node["draftRef"] = draft_ref
            children = node.get("children")
            if isinstance(children, list):
                self._attach_tree_draft_refs(children, bindings_by_self_ref)

    def _render_ref_remaps(self, bindings: dict[str, DraftNodeBinding]) -> list[dict[str, Any]]:
        return [
            {
                "draftRef": binding.draft_ref,
                "selfRef": binding.self_ref,
                "nodeKind": binding.node_kind,
            }
            for binding in bindings.values()
        ]

    def _build_page_patches(
        self,
        previous_pages: list[dict[str, Any]],
        next_pages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        previous_by_number = {
            int(page.get("page_number") or 0): page
            for page in previous_pages
            if page.get("page_number")
        }
        next_by_number = {
            int(page.get("page_number") or 0): page
            for page in next_pages
            if page.get("page_number")
        }
        page_numbers = sorted(set(previous_by_number) | set(next_by_number))
        patches: list[dict[str, Any]] = []
        for page_number in page_numbers:
            previous_page = previous_by_number.get(page_number)
            next_page = next_by_number.get(page_number)
            if next_page is None:
                patches.append({"op": "remove", "pageNumber": page_number})
                continue
            if previous_page != next_page:
                patches.append({"op": "upsert", "pageNumber": page_number, "page": next_page})
        return patches

    def _build_tree_patches(
        self,
        previous_tree: list[dict[str, Any]],
        next_tree: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if previous_tree == next_tree:
            return []
        return [{"op": "replace", "path": [], "nodes": next_tree}]

    async def _ensure_bindings(
        self,
        session: DocumentEditSession,
        document: DoclingDocument,
    ) -> dict[str, DraftNodeBinding]:
        existing = await self._bindings.find_by_session(session.id)
        existing_by_self_ref = {
            binding.self_ref: binding for binding in existing if binding.self_ref is not None
        }
        next_bindings: list[DraftNodeBinding] = []
        changed = len(existing) == 0
        for self_ref, node_kind in self._collect_bindable_refs(document):
            binding = existing_by_self_ref.get(self_ref)
            if binding is None:
                changed = True
                binding = DraftNodeBinding(
                    session_id=session.id,
                    draft_ref=f"draft-{uuid.uuid4()}",
                    self_ref=self_ref,
                    node_kind=node_kind,
                )
            elif binding.node_kind != node_kind:
                changed = True
                binding = DraftNodeBinding(
                    session_id=binding.session_id,
                    draft_ref=binding.draft_ref,
                    self_ref=binding.self_ref,
                    node_kind=node_kind,
                )
            next_bindings.append(binding)
        if len(next_bindings) != len(existing):
            changed = True
        if changed:
            await self._bindings.replace_for_session(session.id, next_bindings)
        return {binding.draft_ref: binding for binding in next_bindings}

    def _collect_bindable_refs(self, document: DoclingDocument) -> list[tuple[str, str]]:
        refs: list[tuple[str, str]] = []
        for item, _level in document.iterate_items(with_groups=True):
            self_ref = str(getattr(item, "self_ref", "") or "")
            if not self_ref:
                continue
            refs.append((self_ref, item.__class__.__name__))
        return refs

    def _resolve_self_ref(
        self,
        target_ref: str,
        bindings: dict[str, DraftNodeBinding],
    ) -> str:
        binding = bindings.get(target_ref)
        if binding is not None:
            if not binding.self_ref:
                raise DocumentEditConflictError(f"Draft target is no longer bound: {target_ref}")
            return binding.self_ref
        return target_ref

    def _reorder_item_after(
        self,
        document: DoclingDocument,
        target_ref: str,
        after_target_ref: str,
    ) -> DoclingDocument:
        return self._reorder_item_relative(
            document,
            target_ref,
            anchor_ref=after_target_ref,
            insert_after=True,
            action_name="move_item_after",
        )

    def _merge_items(
        self,
        document: DoclingDocument,
        target_ref: str,
        trailing_target_ref: str,
        *,
        separator: str,
    ) -> DoclingDocument:
        leading_item = self._find_item(document, target_ref)
        trailing_item = self._find_item(document, trailing_target_ref)
        if not isinstance(leading_item, TextItem) or not isinstance(trailing_item, TextItem):
            raise DocumentEditConflictError("merge_items currently supports text items only")

        document_dict = document.export_to_dict()
        nodes_by_ref = self._index_document_nodes(document_dict)
        leading_node = nodes_by_ref.get(target_ref)
        trailing_node = nodes_by_ref.get(trailing_target_ref)
        if leading_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {target_ref}")
        if trailing_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {trailing_target_ref}")

        leading_parent_ref = self._parent_ref(leading_node)
        trailing_parent_ref = self._parent_ref(trailing_node)
        if (
            not leading_parent_ref
            or not trailing_parent_ref
            or leading_parent_ref != trailing_parent_ref
        ):
            raise DocumentEditConflictError(
                "merge_items currently supports sibling text items within one parent"
            )

        parent_node = nodes_by_ref.get(leading_parent_ref)
        if parent_node is None:
            raise DocumentEditConflictError(
                f"Parent node not found for merge: {leading_parent_ref}"
            )
        children = parent_node.get("children")
        if not isinstance(children, list):
            raise DocumentEditConflictError(
                f"Parent does not expose mergeable children: {leading_parent_ref}"
            )

        leading_index = self._child_index(children, target_ref)
        trailing_index = self._child_index(children, trailing_target_ref)
        if leading_index + 1 != trailing_index:
            raise DocumentEditConflictError(
                "merge_items currently requires adjacent siblings with targetRef leading"
            )

        leading_text = str(leading_node.get("text") or "")
        trailing_text = str(trailing_node.get("text") or "")
        merged_text = f"{leading_text}{separator}{trailing_text}"
        leading_node["text"] = merged_text
        if "orig" in leading_node:
            leading_node["orig"] = merged_text

        children.pop(trailing_index)
        self._remove_text_item_from_document_dict(document_dict, trailing_target_ref)
        return DoclingDocument.model_validate(document_dict)

    def _delete_item(
        self,
        document: DoclingDocument,
        target_ref: str,
    ) -> DoclingDocument:
        target_item = self._find_item(document, target_ref)
        if not isinstance(target_item, TextItem):
            raise DocumentEditConflictError("delete_item currently supports text items only")

        document_dict = document.export_to_dict()
        nodes_by_ref = self._index_document_nodes(document_dict)
        target_node = nodes_by_ref.get(target_ref)
        if target_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {target_ref}")

        parent_ref = self._parent_ref(target_node)
        if not parent_ref:
            raise DocumentEditConflictError(f"Target node is missing a parent: {target_ref}")
        parent_node = nodes_by_ref.get(parent_ref)
        if parent_node is None:
            raise DocumentEditConflictError(f"Parent node not found for delete: {parent_ref}")
        children = parent_node.get("children")
        if not isinstance(children, list):
            raise DocumentEditConflictError(
                f"Parent does not expose deletable children: {parent_ref}"
            )

        child_index = self._child_index(children, target_ref)
        children.pop(child_index)
        self._remove_text_item_from_document_dict(document_dict, target_ref)
        return DoclingDocument.model_validate(document_dict)

    def _insert_item(
        self,
        document: DoclingDocument,
        target_ref: str,
        *,
        content: str,
    ) -> DoclingDocument:
        target_item = self._find_item(document, target_ref)
        if not isinstance(target_item, TextItem):
            raise DocumentEditConflictError("insert_item currently supports text items only")

        document_dict = document.export_to_dict()
        nodes_by_ref = self._index_document_nodes(document_dict)
        target_node = nodes_by_ref.get(target_ref)
        if target_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {target_ref}")

        parent_ref = self._parent_ref(target_node)
        if not parent_ref:
            raise DocumentEditConflictError(f"Target node is missing a parent: {target_ref}")
        parent_node = nodes_by_ref.get(parent_ref)
        if parent_node is None:
            raise DocumentEditConflictError(f"Parent node not found for insert: {parent_ref}")
        children = parent_node.get("children")
        if not isinstance(children, list):
            raise DocumentEditConflictError(
                f"Parent does not expose insertable children: {parent_ref}"
            )

        next_self_ref = self._next_text_self_ref(document_dict)
        inserted_node = copy.deepcopy(target_node)
        inserted_node["self_ref"] = next_self_ref
        inserted_node["text"] = content
        if "orig" in inserted_node:
            inserted_node["orig"] = content
        inserted_node["parent"] = {"$ref": parent_ref}

        texts = document_dict.get("texts")
        if not isinstance(texts, list):
            raise DocumentEditConflictError("Document does not expose a texts array")
        texts.append(inserted_node)

        child_index = self._child_index(children, target_ref)
        children.insert(child_index + 1, {"$ref": next_self_ref})
        return DoclingDocument.model_validate(document_dict)

    def _reorder_item_before(
        self,
        document: DoclingDocument,
        target_ref: str,
        before_target_ref: str,
    ) -> DoclingDocument:
        return self._reorder_item_relative(
            document,
            target_ref,
            anchor_ref=before_target_ref,
            insert_after=False,
            action_name="move_item_before",
        )

    def _split_item(
        self,
        document: DoclingDocument,
        target_ref: str,
        *,
        split_index: int,
    ) -> DoclingDocument:
        target_item = self._find_item(document, target_ref)
        if not isinstance(target_item, TextItem):
            raise DocumentEditConflictError("split_item currently supports text items only")

        document_dict = document.export_to_dict()
        nodes_by_ref = self._index_document_nodes(document_dict)
        target_node = nodes_by_ref.get(target_ref)
        if target_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {target_ref}")

        target_text = str(target_node.get("text") or "")
        if split_index >= len(target_text):
            raise DocumentEditConflictError(
                "split_item payload.splitIndex must be smaller than the text length"
            )

        parent_ref = self._parent_ref(target_node)
        if not parent_ref:
            raise DocumentEditConflictError(f"Target node is missing a parent: {target_ref}")
        parent_node = nodes_by_ref.get(parent_ref)
        if parent_node is None:
            raise DocumentEditConflictError(f"Parent node not found for split: {parent_ref}")
        children = parent_node.get("children")
        if not isinstance(children, list):
            raise DocumentEditConflictError(
                f"Parent does not expose splittable children: {parent_ref}"
            )

        child_index = self._child_index(children, target_ref)
        leading_text = target_text[:split_index]
        trailing_text = target_text[split_index:]
        next_self_ref = self._next_text_self_ref(document_dict)

        target_node["text"] = leading_text
        if "orig" in target_node:
            target_node["orig"] = leading_text

        split_node = copy.deepcopy(target_node)
        split_node["self_ref"] = next_self_ref
        split_node["text"] = trailing_text
        if "orig" in split_node:
            split_node["orig"] = trailing_text

        texts = document_dict.get("texts")
        if not isinstance(texts, list):
            raise DocumentEditConflictError("Document does not expose a texts array")
        texts.append(split_node)
        children.insert(child_index + 1, {"$ref": next_self_ref})
        return DoclingDocument.model_validate(document_dict)

    def _reorder_item_relative(
        self,
        document: DoclingDocument,
        target_ref: str,
        *,
        anchor_ref: str,
        insert_after: bool,
        action_name: str,
    ) -> DoclingDocument:
        document_dict = document.export_to_dict()
        nodes_by_ref = self._index_document_nodes(document_dict)
        target_node = nodes_by_ref.get(target_ref)
        anchor_node = nodes_by_ref.get(anchor_ref)
        if target_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {target_ref}")
        if anchor_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {anchor_ref}")

        target_parent_ref = self._parent_ref(target_node)
        anchor_parent_ref = self._parent_ref(anchor_node)
        if not target_parent_ref or not anchor_parent_ref or target_parent_ref != anchor_parent_ref:
            raise DocumentEditConflictError(
                f"{action_name} currently supports sibling reordering within one parent"
            )

        parent_node = nodes_by_ref.get(target_parent_ref)
        if parent_node is None:
            raise DocumentEditConflictError(
                f"Parent node not found for reorder: {target_parent_ref}"
            )
        children = parent_node.get("children")
        if not isinstance(children, list):
            raise DocumentEditConflictError(
                f"Parent does not expose reorderable children: {target_parent_ref}"
            )

        target_index = self._child_index(children, target_ref)
        anchor_index = self._child_index(children, anchor_ref)
        target_child = children.pop(target_index)
        if target_index < anchor_index:
            anchor_index -= 1
        insert_index = anchor_index + 1 if insert_after else anchor_index
        children.insert(insert_index, target_child)
        return DoclingDocument.model_validate(document_dict)

    def _reparent_item(
        self,
        document: DoclingDocument,
        target_ref: str,
        parent_target_ref: str,
        *,
        index: Any,
    ) -> DoclingDocument:
        document_dict = document.export_to_dict()
        nodes_by_ref = self._index_document_nodes(document_dict)
        target_node = nodes_by_ref.get(target_ref)
        parent_node = nodes_by_ref.get(parent_target_ref)
        if target_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {target_ref}")
        if parent_node is None:
            raise DocumentEditNotFoundError(f"Document item not found: {parent_target_ref}")
        if self._is_descendant_ref(nodes_by_ref, parent_target_ref, target_ref):
            raise DocumentEditConflictError(
                "reparent_item cannot move a node under one of its descendants"
            )

        current_parent_ref = self._parent_ref(target_node)
        if not current_parent_ref:
            raise DocumentEditConflictError(f"Target node is missing a parent: {target_ref}")
        current_parent_node = nodes_by_ref.get(current_parent_ref)
        if current_parent_node is None:
            raise DocumentEditConflictError(
                f"Parent node not found for reparent: {current_parent_ref}"
            )

        current_children = current_parent_node.get("children")
        next_children = parent_node.get("children")
        if not isinstance(current_children, list):
            raise DocumentEditConflictError(
                f"Parent does not expose reparentable children: {current_parent_ref}"
            )
        if not isinstance(next_children, list):
            raise DocumentEditConflictError(
                f"Target parent does not expose children: {parent_target_ref}"
            )

        current_index = self._child_index(current_children, target_ref)
        target_child = current_children.pop(current_index)
        if (
            current_parent_ref == parent_target_ref
            and isinstance(index, int)
            and current_index < index
        ):
            index -= 1

        insert_index = len(next_children) if index is None else min(index, len(next_children))
        next_children.insert(insert_index, target_child)
        target_node["parent"] = {"$ref": parent_target_ref}
        return DoclingDocument.model_validate(document_dict)

    def _remove_text_item_from_document_dict(
        self,
        document_dict: dict[str, Any],
        target_ref: str,
    ) -> None:
        texts = document_dict.get("texts")
        if not isinstance(texts, list):
            raise DocumentEditConflictError("Document does not expose a texts array")
        for index, item in enumerate(texts):
            if isinstance(item, dict) and item.get("self_ref") == target_ref:
                texts.pop(index)
                return
        raise DocumentEditNotFoundError(f"Document item not found: {target_ref}")

    def _next_text_self_ref(self, document_dict: dict[str, Any]) -> str:
        texts = document_dict.get("texts")
        if not isinstance(texts, list):
            raise DocumentEditConflictError("Document does not expose a texts array")
        next_index = -1
        for item in texts:
            if not isinstance(item, dict):
                continue
            self_ref = item.get("self_ref")
            if not isinstance(self_ref, str) or not self_ref.startswith("#/texts/"):
                continue
            try:
                next_index = max(next_index, int(self_ref.removeprefix("#/texts/")))
            except ValueError:
                continue
        return f"#/texts/{next_index + 1}"

    def _index_document_nodes(self, value: Any) -> dict[str, dict[str, Any]]:
        nodes: dict[str, dict[str, Any]] = {}

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                self_ref = node.get("self_ref")
                if isinstance(self_ref, str) and self_ref:
                    nodes[self_ref] = node
                for child in node.values():
                    visit(child)
                return
            if isinstance(node, list):
                for child in node:
                    visit(child)

        visit(value)
        return nodes

    def _parent_ref(self, node: dict[str, Any]) -> str:
        parent = node.get("parent")
        if isinstance(parent, dict):
            parent_ref = parent.get("$ref")
            if isinstance(parent_ref, str):
                return parent_ref
        return ""

    def _child_index(self, children: list[Any], target_ref: str) -> int:
        for index, child in enumerate(children):
            if isinstance(child, dict) and child.get("$ref") == target_ref:
                return index
        raise DocumentEditConflictError(f"Child ref not found in parent ordering: {target_ref}")

    def _is_descendant_ref(
        self,
        nodes_by_ref: dict[str, dict[str, Any]],
        ancestor_ref: str,
        target_ref: str,
    ) -> bool:
        current_ref = ancestor_ref
        while current_ref:
            if current_ref == target_ref:
                return True
            current_node = nodes_by_ref.get(current_ref)
            if current_node is None:
                return False
            current_ref = self._parent_ref(current_node)
        return False

    def _edit_to_dict(self, edit: DocumentEdit) -> dict[str, Any]:
        return {
            "id": edit.id,
            "analysisId": edit.analysis_id,
            "action": edit.action.value,
            "targetRef": edit.target_ref,
            "payload": edit.payload,
            "actor": edit.actor,
            "at": str(edit.at),
            "status": edit.status.value,
        }


_TYPE_TO_LABEL: dict[str, DocItemLabel] = {
    "text": DocItemLabel.TEXT,
    "title": DocItemLabel.TITLE,
    "section_header": DocItemLabel.SECTION_HEADER,
    "list": DocItemLabel.LIST_ITEM,
    "formula": DocItemLabel.FORMULA,
    "code": DocItemLabel.CODE,
    "picture": DocItemLabel.PICTURE,
    "table": DocItemLabel.TABLE,
    "caption": DocItemLabel.CAPTION,
    "floating": DocItemLabel.FOOTNOTE,
}


def _allowed_labels_for_item(item: DocItem) -> set[DocItemLabel]:
    class_name = item.__class__.__name__
    if class_name in {
        "TextItem",
        "TitleItem",
        "SectionHeaderItem",
        "ListItem",
        "CodeItem",
        "FormulaItem",
    }:
        return {
            DocItemLabel.TEXT,
            DocItemLabel.TITLE,
            DocItemLabel.SECTION_HEADER,
            DocItemLabel.LIST_ITEM,
            DocItemLabel.CODE,
            DocItemLabel.FORMULA,
            DocItemLabel.CAPTION,
        }
    if class_name == "PictureItem":
        return {DocItemLabel.PICTURE, DocItemLabel.CHART}
    if class_name == "TableItem":
        return {DocItemLabel.TABLE, DocItemLabel.DOCUMENT_INDEX}
    return {getattr(item, "label", DocItemLabel.TEXT)}


def _label_to_type_name(label: DocItemLabel) -> str:
    if label is DocItemLabel.LIST_ITEM:
        return "list"
    if label is DocItemLabel.CHART:
        return "picture"
    if label is DocItemLabel.DOCUMENT_INDEX:
        return "table"
    if label is DocItemLabel.FOOTNOTE:
        return "floating"
    return str(label.value)


def _build_text_family_item(item: TextItem, next_label: DocItemLabel) -> TextItem | None:
    payload = item.model_dump(mode="python")
    payload["label"] = next_label
    if next_label is DocItemLabel.TITLE:
        payload.pop("level", None)
        return TitleItem.model_validate(payload)
    if next_label is DocItemLabel.SECTION_HEADER:
        payload["level"] = getattr(item, "level", 1) or 1
        return SectionHeaderItem.model_validate(payload)
    if next_label in {
        DocItemLabel.CAPTION,
        DocItemLabel.CHECKBOX_SELECTED,
        DocItemLabel.CHECKBOX_UNSELECTED,
        DocItemLabel.FOOTNOTE,
        DocItemLabel.PAGE_FOOTER,
        DocItemLabel.PAGE_HEADER,
        DocItemLabel.PARAGRAPH,
        DocItemLabel.REFERENCE,
        DocItemLabel.TEXT,
        DocItemLabel.EMPTY_VALUE,
        DocItemLabel.FIELD_KEY,
        DocItemLabel.FIELD_HINT,
        DocItemLabel.MARKER,
        DocItemLabel.HANDWRITTEN_TEXT,
    }:
        payload.pop("level", None)
        return TextItem.model_validate(payload)
    return None


def _replace_text_item_in_document(
    document: DoclingDocument, old_item: TextItem, new_item: TextItem
) -> None:
    for index, item in enumerate(document.texts):
        if getattr(item, "self_ref", "") == old_item.self_ref:
            # Mutate the canonical texts array in place so the self_ref and tree references stay stable.
            document.texts[index] = new_item
            return
    raise DocumentEditConflictError(
        f"Unsupported text item ref for type replacement: {old_item.self_ref}"
    )
