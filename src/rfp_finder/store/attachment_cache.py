"""Attachment cache store for Phase 5 document handling."""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CachedAttachment:
    """Cached attachment with extraction metadata."""

    url: str
    local_path: str
    fetched_at: datetime
    extraction_status: str  # pending | success | failed
    extracted_text: str | None
    text_length: int | None
    page_count: int | None
    error_message: str | None


class AttachmentCacheStore:
    """SQLite store for attachment cache metadata."""

    def __init__(self, db_path: str | Path = "rfp_finder.db"):
        self._db_path = Path(db_path)
        self._ensure_schema()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        schema_path = Path(__file__).parent / "schema.sql"
        with self._connection() as conn:
            conn.executescript(schema_path.read_text())

    @staticmethod
    def _url_to_filename(url: str) -> str:
        """Derive cache filename from URL."""
        h = hashlib.sha256(url.encode()).hexdigest()[:16]
        if url.lower().endswith(".pdf"):
            return f"{h}.pdf"
        return f"{h}.bin"

    def get_cached(self, url: str) -> CachedAttachment | None:
        """Get cached attachment by URL if exists."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM attachment_cache WHERE url = ?", (url,)
            ).fetchone()
        if not row:
            return None
        return CachedAttachment(
            url=row["url"],
            local_path=row["local_path"],
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
            extraction_status=row["extraction_status"],
            extracted_text=row["extracted_text"],
            text_length=row["text_length"],
            page_count=row["page_count"],
            error_message=row["error_message"],
        )

    def upsert(
        self,
        url: str,
        local_path: str,
        *,
        extraction_status: str = "pending",
        extracted_text: str | None = None,
        text_length: int | None = None,
        page_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Insert or update cache entry."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO attachment_cache
                (url, local_path, fetched_at, extraction_status, extracted_text, text_length, page_count, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    local_path = excluded.local_path,
                    fetched_at = excluded.fetched_at,
                    extraction_status = excluded.extraction_status,
                    extracted_text = excluded.extracted_text,
                    text_length = excluded.text_length,
                    page_count = excluded.page_count,
                    error_message = excluded.error_message
                """,
                (
                    url,
                    local_path,
                    now,
                    extraction_status,
                    extracted_text or "",
                    text_length,
                    page_count,
                    error_message or "",
                ),
            )
            conn.commit()

    def update_extraction(
        self,
        url: str,
        *,
        status: str,
        extracted_text: str | None = None,
        text_length: int | None = None,
        page_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update extraction result for cached attachment."""
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE attachment_cache SET
                    extraction_status = ?,
                    extracted_text = COALESCE(?, extracted_text),
                    text_length = COALESCE(?, text_length),
                    page_count = COALESCE(?, page_count),
                    error_message = COALESCE(?, error_message)
                WHERE url = ?
                """,
                (status, extracted_text, text_length, page_count, error_message, url),
            )
            conn.commit()
