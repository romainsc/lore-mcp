# Grooming E3.16: MCP serve db connection lifecycle

## Context

After `add_source` or `remove_source` modifies
the .db, `search_docs` and `list_indexed_sources`
continue serving stale data. The MCP server opens
a db connection on first query and caches it —
subsequent writes by background tasks are
invisible to the serve connection.

Found by E12.97 validation: after `add_source`
completed (7 chunks indexed), `search_docs`
returned no results for the added content. After
`remove_source` deleted all data,
`list_indexed_sources` still showed 21 sources.

## Root cause

`server.py` uses `open_db()` once and reuses the
connection. SQLite default journal mode is
`delete` — a reader connection opened before a
write does not see changes until it closes and
reopens.

## Fix options

### Option A: Invalidate after write (recommended)

After `add_source`/`remove_source` complete,
close and reopen the serve db connection.

```python
# In server.py, after add/remove completes:
_db_connection = None  # Force re-open on next query
```

Simple, no SQLite mode change, immediate effect.

### Option B: WAL mode

Enable WAL mode on the .db (`PRAGMA journal_mode=WAL`).
Writers and readers can coexist — a reader sees
writes committed before its next BEGIN.

More robust but changes the SQLite file format
(creates .db-wal and .db-shm files). May affect
portability of the .db file.

### Option C: Re-read on every query

Close and reopen the connection on every
`search_docs`/`list_indexed_sources` call.
Simple but adds latency (~1ms per query).

## Recommendation

**Option A** — minimal change, no performance
impact, no file format change. The invalidation
only happens when data changes (add/remove),
which is infrequent compared to reads.

## DoD

- After `add_source` completes: serve connection
  invalidated
- After `remove_source` completes: serve
  connection invalidated
- Test: add_source → search_docs finds content
- Test: remove_source → list_indexed_sources
  reflects removal
- No performance regression on search_docs

## Implementation

Add a `_invalidate_db()` helper in server.py that
closes the cached connection. Call it in the
`_do_add` callback (after ingest) and at the end
of `remove_source`. The next `search_docs` call
will reopen the connection with fresh data.
