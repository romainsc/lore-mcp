# Grooming E1.05: Store abstraction (Repository pattern)

## Context

store.py uses raw SQL with LEFT JOIN between
chunks, chunks_vec, and chunks_fts tables.
Orphan vectors (rowid in chunks_vec without
matching row in chunks) cause NULL content in
search results, crashing the reranker.

E12.97 validation found this bug: after
add_source, search_docs fails with
"Unsupported input type: NoneType" because
_rerank receives (query, None) pairs.

## Research findings

**No Python ORM supports sqlite-vec natively.**
SQLAlchemy coexists (Octave project) but
quarantines vec0 SQL. ChromaDB, LanceDB, and
sqlite-vec upstream all use raw SQL with
internal abstraction. The Repository pattern
is the standard approach.

See: ChromaDB `chromadb/db/impl/sqlite.py`
(Apache 2.0), Octave PR#84, sqlite-vec
examples (raw sqlite3).

## Design

### INNER JOIN instead of LEFT JOIN

Immediate fix: `_search_vector` uses LEFT JOIN
to match vec0 KNN results with chunks table.
If a vector has no matching chunk, content is
NULL. Replace with INNER JOIN — orphan vectors
are silently excluded.

```sql
-- Before (fragile)
LEFT JOIN chunks c ON c.rowid = knn.rowid

-- After (safe)
INNER JOIN chunks c ON c.rowid = knn.rowid
```

### ChunkStore class

Encapsulate multi-table operations in a class
that guarantees rowid synchronization:

```python
class ChunkStore:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert(self, chunks, embeddings):
        """Atomic insert into chunks + vec + fts."""

    def delete(self, source_file):
        """Atomic delete from chunks + vec + fts."""

    def search(self, embedding, top_k, **kwargs):
        """INNER JOIN search, guaranteed no NULL."""

    def list_sources(self):
        """List indexed sources with counts."""
```

Current functions (`insert_chunks`,
`delete_source_chunks`, `search`, etc.) become
methods of `ChunkStore`. External API unchanged.

### Module structure

Internal module `store.py` refactored, not
extracted. Extractable later if a second
consumer appears. No new dependency.

## MVPs

1. **MVP1**: LEFT JOIN → INNER JOIN in
   `_search_vector`. NULL guard in `_rerank`.
   Fix the crash.
2. **MVP2**: `ChunkStore` class wrapping
   existing functions. Same external API.
3. **MVP3**: Atomic transactions with rollback
   on partial failure.

## DoD

- INNER JOIN in all search queries
- NULL guard in _rerank (defense in depth)
- ChunkStore class in store.py
- No NULL content in search results (test)
- No new dependency
- 0 regression in existing tests

## Risks

- Refactoring store.py touches all callers
  (ingest.py, server.py, eval.py, build.py).
  MVP2 must preserve external function API.
- FTS5 external content tables could further
  automate rowid sync (future optimization,
  not MVP).
