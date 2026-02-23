"""SQLite-backed opportunity store with deduplication and change tracking."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rfp_finder.models.opportunity import NormalizedOpportunity


class RunRecord:
    """Record of an ingest run."""

    def __init__(
        self,
        id: int,
        source: str,
        started_at: datetime,
        finished_at: Optional[datetime],
        status: str,
        items_fetched: int,
        items_new: int,
        items_amended: int,
    ):
        self.id = id
        self.source = source
        self.started_at = started_at
        self.finished_at = finished_at
        self.status = status
        self.items_fetched = items_fetched
        self.items_new = items_new
        self.items_amended = items_amended


class OpportunityStore:
    """
    SQLite store for normalized opportunities with deduplication and change detection.
    Uses (source, source_id) for dedupe; content_hash for amendment detection.
    """

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

    def _resolve_status(self, opp: NormalizedOpportunity) -> str:
        """Resolve final status including closed (past closing date)."""
        if opp.status in ("cancelled", "expired", "closed"):
            return opp.status
        now = datetime.now(timezone.utc)
        closing = opp.closing_at
        if closing:
            closing_utc = closing if closing.tzinfo else closing.replace(tzinfo=timezone.utc)
            if closing_utc < now:
                return "closed"
        return opp.status if opp.status in ("open", "amended", "unknown") else "open"

    def _serialize_opp(self, opp: NormalizedOpportunity) -> str:
        """Serialize opportunity to JSON for storage."""
        data = opp.model_dump(mode="json")
        return json.dumps(data, default=str)

    def _deserialize_opp(self, row: sqlite3.Row) -> NormalizedOpportunity:
        """Deserialize stored row to NormalizedOpportunity."""
        data = json.loads(row["data"])
        return NormalizedOpportunity.model_validate(data)

    def upsert(self, opp: NormalizedOpportunity) -> tuple[bool, bool]:
        """
        Insert or update opportunity. Returns (was_new, was_amended).
        """
        now = datetime.now(timezone.utc).isoformat()
        status = self._resolve_status(opp)
        opp_copy = opp.model_copy(update={"status": status})
        data_str = self._serialize_opp(opp_copy)
        content_hash = opp.content_hash or ""
        was_new = False
        was_amended = False

        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT id, content_hash FROM opportunities WHERE source = ? AND source_id = ?",
                (opp.source, opp.source_id),
            )
            existing = cursor.fetchone()

            if existing:
                prior_hash = existing["content_hash"]
                if prior_hash != content_hash:
                    was_amended = True
                    conn.execute(
                        """
                        UPDATE opportunities SET
                            content_hash = ?, status = ?, prior_content_hash = ?,
                            data = ?, last_seen_at = ?
                        WHERE id = ?
                        """,
                        (content_hash, status, prior_hash, data_str, now, opp.id),
                    )
                else:
                    # Same source content: still update data so normalization improvements persist
                    conn.execute(
                        "UPDATE opportunities SET data = ?, last_seen_at = ? WHERE id = ?",
                        (data_str, now, opp.id),
                    )
            else:
                was_new = True
                conn.execute(
                    """
                    INSERT INTO opportunities (id, source, source_id, content_hash, status, data, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (opp.id, opp.source, opp.source_id, content_hash, status, data_str, now, now),
                )
            conn.commit()

        return (was_new, was_amended)

    def get_all(self) -> list[NormalizedOpportunity]:
        """Return all opportunities."""
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM opportunities ORDER BY last_seen_at DESC").fetchall()
        return [self._deserialize_opp(r) for r in rows]

    def get_by_status(self, status: str) -> list[NormalizedOpportunity]:
        """Return opportunities with given status."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM opportunities WHERE status = ? ORDER BY last_seen_at DESC",
                (status,),
            ).fetchall()
        return [self._deserialize_opp(r) for r in rows]

    def get_modified_since(self, since: datetime) -> list[NormalizedOpportunity]:
        """Return opportunities modified (last_seen_at) since given datetime."""
        since_str = since.isoformat()
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM opportunities WHERE last_seen_at >= ? ORDER BY last_seen_at DESC",
                (since_str,),
            ).fetchall()
        return [self._deserialize_opp(r) for r in rows]

    def get(self, opp_id: str) -> Optional[NormalizedOpportunity]:
        """Get single opportunity by id."""
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
        return self._deserialize_opp(row) if row else None

    def start_run(self, source: str) -> RunRecord:
        """Record start of an ingest run. Returns RunRecord with id."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (source, started_at, status, items_fetched, items_new, items_amended) VALUES (?, ?, 'running', 0, 0, 0)",
                (source, now),
            )
            conn.commit()
            run_id = cursor.lastrowid
        return RunRecord(
            id=run_id or 0,
            source=source,
            started_at=datetime.fromisoformat(now),
            finished_at=None,
            status="running",
            items_fetched=0,
            items_new=0,
            items_amended=0,
        )

    def finish_run(
        self,
        run_id: int,
        items_fetched: int,
        items_new: int,
        items_amended: int,
        status: str = "completed",
    ) -> None:
        """Record completion of an ingest run."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE runs SET finished_at = ?, status = ?, items_fetched = ?, items_new = ?, items_amended = ?
                WHERE id = ?
                """,
                (now, status, items_fetched, items_new, items_amended, run_id),
            )
            conn.commit()
