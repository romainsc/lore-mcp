# Grooming E12.122 — Guard _get_db against empty .db

## Problem

`_get_db(collection)` calls `open_db(db_path)` even
when the .db file does not exist. `sqlite3.connect`
creates an empty file (no tables). Any subsequent
query (`search_docs`, `list_indexed_sources`) crashes
with `OperationalError: no such table: chunks`.

Discovered during E2.13 validation: `add_recipe` with
`preprocess=false` on a new collection.

## Fix

`_get_db` checks `Path(db_path).exists()` before
opening. If absent, raises with clear message.

Callers in read-only MCP tools (`search_docs`,
`list_indexed_sources`) catch the error and return
a user-friendly message.

Write tools (`add_source`, `add_sources`,
`add_recipe`) do not use `_get_db` for writes —
they use `ingest_with_manifest` or explicit
`open_db` + `create_tables`. No change needed.

## DoD

- `_get_db` raises `FileNotFoundError` if .db
  does not exist
- `search_docs` returns "Collection not found"
  instead of crashing
- `list_indexed_sources` returns "Collection not
  found" instead of crashing
- Existing tests pass
- CI green

## Effort

Petit — 3 fonctions à modifier.
