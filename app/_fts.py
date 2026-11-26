"""Local full-text paper index on SQLite FTS5, with a Pinecone-shaped interface.

One SQLite file per index. `papers` keeps each paper's metadata dict as JSON
(the exact dict the app used to get from Pinecone); `papers_fts` indexes its
title, abstract and author names with the Porter stemmer. Ranking is BM25
(title weighted 3x),
and scores are normalized so the best match is 1.0.

Shared by the web app (read) and the ingestion job of
reviewer-recommendation-system (write, via `upsert`).
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    metadata TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts
    USING fts5(title, abstract, authors, tokenize = 'porter unicode61');
"""

TITLE_WEIGHT = 3.0
ABSTRACT_WEIGHT = 1.0
AUTHORS_WEIGHT = 1.0


def connect(path: str | Path) -> sqlite3.Connection:
    """Open (and create if needed) an index file."""
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    return conn


def match_expression(text: str) -> str | None:
    """Turn free text into a safe FTS5 query: every word quoted, OR-ed.

    Returns None when the text has no word, so FTS syntax in user input
    (quotes, AND, NEAR, *, parentheses) can never reach MATCH unescaped.
    """
    words = re.findall(r"\w+", text.lower())
    if not words:
        return None
    unique = list(dict.fromkeys(words))
    return " OR ".join(f'"{w}"' for w in unique)


def _text(metadata: dict, key: str) -> str:
    value = metadata.get(key) or ""
    return value if isinstance(value, str) else " ".join(map(str, value))


def upsert(path: str | Path, records: Iterable[dict]) -> int:
    """Insert or replace records {"id": str, "metadata": dict}; returns the number of new ids."""
    conn = connect(path)
    added = 0
    with conn:
        for record in records:
            metadata = record["metadata"]
            row = conn.execute("SELECT rowid FROM papers WHERE id = ?", (record["id"],)).fetchone()
            if row:
                conn.execute("DELETE FROM papers_fts WHERE rowid = ?", (row[0],))
                conn.execute(
                    "UPDATE papers SET metadata = ? WHERE rowid = ?",
                    (json.dumps(metadata), row[0]),
                )
                rowid = row[0]
            else:
                rowid = conn.execute(
                    "INSERT INTO papers (id, metadata) VALUES (?, ?)",
                    (record["id"], json.dumps(metadata)),
                ).lastrowid
                added += 1
            conn.execute(
                "INSERT INTO papers_fts (rowid, title, abstract, authors) VALUES (?, ?, ?, ?)",
                (rowid, _text(metadata, "title"), _text(metadata, "abstract"), _text(metadata, "authors")),
            )
    conn.close()
    return added


class LocalIndex:
    """Read side, mimicking the subset of pinecone.Index the app uses."""

    def __init__(self, path: str | Path):
        if not Path(path).exists():
            raise FileNotFoundError(f"search index not found: {path}")
        self.path = str(path)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)

    def query(self, text: str, top_k: int = 100, include_metadata: bool = True) -> dict:
        expression = match_expression(text)
        if expression is None:
            return {"matches": []}
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT p.id, p.metadata, bm25(papers_fts, ?, ?, ?) AS rank
                   FROM papers_fts JOIN papers p ON p.rowid = papers_fts.rowid
                   WHERE papers_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (TITLE_WEIGHT, ABSTRACT_WEIGHT, AUTHORS_WEIGHT, expression, top_k),
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            return {"matches": []}
        best = rows[0][2]  # bm25 is negative; the best match is the most negative
        matches = []
        for paper_id, metadata, rank in rows:
            score = rank / best if best < 0 else 1.0
            match = {"id": paper_id, "score": score}
            if include_metadata:
                match["metadata"] = json.loads(metadata)
            matches.append(match)
        return {"matches": matches}

    def fetch(self, ids: list[str]) -> dict:
        conn = self._conn()
        try:
            marks = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT id, metadata FROM papers WHERE id IN ({marks})", ids
            ).fetchall()
        finally:
            conn.close()
        return {"vectors": {i: {"id": i, "metadata": json.loads(m)} for i, m in rows}}

    def count(self) -> int:
        conn = self._conn()
        try:
            return conn.execute("SELECT count(*) FROM papers").fetchone()[0]
        finally:
            conn.close()
