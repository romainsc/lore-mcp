"""SQLite + sqlite-vec storage backend. See docs/architecture.md."""

import sqlite3
from datetime import datetime, timezone

import sqlite_vec
from sqlite_vec import serialize_float32


RRF_K = 60
_reranker = None


def _load_reranker(model_name: str):
    """Load a cross-encoder reranker model (singleton)."""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(model_name)
    return _reranker


class ChunkStore:
    """Collection-level store: all DB operations on a single .db file."""

    def __init__(self, db_path: str):
        self.path = db_path
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        self._migrate()

    def close(self):
        """Close the database connection."""
        self.db.close()

    # --- Migration ---

    def _migrate(self):
        tables = {r[0] for r in self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "sources" not in tables:
            return
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(sources)").fetchall()}
        if "lang" not in cols:
            self.db.execute("ALTER TABLE sources ADD COLUMN lang TEXT")
            self.db.commit()

    # --- Schema ---

    def create_tables(
        self,
        model_name: str,
        model_dim: int,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        """Create chunks, chunks_vec, sources, and meta tables if they don't exist."""
        if not isinstance(model_dim, int) or model_dim <= 0:
            raise ValueError(f"model_dim must be a positive integer, got {model_dim}")
        self.db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec "
            f"USING vec0(embedding float[{model_dim}] distance_metric=cosine)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS chunks ("
            "  id TEXT PRIMARY KEY,"
            "  source_file TEXT NOT NULL,"
            "  chunk_index INTEGER NOT NULL,"
            "  content TEXT NOT NULL,"
            "  metadata TEXT DEFAULT '{}',"
            "  parent_id INTEGER DEFAULT NULL"
            ")"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS parent_chunks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  source_file TEXT NOT NULL,"
            "  content TEXT NOT NULL"
            ")"
        )
        self.db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
            "USING fts5(content, source_file, content=chunks, content_rowid=rowid)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS sources ("
            "  source_file TEXT PRIMARY KEY,"
            "  title TEXT,"
            "  author TEXT,"
            "  url TEXT,"
            "  date TEXT,"
            "  license TEXT,"
            "  level TEXT,"
            "  lang TEXT,"
            "  extra TEXT DEFAULT '{}'"
            ")"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS source_hashes ("
            "  source_file TEXT PRIMARY KEY,"
            "  content_hash TEXT NOT NULL,"
            "  indexed_at TEXT NOT NULL"
            ")"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS meta ("
            "  key TEXT PRIMARY KEY,"
            "  value TEXT NOT NULL"
            ")"
        )
        self.db.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("model_name", model_name),
        )
        self.db.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("model_dim", str(model_dim)),
        )
        self.db.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("created_at", datetime.now(timezone.utc).isoformat()),
        )
        if chunk_size is not None:
            self.db.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
                ("chunk_size", str(chunk_size)),
            )
        if chunk_overlap is not None:
            self.db.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
                ("chunk_overlap", str(chunk_overlap)),
            )
        self.db.commit()

    def get_meta(self) -> dict[str, str]:
        """Read all metadata from the meta table."""
        try:
            return dict(self.db.execute("SELECT key, value FROM meta").fetchall())
        except sqlite3.OperationalError:
            return {}

    def validate_model(self, model_name: str, model_dim: int) -> None:
        """Raise ValueError if the current model doesn't match the stored one."""
        meta = dict(self.db.execute("SELECT key, value FROM meta").fetchall())
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

    # --- Sources ---

    def upsert_source(
        self,
        source_file: str,
        title: str | None = None,
        author: str | None = None,
        url: str | None = None,
        date: str | None = None,
        license: str | None = None,
        level: str | None = None,
        lang: str | None = None,
    ) -> None:
        """Insert or update bibliographic metadata for a source file."""
        self.db.execute(
            "INSERT INTO sources(source_file, title, author, url, date, license, level, lang) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(source_file) DO UPDATE SET "
            "title=COALESCE(excluded.title, sources.title), "
            "author=COALESCE(excluded.author, sources.author), "
            "url=COALESCE(excluded.url, sources.url), "
            "date=COALESCE(excluded.date, sources.date), "
            "license=COALESCE(excluded.license, sources.license), "
            "level=COALESCE(excluded.level, sources.level), "
            "lang=COALESCE(excluded.lang, sources.lang)",
            (source_file, title, author, url, date, license, level, lang),
        )
        self.db.commit()

    def get_source(self, source_file: str) -> dict | None:
        """Get bibliographic metadata for a source file."""
        self.db.row_factory = sqlite3.Row
        row = self.db.execute(
            "SELECT * FROM sources WHERE source_file = ?", (source_file,)
        ).fetchone()
        self.db.row_factory = None
        return dict(row) if row else None

    def get_all_sources(self) -> list[dict]:
        """Get all source bibliographic metadata."""
        self.db.row_factory = sqlite3.Row
        rows = self.db.execute("SELECT * FROM sources ORDER BY source_file").fetchall()
        self.db.row_factory = None
        return [dict(r) for r in rows]

    def list_sources(self) -> list[dict]:
        """List indexed files with chunk counts."""
        rows = self.db.execute(
            "SELECT source_file, count(*) FROM chunks "
            "GROUP BY source_file ORDER BY source_file"
        ).fetchall()
        return [{"source_file": row[0], "count": row[1]} for row in rows]

    def set_source_hash(self, source_file: str, content_hash: str) -> None:
        """Store or update the content hash for a source file."""
        self.db.execute(
            "INSERT INTO source_hashes(source_file, content_hash, indexed_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(source_file) DO UPDATE SET "
            "content_hash=excluded.content_hash, indexed_at=excluded.indexed_at",
            (source_file, content_hash, datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()

    def get_source_hashes(self) -> dict[str, str]:
        """Return {source_file: content_hash} for all indexed sources."""
        try:
            rows = self.db.execute(
                "SELECT source_file, content_hash FROM source_hashes"
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        return {r[0]: r[1] for r in rows}

    def delete_source_chunks(self, source_file: str) -> None:
        """Delete all chunks, vectors, FTS entries, metadata, and hash for a source."""
        rowids = [r[0] for r in self.db.execute(
            "SELECT rowid FROM chunks WHERE source_file = ?", (source_file,)
        ).fetchall()]
        if rowids:
            placeholders = ",".join("?" * len(rowids))
            self.db.execute(
                f"DELETE FROM chunks_vec WHERE rowid IN ({placeholders})", rowids
            )
            self.db.execute(
                f"DELETE FROM chunks WHERE rowid IN ({placeholders})", rowids
            )
        self.db.execute("DELETE FROM parent_chunks WHERE source_file = ?", (source_file,))
        self.db.execute("DELETE FROM sources WHERE source_file = ?", (source_file,))
        self.db.execute("DELETE FROM source_hashes WHERE source_file = ?", (source_file,))
        self.db.commit()

    # --- Chunks ---

    def insert_chunk(
        self,
        chunk_id: str,
        source_file: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
    ) -> None:
        """Insert a single chunk with its embedding. Duplicates are ignored."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO chunks(id, source_file, chunk_index, content) "
            "VALUES (?, ?, ?, ?)",
            (chunk_id, source_file, chunk_index, content),
        )
        if cur.rowcount > 0:
            self.db.execute(
                "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                (cur.lastrowid, serialize_float32(embedding)),
            )
        self.db.commit()

    def insert_chunks(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        """Batch-insert chunks with their embeddings in a single transaction."""
        has_fts = self._has_fts()
        for chunk, emb in zip(chunks, embeddings):
            parent_id = chunk.get("parent_id")
            if parent_id is not None:
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO chunks(id, source_file, chunk_index, content, parent_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (chunk["id"], chunk["source_file"], chunk["chunk_index"],
                     chunk["content"], parent_id),
                )
            else:
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO chunks(id, source_file, chunk_index, content) "
                    "VALUES (?, ?, ?, ?)",
                    (chunk["id"], chunk["source_file"], chunk["chunk_index"],
                     chunk["content"]),
                )
            if cur.rowcount > 0:
                rowid = cur.lastrowid
                self.db.execute(
                    "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                    (rowid, serialize_float32(emb)),
                )
                if has_fts:
                    self.db.execute(
                        "INSERT INTO chunks_fts(rowid, content, source_file) "
                        "VALUES (?, ?, ?)",
                        (rowid, chunk["content"], chunk["source_file"]),
                    )
        self.db.commit()

    # --- Search ---

    def _has_fts(self) -> bool:
        row = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
        ).fetchone()
        return row is not None

    def _build_prefilter_rowids(self, filters: dict) -> list[int] | None:
        if not filters:
            return None
        conditions = []
        params = []
        for key, value in filters.items():
            if key in ("source", "source_file"):
                conditions.append("c.source_file LIKE ?")
                params.append(f"%{value}%")
            elif key == "level":
                conditions.append("s.level = ?")
                params.append(value)
            elif key == "license":
                conditions.append("s.license LIKE ?")
                params.append(f"%{value}%")
            elif key == "title":
                conditions.append("s.title LIKE ?")
                params.append(f"%{value}%")
            elif key == "author":
                conditions.append("s.author LIKE ?")
                params.append(f"%{value}%")
            elif key == "date_from":
                conditions.append("s.date >= ?")
                params.append(value)
            elif key == "date_to":
                conditions.append("s.date <= ?")
                params.append(value)
        if not conditions:
            return None
        where = " AND ".join(conditions)
        rows = self.db.execute(
            f"SELECT c.rowid FROM chunks c "
            f"LEFT JOIN sources s ON s.source_file = c.source_file "
            f"WHERE {where}",
            params,
        ).fetchall()
        return [r[0] for r in rows]

    def _search_vector(
        self,
        query_embedding: list[float],
        top_k: int,
        prefilter_rowids: list[int] | None = None,
    ) -> list[dict]:
        if prefilter_rowids is not None:
            if not prefilter_rowids:
                return []
            placeholders = ",".join("?" * len(prefilter_rowids))
            rows = self.db.execute(
                f"""
                WITH knn AS (
                    SELECT rowid, distance
                    FROM chunks_vec
                    WHERE embedding MATCH ?
                    AND k = ?
                    AND rowid IN ({placeholders})
                )
                SELECT c.rowid, c.content, c.source_file, knn.distance,
                       s.title, s.author, s.url, s.license
                FROM knn
                JOIN chunks c ON c.rowid = knn.rowid
                LEFT JOIN sources s ON s.source_file = c.source_file
                ORDER BY knn.distance
                """,
                [serialize_float32(query_embedding), top_k] + prefilter_rowids,
            ).fetchall()
        else:
            rows = self.db.execute(
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
                JOIN chunks c ON c.rowid = knn.rowid
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
                "score": 1.0 - (row[3] or 0.0),
                "title": row[4],
                "author": row[5],
                "url": row[6],
                "license": row[7],
            }
            for row in rows
            if row[1] is not None
        ]

    def _search_fts(self, query_text: str, top_k: int) -> list[dict]:
        import re
        cleaned = re.sub(r'[^\w\s]', ' ', query_text)
        safe_query = " ".join(w for w in cleaned.split() if w)
        if not safe_query:
            return []
        rows = self.db.execute(
            """
            SELECT c.rowid, c.content, c.source_file,
                   rank, s.title, s.author, s.url, s.license
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
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

    def _expand_adjacent(self, results: list[dict], window_size: int) -> list[dict]:
        expanded = []
        seen = set()
        for r in results:
            src = r["source_file"]
            rows = self.db.execute(
                "SELECT chunk_index, content FROM chunks "
                "WHERE source_file = ? ORDER BY chunk_index",
                (src,),
            ).fetchall()
            if not rows:
                expanded.append(r)
                continue
            idx_map = {row[0]: row[1] for row in rows}
            center_rows = self.db.execute(
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

    def _expand_parent(self, results: list[dict]) -> list[dict]:
        expanded = []
        seen_parents = set()
        for r in results:
            row = self.db.execute(
                "SELECT parent_id FROM chunks WHERE content = ? AND source_file = ?",
                (r["content"], r["source_file"]),
            ).fetchone()
            parent_id = row[0] if row else None
            if parent_id is not None:
                if parent_id in seen_parents:
                    continue
                seen_parents.add(parent_id)
                parent_row = self.db.execute(
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

    def _has_parent_chunks(self) -> bool:
        row = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='parent_chunks'"
        ).fetchone()
        if not row:
            return False
        count = self.db.execute("SELECT COUNT(*) FROM parent_chunks").fetchone()[0]
        return count > 0

    def search(
        self,
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
        """Hybrid search: vector + FTS5 with RRF fusion."""
        retrieve_k = top_k * 3
        prefilter_rowids = self._build_prefilter_rowids(filters) if filters else None
        vector_results = self._search_vector(
            query_embedding, retrieve_k, prefilter_rowids=prefilter_rowids
        )

        if query_text and self._has_fts():
            fts_results = self._search_fts(query_text, retrieve_k)
            if prefilter_rowids is not None:
                allowed = set(prefilter_rowids)
                fts_results = [r for r in fts_results if r.get("rowid") in allowed]
            results = _rrf_fuse(
                vector_results, fts_results,
                top_k if not reranking_model else retrieve_k,
            )
        else:
            results = vector_results[:top_k if not reranking_model else retrieve_k]
            for r in results:
                r.pop("rowid", None)

        if reranking_model and query_text:
            results = _rerank(query_text, results, reranking_model, top_k)

        if mmr:
            results = _apply_mmr(results, top_k)

        if max_per_source > 0:
            results = _apply_per_source_cap(results, max_per_source)

        if parent_child and self._has_parent_chunks():
            results = self._expand_parent(results)

        if window_size > 0:
            results = self._expand_adjacent(results, window_size)

        return results[:top_k]

    # --- Static utilities ---

    @staticmethod
    def parse_filters(filter_str: str) -> dict:
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


# --- Module-level helpers (no db state) ---

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


def _rerank(
    query_text: str,
    results: list[dict],
    model_name: str,
    top_k: int,
) -> list[dict]:
    """Re-score results with a cross-encoder."""
    reranker = _load_reranker(model_name)
    results = [r for r in results if r.get("content") is not None]
    if not results:
        return []
    pairs = [(query_text, r["content"]) for r in results]
    scores = reranker.predict(pairs)
    for r, score in zip(results, scores):
        r["score"] = float(score)
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


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


# --- Backward compatibility for tests ---
# These thin wrappers let test files keep using the old function API.
# Production code uses ChunkStore directly.

def open_db(path: str) -> sqlite3.Connection:
    """Open a SQLite database. Returns raw connection."""
    db = sqlite3.connect(path, check_same_thread=False)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "sources" in tables:
        cols = {r[1] for r in db.execute("PRAGMA table_info(sources)").fetchall()}
        if "lang" not in cols:
            db.execute("ALTER TABLE sources ADD COLUMN lang TEXT")
            db.commit()
    return db


def create_tables(db, model_name, model_dim, chunk_size=None, chunk_overlap=None):
    """Create tables on a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    s.create_tables(model_name, model_dim, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def validate_model(db, model_name, model_dim):
    """Validate model on a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    s.validate_model(model_name, model_dim)


def get_meta(db) -> dict:
    """Get meta from a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s.get_meta()


def upsert_source(db, source_file, **kwargs):
    """Upsert source on a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    s.upsert_source(source_file, **kwargs)


def get_source(db, source_file):
    """Get source from a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s.get_source(source_file)


def get_all_sources(db):
    """Get all sources from a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s.get_all_sources()


def list_sources(db):
    """List sources from a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s.list_sources()


def set_source_hash(db, source_file, content_hash):
    """Set source hash on a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    s.set_source_hash(source_file, content_hash)


def get_source_hashes(db):
    """Get source hashes from a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s.get_source_hashes()


def delete_source_chunks(db, source_file):
    """Delete source chunks on a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    s.delete_source_chunks(source_file)


def insert_chunk(db, chunk_id, source_file, chunk_index, content, embedding):
    """Insert a single chunk on a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    s.insert_chunk(chunk_id, source_file, chunk_index, content, embedding)


def insert_chunks(db, chunks, embeddings):
    """Batch insert chunks on a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    s.insert_chunks(chunks, embeddings)


def search(db, query_embedding, top_k=5, **kwargs):
    """Search on a raw connection."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s.search(query_embedding, top_k=top_k, **kwargs)


def _parse_filters(filter_str):
    """Parse filters (backward compat)."""
    return ChunkStore.parse_filters(filter_str)


def _has_parent_chunks(db):
    """Check parent chunks on a raw connection (backward compat)."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s._has_parent_chunks()


def _expand_parent(db, results):
    """Expand parent chunks on a raw connection (backward compat)."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s._expand_parent(results)


def _has_fts(db):
    """Check FTS on a raw connection (backward compat)."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s._has_fts()


def _build_prefilter_rowids(db, filters):
    """Build prefilter rowids on a raw connection (backward compat)."""
    s = ChunkStore.__new__(ChunkStore)
    s.db = db
    s.path = ""
    return s._build_prefilter_rowids(filters)
