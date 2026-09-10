"""SQLite + sqlite-vec storage backend. See docs/architecture.md."""

import sqlite3
from datetime import datetime, timezone

import sqlite_vec
from sqlite_vec import serialize_float32


def open_db(path: str) -> sqlite3.Connection:
    """Open a SQLite database and load the sqlite-vec extension."""
    db = sqlite3.connect(path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    return db


def create_tables(
    db: sqlite3.Connection,
    model_name: str,
    model_dim: int,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> None:
    """Create chunks, chunks_vec, sources, and meta tables if they don't exist."""
    if not isinstance(model_dim, int) or model_dim <= 0:
        raise ValueError(f"model_dim must be a positive integer, got {model_dim}")
    db.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec "
        f"USING vec0(embedding float[{model_dim}] distance_metric=cosine)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        "  id TEXT PRIMARY KEY,"
        "  source_file TEXT NOT NULL,"
        "  chunk_index INTEGER NOT NULL,"
        "  content TEXT NOT NULL,"
        "  metadata TEXT DEFAULT '{}'"
        ")"
    )
    db.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
        "USING fts5(content, source_file, content=chunks, content_rowid=rowid)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS sources ("
        "  source_file TEXT PRIMARY KEY,"
        "  title TEXT,"
        "  author TEXT,"
        "  url TEXT,"
        "  date TEXT,"
        "  license TEXT,"
        "  level TEXT,"
        "  extra TEXT DEFAULT '{}'"
        ")"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS meta ("
        "  key TEXT PRIMARY KEY,"
        "  value TEXT NOT NULL"
        ")"
    )
    db.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
        ("model_name", model_name),
    )
    db.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
        ("model_dim", str(model_dim)),
    )
    db.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
        ("created_at", datetime.now(timezone.utc).isoformat()),
    )
    if chunk_size is not None:
        db.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("chunk_size", str(chunk_size)),
        )
    if chunk_overlap is not None:
        db.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("chunk_overlap", str(chunk_overlap)),
        )
    db.commit()


def validate_model(db: sqlite3.Connection, model_name: str, model_dim: int) -> None:
    """Raise ValueError if the current model doesn't match the stored one."""
    meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
    stored_name = meta.get("model_name")
    stored_dim = meta.get("model_dim")
    if stored_name and stored_name != model_name:
        raise ValueError(
            f"model mismatch: index uses '{stored_name}', "
            f"current is '{model_name}'"
        )
    if stored_dim and int(stored_dim) != model_dim:
        raise ValueError(
            f"dimension mismatch: index uses {stored_dim}, "
            f"current is {model_dim}"
        )


def upsert_source(
    db: sqlite3.Connection,
    source_file: str,
    title: str | None = None,
    author: str | None = None,
    url: str | None = None,
    date: str | None = None,
    license: str | None = None,
    level: str | None = None,
) -> None:
    """Insert or update bibliographic metadata for a source file."""
    db.execute(
        "INSERT INTO sources(source_file, title, author, url, date, license, level) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(source_file) DO UPDATE SET "
        "title=COALESCE(excluded.title, sources.title), "
        "author=COALESCE(excluded.author, sources.author), "
        "url=COALESCE(excluded.url, sources.url), "
        "date=COALESCE(excluded.date, sources.date), "
        "license=COALESCE(excluded.license, sources.license), "
        "level=COALESCE(excluded.level, sources.level)",
        (source_file, title, author, url, date, license, level),
    )
    db.commit()


def get_source(db: sqlite3.Connection, source_file: str) -> dict | None:
    """Get bibliographic metadata for a source file."""
    db.row_factory = sqlite3.Row
    row = db.execute(
        "SELECT * FROM sources WHERE source_file = ?", (source_file,)
    ).fetchone()
    db.row_factory = None
    return dict(row) if row else None


def get_all_sources(db: sqlite3.Connection) -> list[dict]:
    """Get all source bibliographic metadata."""
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM sources ORDER BY source_file").fetchall()
    db.row_factory = None
    return [dict(r) for r in rows]


def insert_chunk(
    db: sqlite3.Connection,
    chunk_id: str,
    source_file: str,
    chunk_index: int,
    content: str,
    embedding: list[float],
) -> None:
    """Insert a single chunk with its embedding. Duplicates are ignored."""
    cur = db.execute(
        "INSERT OR IGNORE INTO chunks(id, source_file, chunk_index, content) "
        "VALUES (?, ?, ?, ?)",
        (chunk_id, source_file, chunk_index, content),
    )
    if cur.rowcount > 0:
        db.execute(
            "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
            (cur.lastrowid, serialize_float32(embedding)),
        )
    db.commit()


def insert_chunks(
    db: sqlite3.Connection,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> None:
    """Batch-insert chunks with their embeddings in a single transaction."""
    has_fts = _has_fts(db)
    for chunk, emb in zip(chunks, embeddings):
        cur = db.execute(
            "INSERT OR IGNORE INTO chunks(id, source_file, chunk_index, content) "
            "VALUES (?, ?, ?, ?)",
            (chunk["id"], chunk["source_file"], chunk["chunk_index"], chunk["content"]),
        )
        if cur.rowcount > 0:
            rowid = cur.lastrowid
            db.execute(
                "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                (rowid, serialize_float32(emb)),
            )
            if has_fts:
                db.execute(
                    "INSERT INTO chunks_fts(rowid, content, source_file) "
                    "VALUES (?, ?, ?)",
                    (rowid, chunk["content"], chunk["source_file"]),
                )
    db.commit()


RRF_K = 60


def _has_fts(db: sqlite3.Connection) -> bool:
    """Check if FTS5 table exists."""
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
    ).fetchone()
    return row is not None


def _search_vector(
    db: sqlite3.Connection,
    query_embedding: list[float],
    top_k: int,
) -> list[dict]:
    """KNN vector search. Returns results with rowid for RRF."""
    rows = db.execute(
        """
        WITH knn AS (
            SELECT rowid, distance
            FROM chunks_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
        )
        SELECT c.rowid, c.content, c.source_file, knn.distance,
               s.title, s.author, s.url, s.license
        FROM knn
        LEFT JOIN chunks c ON c.rowid = knn.rowid
        LEFT JOIN sources s ON s.source_file = c.source_file
        ORDER BY knn.distance
        """,
        (serialize_float32(query_embedding), top_k),
    ).fetchall()
    return [
        {
            "rowid": row[0],
            "content": row[1],
            "source_file": row[2],
            "score": 1.0 - row[3],
            "title": row[4],
            "author": row[5],
            "url": row[6],
            "license": row[7],
        }
        for row in rows
    ]


def _search_fts(
    db: sqlite3.Connection,
    query_text: str,
    top_k: int,
) -> list[dict]:
    """FTS5 full-text search."""
    safe_query = " ".join(
        w for w in query_text.split() if w and not w.startswith("-")
    )
    if not safe_query:
        return []
    rows = db.execute(
        """
        SELECT c.rowid, c.content, c.source_file,
               rank, s.title, s.author, s.url, s.license
        FROM chunks_fts
        LEFT JOIN chunks c ON c.rowid = chunks_fts.rowid
        LEFT JOIN sources s ON s.source_file = c.source_file
        WHERE chunks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (safe_query, top_k),
    ).fetchall()
    return [
        {
            "rowid": row[0],
            "content": row[1],
            "source_file": row[2],
            "score": -row[3],
            "title": row[4],
            "author": row[5],
            "url": row[6],
            "license": row[7],
        }
        for row in rows
    ]


def _rrf_fuse(
    vector_results: list[dict],
    fts_results: list[dict],
    top_k: int,
) -> list[dict]:
    """Reciprocal Rank Fusion of vector and FTS results."""
    scores: dict[int, float] = {}
    data: dict[int, dict] = {}

    for rank, r in enumerate(vector_results):
        rid = r["rowid"]
        scores[rid] = scores.get(rid, 0) + 1.0 / (RRF_K + rank + 1)
        data[rid] = r

    for rank, r in enumerate(fts_results):
        rid = r["rowid"]
        scores[rid] = scores.get(rid, 0) + 1.0 / (RRF_K + rank + 1)
        if rid not in data:
            data[rid] = r

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for rid, rrf_score in ranked:
        result = dict(data[rid])
        result["score"] = rrf_score
        result.pop("rowid", None)
        results.append(result)
    return results


def _expand_adjacent(
    db: sqlite3.Connection,
    results: list[dict],
    window_size: int,
) -> list[dict]:
    """Expand results with adjacent chunks, merged into one text."""
    expanded = []
    seen = set()

    for r in results:
        src = r["source_file"]
        rows = db.execute(
            "SELECT chunk_index, content FROM chunks "
            "WHERE source_file = ? ORDER BY chunk_index",
            (src,),
        ).fetchall()
        if not rows:
            expanded.append(r)
            continue

        idx_map = {row[0]: row[1] for row in rows}
        center_rows = db.execute(
            "SELECT chunk_index FROM chunks "
            "WHERE source_file = ? AND content = ?",
            (src, r["content"]),
        ).fetchall()
        center_idx = center_rows[0][0] if center_rows else 0

        indices = sorted(idx_map.keys())
        start = max(min(indices), center_idx - window_size)
        end = min(max(indices), center_idx + window_size)

        key = (src, start, end)
        if key in seen:
            continue
        seen.add(key)

        merged = "\n\n".join(
            idx_map[i] for i in range(start, end + 1) if i in idx_map
        )
        result = dict(r)
        result["content"] = merged
        expanded.append(result)

    return expanded


def search(
    db: sqlite3.Connection,
    query_embedding: list[float],
    top_k: int = 5,
    query_text: str = "",
    window_size: int = 0,
) -> list[dict]:
    """Hybrid search: vector + FTS5 with RRF fusion.

    Falls back to vector-only if no FTS5 table or no query_text.
    window_size > 0 expands results with adjacent chunks (merged).
    """
    retrieve_k = top_k * 3
    vector_results = _search_vector(db, query_embedding, retrieve_k)

    if query_text and _has_fts(db):
        fts_results = _search_fts(db, query_text, retrieve_k)
        results = _rrf_fuse(vector_results, fts_results, top_k)
    else:
        results = vector_results[:top_k]
        for r in results:
            r.pop("rowid", None)

    if window_size > 0:
        results = _expand_adjacent(db, results, window_size)

    return results


def list_sources(db: sqlite3.Connection) -> list[dict]:
    """List indexed files with chunk counts."""
    rows = db.execute(
        "SELECT source_file, count(*) FROM chunks "
        "GROUP BY source_file ORDER BY source_file"
    ).fetchall()
    return [{"source_file": row[0], "count": row[1]} for row in rows]
