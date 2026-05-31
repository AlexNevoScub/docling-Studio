"""API tests for document edit draft responses."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_service():
    svc = MagicMock()
    original = getattr(app.state, "document_edit_service", None)
    app.state.document_edit_service = svc
    yield svc
    app.state.document_edit_service = original


def _pending_command() -> dict:
    return {
        "id": "cmd-1",
        "analysisId": "a-1",
        "action": "update_page_element",
        "targetRef": "#/texts/12",
        "payload": {"content": "Updated content"},
        "actor": "user",
        "at": "2026-05-30T12:00:00+00:00",
        "status": "pending",
    }


def _tree(label: str = "Draft title") -> list[dict]:
    return [
        {
            "ref": "#/texts/12",
            "draftRef": "draft-1",
            "type": "title",
            "label": label,
            "children": [],
        }
    ]


def _pages() -> list[dict]:
    return [
        {
            "page_number": 1,
            "width": 600,
            "height": 800,
            "elements": [
                {
                    "self_ref": "#/texts/12",
                    "draftRef": "draft-1",
                    "type": "title",
                    "content": "Draft title",
                    "bbox": [0, 0, 10, 10],
                }
            ],
        }
    ]


def _page_patches() -> list[dict]:
    return [{"op": "upsert", "pageNumber": 1, "page": _pages()[0]}]


def _tree_patches(label: str = "Draft title") -> list[dict]:
    return [{"op": "replace", "path": [], "nodes": _tree(label)}]


def _ref_remaps() -> list[dict]:
    return [{"draftRef": "draft-1", "selfRef": "#/texts/12", "nodeKind": "TextItem"}]


class TestDocumentEditSessionRoutes:
    def test_get_session_returns_tree(self, client, mock_service):
        mock_service.get_session = AsyncMock(
            return_value={
                "sessionId": "sess-1",
                "analysisId": "a-1",
                "baseAnalysisId": "a-1",
                "draftVersion": 0,
                "pages": _pages(),
                "tree": _tree(),
                "pagePatches": [],
                "treePatches": [],
                "refRemaps": _ref_remaps(),
                "pendingCommands": [_pending_command()],
            }
        )

        resp = client.get("/api/documents/d-1/edits/session")

        assert resp.status_code == 200
        body = resp.json()
        assert body["sessionId"] == "sess-1"
        assert body["tree"] == _tree()
        assert body["refRemaps"] == _ref_remaps()
        assert body["pendingCommands"][0]["action"] == "update_page_element"

    def test_apply_commands_returns_tree(self, client, mock_service):
        mock_service.apply_commands = AsyncMock(
            return_value={
                "sessionId": "sess-1",
                "analysisId": "a-1",
                "baseAnalysisId": "a-1",
                "draftVersion": 1,
                "pages": _pages(),
                "tree": _tree("Updated heading"),
                "pagePatches": _page_patches(),
                "treePatches": _tree_patches("Updated heading"),
                "refRemaps": _ref_remaps(),
                "pendingCommands": [_pending_command()],
            }
        )

        resp = client.post(
            "/api/documents/d-1/edits/commands",
            json={
                "sessionId": "sess-1",
                "draftVersion": 0,
                "commands": [
                    {
                        "action": "update_page_element",
                        "targetRef": "#/texts/12",
                        "payload": {"content": "Updated content"},
                    }
                ],
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["draftVersion"] == 1
        assert body["tree"] == _tree("Updated heading")
        assert body["pagePatches"] == _page_patches()
        assert body["treePatches"] == _tree_patches("Updated heading")
        mock_service.apply_commands.assert_awaited_once()

    def test_commit_returns_tree(self, client, mock_service):
        mock_service.commit = AsyncMock(
            return_value={
                "committed": False,
                "consistent": False,
                "differences": [{"ref": "#/texts/12", "field": "content"}],
                "pages": _pages(),
                "tree": _tree("Backend truth"),
                "pagePatches": _page_patches(),
                "treePatches": _tree_patches("Backend truth"),
                "refRemaps": _ref_remaps(),
            }
        )

        resp = client.post(
            "/api/documents/d-1/edits/commit",
            json={"sessionId": "sess-1", "draftVersion": 1},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["committed"] is False
        assert body["tree"] == _tree("Backend truth")
        assert body["treePatches"] == _tree_patches("Backend truth")
