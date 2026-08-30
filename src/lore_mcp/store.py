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
    for chunk, emb in zip(chunks, embeddings):
        cur = db.execute(
            "INSERT OR IGNORE INTO chunks(id, source_file, chunk_index, content) "
            "VALUES (?, ?, ?, ?)",
            (chunk["id"], chunk["source_file"], chunk["chunk_index"], chunk["content"]),
        )
        if cur.rowcount > 0:
            db.execute(
                "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                (cur.lastrowid, serialize_float32(emb)),
            )
    db.commit()


def search(
    db: sqlite3.Connection,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """KNN search with bibliographic metadata from sources table."""
    rows = db.execute(
        """
        WITH knn AS (
            SELECT rowid, distance
            FROM chunks_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
        )
        SELECT c.content, c.source_file, knn.distance,
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
            "content": row[0],
            "source_file": row[1],
            "score": 1.0 - row[2],
            "title": row[3],
            "author": row[4],
            "url": row[5],
            "license": row[6],
        }
        for row in rows
    ]


def list_sources(db: sqlite3.Connection) -> list[dict]:
    """List indexed files with chunk counts."""
    rows = db.execute(
        "SELECT source_file, count(*) FROM chunks "
        "GROUP BY source_file ORDER BY source_file"
    ).fetchall()
    return [{"source_file": row[0], "count": row[1]} for row in rows]
