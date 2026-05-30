"""Draft node binding repository — stable session-local document edit identities."""

from __future__ import annotations

from domain.models import DraftNodeBinding
from persistence.database import get_connection


def _row_to_binding(row) -> DraftNodeBinding:
    return DraftNodeBinding(
        session_id=row["session_id"],
        draft_ref=row["draft_ref"],
        self_ref=row["self_ref"],
        node_kind=row["node_kind"],
    )


class SqliteDraftNodeBindingRepository:
    async def find_by_session(self, session_id: str) -> list[DraftNodeBinding]:
        async with get_connection() as db:
            cursor = await db.execute(
                """SELECT session_id, draft_ref, self_ref, node_kind
                   FROM document_edit_draft_bindings
                   WHERE session_id = ?
                   ORDER BY draft_ref""",
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [_row_to_binding(row) for row in rows]

    async def replace_for_session(self, session_id: str, bindings: list[DraftNodeBinding]) -> None:
        async with get_connection() as db:
            await db.execute(
                "DELETE FROM document_edit_draft_bindings WHERE session_id = ?",
                (session_id,),
            )
            if bindings:
                await db.executemany(
                    """INSERT INTO document_edit_draft_bindings
                       (session_id, draft_ref, self_ref, node_kind)
                       VALUES (?, ?, ?, ?)""",
                    [
                        (binding.session_id, binding.draft_ref, binding.self_ref, binding.node_kind)
                        for binding in bindings
                    ],
                )
            await db.commit()
