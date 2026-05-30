"""Document edit session repository — active draft-session metadata."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.models import DocumentEditSession
from persistence.database import get_connection


def _parse_iso(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _row_to_session(row) -> DocumentEditSession:
    now = datetime.now(UTC)
    return DocumentEditSession(
        id=row["id"],
        document_id=row["document_id"],
        base_analysis_id=row["base_analysis_id"],
        draft_version=int(row["draft_version"]),
        actor=row["actor"],
        created_at=_parse_iso(row["created_at"]) or now,
        updated_at=_parse_iso(row["updated_at"]) or now,
    )


class SqliteDocumentEditSessionRepository:
    async def insert(self, session: DocumentEditSession) -> None:
        async with get_connection() as db:
            await db.execute(
                """INSERT INTO document_edit_sessions
                   (id, document_id, base_analysis_id, draft_version, actor, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.id,
                    session.document_id,
                    session.base_analysis_id,
                    session.draft_version,
                    session.actor,
                    str(session.created_at),
                    str(session.updated_at),
                ),
            )
            await db.commit()

    async def find_by_document(self, document_id: str) -> DocumentEditSession | None:
        async with get_connection() as db:
            cursor = await db.execute(
                "SELECT * FROM document_edit_sessions WHERE document_id = ?",
                (document_id,),
            )
            row = await cursor.fetchone()
            return _row_to_session(row) if row else None

    async def update(self, session: DocumentEditSession) -> None:
        async with get_connection() as db:
            await db.execute(
                """UPDATE document_edit_sessions
                   SET document_id = ?,
                       base_analysis_id = ?,
                       draft_version = ?,
                       actor = ?,
                       created_at = ?,
                       updated_at = ?
                   WHERE id = ?""",
                (
                    session.document_id,
                    session.base_analysis_id,
                    session.draft_version,
                    session.actor,
                    str(session.created_at),
                    str(session.updated_at),
                    session.id,
                ),
            )
            await db.commit()

    async def delete(self, session_id: str) -> bool:
        async with get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM document_edit_sessions WHERE id = ?",
                (session_id,),
            )
            await db.commit()
            return cursor.rowcount > 0
