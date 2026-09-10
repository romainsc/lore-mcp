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
        "  metadata TEXT DEFAULT '{}',"
        "  parent_id INTEGER DEFAULT NULL"
        ")"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS parent_chunks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  source_file TEXT NOT NULL,"
        "  content TEXT NOT NULL"
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


def insert_parent_chunk(
    db: sqlite3.Connection,
    source_file: str,
    content: str,
) -> int:
    """Insert a parent chunk and return its id."""
    cur = db.execute(
        "INSERT INTO parent_chunks(source_file, content) VALUES (?, ?)",
        (source_file, content),
    )
    db.commit()
    return cur.lastrowid


def insert_chunks(
    db: sqlite3.Connection,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> None:
    """Batch-insert chunks with their embeddings in a single transaction."""
    has_fts = _has_fts(db)
    for chunk, emb in zip(chunks, embeddings):
        parent_id = chunk.get("parent_id")
        if parent_id is not None:
            cur = db.execute(
                "INSERT OR IGNORE INTO chunks(id, source_file, chunk_index, content, parent_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (chunk["id"], chunk["source_file"], chunk["chunk_index"], chunk["content"], parent_id),
            )
        else:
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
    import re
    cleaned = re.sub(r'[^\w\s]', ' ', query_text)
    safe_query = " ".join(w for w in cleaned.split() if w)
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


_reranker = None


def _load_reranker(model_name: str):
    """Load a cross-encoder reranker model."""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(model_name)
    return _reranker


def _rerank(
    query_text: str,
    results: list[dict],
    model_name: str,
    top_k: int,
) -> list[dict]:
    """Re-score results with a cross-encoder."""
    reranker = _load_reranker(model_name)
    pairs = [(query_text, r["content"]) for r in results]
    scores = reranker.predict(pairs)
    for r, score in zip(results, scores):
        r["score"] = float(score)
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


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


def _expand_parent(
    db: sqlite3.Connection,
    results: list[dict],
) -> list[dict]:
    """Replace child chunk content with parent chunk content."""
    expanded = []
    seen_parents = set()
    for r in results:
        row = db.execute(
            "SELECT parent_id FROM chunks WHERE content = ? AND source_file = ?",
            (r["content"], r["source_file"]),
        ).fetchone()
        parent_id = row[0] if row else None
        if parent_id is not None:
            if parent_id in seen_parents:
                continue
            seen_parents.add(parent_id)
            parent_row = db.execute(
                "SELECT content FROM parent_chunks WHERE id = ?",
                (parent_id,),
            ).fetchone()
            if parent_row:
                result = dict(r)
                result["content"] = parent_row[0]
                expanded.append(result)
                continue
        expanded.append(r)
    return expanded


def _has_parent_chunks(db: sqlite3.Connection) -> bool:
    """Check if parent_chunks table exists and has data."""
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='parent_chunks'"
    ).fetchone()
    if not row:
        return False
    count = db.execute("SELECT COUNT(*) FROM parent_chunks").fetchone()[0]
    return count > 0


def _parse_filters(filter_str: str) -> dict:
    """Parse 'key:value,key:value' filter string into dict."""
    if not filter_str:
        return {}
    filters = {}
    for pair in filter_str.split(","):
        pair = pair.strip()
        if ":" in pair:
            key, value = pair.split(":", 1)
            filters[key.strip()] = value.strip()
    return filters


def _apply_filters(results: list[dict], filters: dict) -> list[dict]:
    """Post-filter results by metadata fields."""
    if not filters:
        return results
    filtered = []
    for r in results:
        match = True
        for key, value in filters.items():
            if key == "source" or key == "source_file":
                if r.get("source_file") and value not in r["source_file"]:
                    match = False
            elif key == "date_from":
                if r.get("date") and str(r["date"]) < value:
                    match = False
            elif key == "date_to":
                if r.get("date") and str(r["date"]) > value:
                    match = False
            elif key in ("title", "author", "license", "level"):
                r_val = r.get(key, "")
                if r_val and value.lower() not in str(r_val).lower():
                    match = False
        if match:
            filtered.append(r)
    return filtered


def _apply_mmr(
    results: list[dict],
    top_k: int,
    lambda_param: float = 0.5,
) -> list[dict]:
    """Maximal Marginal Relevance: diversify results."""
    if not results or len(results) <= 1:
        return results

    selected = [results[0]]
    candidates = list(results[1:])

    while len(selected) < top_k and candidates:
        best_score = -float("inf")
        best_idx = 0
        for i, cand in enumerate(candidates):
            relevance = cand.get("score", 0)
            max_sim = max(
                _text_similarity(cand["content"], s["content"])
                for s in selected
            )
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i
        selected.append(candidates.pop(best_idx))

    return selected


def _text_similarity(a: str, b: str) -> float:
    """Simple Jaccard similarity on word sets."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _apply_per_source_cap(results: list[dict], max_per_source: int) -> list[dict]:
    """Limit results to max N chunks per source_file."""
    if max_per_source <= 0:
        return results
    counts: dict[str, int] = {}
    capped = []
    for r in results:
        src = r.get("source_file", "")
        counts[src] = counts.get(src, 0) + 1
        if counts[src] <= max_per_source:
            capped.append(r)
    return capped


def search(
    db: sqlite3.Connection,
    query_embedding: list[float],
    top_k: int = 5,
    query_text: str = "",
    window_size: int = 0,
    reranking_model: str = "",
    filters: dict | None = None,
    mmr: bool = False,
    max_per_source: int = 0,
    parent_child: bool = False,
) -> list[dict]:
    """Hybrid search: vector + FTS5 with RRF fusion.

    Falls back to vector-only if no FTS5 table or no query_text.
    window_size > 0 expands results with adjacent chunks (merged).
    reranking_model re-scores candidates with a cross-encoder.
    filters: metadata post-filtering (source, title, author, etc.).
    mmr: apply Maximal Marginal Relevance for diversity.
    max_per_source: limit chunks per source file (0 = no limit).
    parent_child: replace child content with parent content.
    """
    retrieve_k = top_k * 3
    vector_results = _search_vector(db, query_embedding, retrieve_k)

    if query_text and _has_fts(db):
        fts_results = _search_fts(db, query_text, retrieve_k)
        results = _rrf_fuse(vector_results, fts_results, top_k if not reranking_model else retrieve_k)
    else:
        results = vector_results[:top_k if not reranking_model else retrieve_k]
        for r in results:
            r.pop("rowid", None)

    if filters:
        results = _apply_filters(results, filters)

    if reranking_model and query_text:
        results = _rerank(query_text, results, reranking_model, top_k)

    if mmr:
        results = _apply_mmr(results, top_k)

    if max_per_source > 0:
        results = _apply_per_source_cap(results, max_per_source)

    if parent_child and _has_parent_chunks(db):
        results = _expand_parent(db, results)

    if window_size > 0:
        results = _expand_adjacent(db, results, window_size)

    return results[:top_k]


def list_sources(db: sqlite3.Connection) -> list[dict]:
    """List indexed files with chunk counts."""
    rows = db.execute(
        "SELECT source_file, count(*) FROM chunks "
        "GROUP BY source_file ORDER BY source_file"
    ).fetchall()
    return [{"source_file": row[0], "count": row[1]} for row in rows]
