"""Store for good/bad fit examples used in AI relevance scoring."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Example:
    """Good-fit or bad-fit example for relevance scoring."""

    id: int
    profile_id: str
    url: str
    label: str  # "good" | "bad"
    title: str | None
    summary: str | None
    raw_text: str | None
    created_at: datetime


class ExampleStore:
    """SQLite store for profile examples."""

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

    def add(
        self,
        profile_id: str,
        url: str,
        label: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        raw_text: str | None = None,
    ) -> Example:
        """Add an example. Label must be 'good' or 'bad'."""
        if label not in ("good", "bad"):
            raise ValueError("label must be 'good' or 'bad'")
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO examples (profile_id, url, label, title, summary, raw_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (profile_id, url, label, title or "", summary or "", raw_text or "", now),
            )
            conn.commit()
            row_id = cursor.lastrowid or 0
        return Example(
            id=row_id,
            profile_id=profile_id,
            url=url,
            label=label,
            title=title,
            summary=summary,
            raw_text=raw_text,
            created_at=datetime.now(timezone.utc),
        )

    def list_by_profile(self, profile_id: str) -> list[Example]:
        """List all examples for a profile."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM examples WHERE profile_id = ? ORDER BY created_at DESC",
                (profile_id,),
            ).fetchall()
        return [self._row_to_example(r) for r in rows]

    def get_texts_for_profile(self, profile_id: str) -> tuple[list[str], list[str]]:
        """Return (good_texts, bad_texts) for similarity scoring. Uses title+summary+raw_text."""
        good: list[str] = []
        bad: list[str] = []
        for ex in self.list_by_profile(profile_id):
            text = " ".join(filter(None, [ex.title, ex.summary, ex.raw_text])).strip()
            if not text:
                continue
            if ex.label == "good":
                good.append(text)
            else:
                bad.append(text)
        return good, bad

    def _row_to_example(self, row: sqlite3.Row) -> Example:
        return Example(
            id=row["id"],
            profile_id=row["profile_id"],
            url=row["url"],
            label=row["label"],
            title=row["title"] or None,
            summary=row["summary"] or None,
            raw_text=row["raw_text"] or None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
