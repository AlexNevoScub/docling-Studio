"""Document edit service — optimistic document_json mutations with replay."""

from __future__ import annotations

import json
import uuid
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
        self._apply_edits(document, edits, bindings)
        return {
            "sessionId": session.id,
            "analysisId": analysis.id,
            "baseAnalysisId": session.base_analysis_id,
            "draftVersion": session.draft_version,
            "pages": self._render_pages(document, bindings),
            "tree": self._render_tree(document, bindings),
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
        bindings = await self._ensure_bindings(session, self._load_doc(analysis.document_json))
        preview_document = self._preview_document(analysis, [*pending, *new_edits], bindings)
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
            "pages": self._render_pages(preview_document, bindings),
            "tree": self._render_tree(preview_document, bindings),
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
        self._apply_edits(document, pending, bindings)
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
        self._apply_edits(document, edits, bindings)
        return document

    def _load_doc(self, raw_document_json: str | None) -> DoclingDocument:
        if not raw_document_json:
            raise DocumentEditNotFoundError("Missing document_json")
        return DoclingDocument.model_validate(json.loads(raw_document_json))

    def _apply_edits(
        self,
        document: DoclingDocument,
        edits: list[DocumentEdit],
        bindings: dict[str, DraftNodeBinding],
    ) -> None:
        for edit in edits:
            if edit.action is DocumentEditAction.UPDATE_PAGE_ELEMENT:
                self._apply_update_page_element(document, edit, bindings)

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
        if action is not DocumentEditAction.UPDATE_PAGE_ELEMENT:
            raise DocumentEditConflictError(f"Unsupported document edit action: {action.value}")
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
                raise DocumentEditConflictError("payload.bbox must contain only numbers") from exc

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
    path = old_item.self_ref.split("/")
    if len(path) != 3 or path[1] != "texts":
        raise DocumentEditConflictError(
            f"Unsupported text item ref for type replacement: {old_item.self_ref}"
        )
    try:
        index = int(path[2])
    except ValueError as exc:
        raise DocumentEditConflictError(
            f"Unsupported text item ref for type replacement: {old_item.self_ref}"
        ) from exc
    # Mutate the canonical texts array in place so the self_ref and tree references stay stable.
    document.texts[index] = new_item
