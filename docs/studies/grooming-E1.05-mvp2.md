# Grooming E1.05 MVP2 — ChunkStore class

## Problem

store.py has 29 functions, 715 lines, no class.
All consumers (server.py, ingest.py, eval.py,
build.py, metadata.py) import individual functions
and pass `db` as first argument. `source_file`
appears as parameter in ~70 refs across 6 files.

Changing the source identifier (E3.29) would
require modifying all 70+ refs. With a class,
it's one change in one file.

## Design

```python
class ChunkStore:
    """Collection-level store operations."""

    def __init__(self, db_path: str):
        self.db = open_db(db_path)
        self.path = db_path

    def close(self):
        self.db.close()

    # --- Schema ---
    def create_tables(self, model_name, model_dim,
                      chunk_size=None, chunk_overlap=None)
    def validate_model(self, model_name, model_dim)
    def get_meta(self) -> dict[str, str]

    # --- Sources ---
    def upsert_source(self, source_file, **meta)
    def get_source(self, source_file) -> dict | None
    def get_all_sources(self) -> list[dict]
    def list_sources(self) -> list[dict]
    def set_hash(self, source_file, content_hash)
    def get_hashes(self) -> dict[str, str]
    def delete_source(self, source_file)

    # --- Chunks ---
    def insert_chunk(self, chunk_id, source_file,
                     chunk_index, content, embedding)
    def insert_chunks(self, chunks, embeddings)

    # --- Search ---
    def search(self, embedding, top_k=5, *,
               query_text="", reranking_model="",
               filters=None, window_size=0,
               mmr=False) -> list[dict]

    # --- Utilities ---
    @staticmethod
    def parse_filters(filter_str) -> dict
```

Functions that don't need `db` stay as module-level:
`serialize_float32` (re-export from sqlite_vec).

Private functions (`_search_vector`, `_search_fts`,
`_rrf_fuse`, `_rerank`, `_expand_adjacent`,
`_expand_parent`, `_apply_mmr`, `_apply_per_source_cap`,
`_load_reranker`, `_text_similarity`, `_has_fts`,
`_has_parent_chunks`, `_build_prefilter_rowids`)
become methods of ChunkStore.

## Consumers to migrate

| File | Current imports | New pattern |
|------|----------------|-------------|
| server.py | open_db, search, validate_model, list_sources, get_meta, create_tables, delete_source_chunks, _parse_filters | `store = ChunkStore(path)`, `store.search(...)` |
| ingest.py | create_tables, delete_source_chunks, get_source_hashes, insert_chunks, open_db, set_source_hash, upsert_source, validate_model | `store = ChunkStore(path)`, `store.insert_chunks(...)` |
| eval.py | open_db, search | `store = ChunkStore(path)`, `store.search(...)` |
| build.py | open_db, list_sources | `store = ChunkStore(path)`, `store.list_sources()` |
| metadata.py | get_all_sources, list_sources, open_db | `store = ChunkStore(path)`, `store.get_all_sources()` |

## Migration strategy

**Backward compatible**: keep module-level
functions as thin wrappers during migration.
Remove wrappers once all consumers are migrated.

```python
# Temporary wrapper (removed after migration)
def open_db(path):
    return ChunkStore(path).db
```

Actually: no wrappers. All consumers are in
lore-mcp (no external users pre-release).
Migrate all at once.

## server.py _get_db

Current: `_get_db` returns `sqlite3.Connection`.
New: `_get_store` returns `ChunkStore`.
Cache changes from `_db_cache: dict[str, Connection]`
to `_store_cache: dict[str, ChunkStore]`.

## DoD

- ChunkStore class in store.py
- All 5 consumer files migrated
- No raw `db` parameter in consumer code
- `source_file` appears only inside ChunkStore
- Tests adapted (fixtures return ChunkStore)
- All existing tests pass
- CI green

## Effort

Moyen — refactoring mécanique (715 lignes
store.py + 5 consumers + tests). Pas de
changement fonctionnel.
