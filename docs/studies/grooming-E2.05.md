# Grooming E2.05 — Dead code cleanup

## Context

Exhaustive audit (2026-10-03) of `src/lore_mcp/`
identified dead code accumulated over E6, E10,
E12, E3 iterations. The project evolved
significantly (manifest→recipe, langchain→Docling
HybridChunker, env vars→LoreConfig, inline
collections→server.py) but orphaned code was
not cleaned up.

## Scope

### Dead functions (19) — remove

| File | Symbol | Reason |
|------|--------|--------|
| `eval.py:532` | `_score_retrieval()` | Replaced by `_word_overlap` |
| `eval.py:182` | `parse_model_configs_from_cli()` | Vestige of `--models` CLI (E10.21) |
| `preprocess/enrich.py:79` | `_call_llm()` | Legacy wrapper, delegates to `llm.call_llm` |
| `collections.py:13` | `build_collection_name()` | Only called by tests |
| `collections.py:23` | `_parse_name()` | Only called by dead `discover_collections` |
| `collections.py:33` | `discover_collections()` | Reimplemented inline in server.py |
| `collections.py:65` | `search_collection()` | Never called in prod |
| `collections.py:86` | `search_across()` | Never called in prod |
| `server.py:186` | `format_collections()` | Never called |
| `store.py:246` | `insert_parent_chunk()` | Vestige of E6.08 pre-HybridChunker |
| `ingest.py:53` | `get_chunk_config()` | Params resolved via LoreConfig |
| `progress.py:283` | `report_step()` | Dead alias |
| `progress.py:287` | `report_config()` | Dead alias |
| `progress.py:294` | `report_summary()` | Dead alias |
| `task_manager.py:100` | `ModelRegistry.get_loaded()` | Only in tests |
| `task_manager.py:105` | `ModelRegistry.get_users()` | Only in tests |
| `task_manager.py:188` | `TaskManager.update_progress()` | Only in tests |
| `preprocess/dedup.py:28` | `DedupReport.to_skip` | Property never used |
| `preprocess/tables.py` | `protect_tables()` + all | Entire module dead |

### Unused imports (14) — remove

| File | Import |
|------|--------|
| `build_config.py:4` | `from pathlib import Path` |
| `build.py:8` | `generate_questions_from_db` from eval |
| `collections.py:7` | `import os` |
| `embedder.py:5` | `import os` |
| `embedder.py:6` | `from pathlib import Path` |
| `eval.py:5` | `import os` |
| `eval.py:7` | `field` from dataclasses |
| `eval.py:34` | `list_sources`, `get_all_sources` from store |
| `preprocess/llm.py:8` | `field` from dataclasses |
| `progress.py:3` | `import json` |
| `server.py:4` | `import os` |
| `preprocess/__init__.py:22` | `classify_parse_result` |
| `preprocess/__init__.py:28` | `unload_docling` |

### Orphan module (1) — remove

`src/lore_mcp/preprocess/tables.py` — vestige of
E6.02 (MarkdownTextSplitter table sentinels).
HybridChunker handles tables natively since
E12.99.

### Dead tests — remove or update

| Test file | Reason |
|-----------|--------|
| `test_table_protection.py` | Tests dead `tables.py` module |
| `test_chunk_config.py::TestGetChunkConfig` | Tests dead `get_chunk_config()` |

Note: `test_parent_child.py` may still be
relevant if parent-child chunking is used via
HybridChunker — verify before removing.

### Boundary cases — keep

- `classify_parse_result()`: keep in parse.py
  (used by tests, useful utility), but remove
  from `__init__.py` re-export
- `unload_docling()`: keep in parse.py (GPU
  memory management utility), but remove from
  `__init__.py` re-export
- `_RagasEmbeddingsWrapper` methods: NOT dead —
  dynamic interface contract for RAGAS/langchain

## DoD

- All dead functions removed from production code
- All unused imports removed
- `tables.py` module deleted
- Dead tests removed or updated
- `collections.py` cleaned (only
  `collection_db_path` remains, or module
  removed if function moved)
- CI green
- No functional regression (existing tests pass)

## MVP

Single MVP — all cleanup in one pass. Changes
are purely subtractive (no logic changes).

## Dependencies

None. Pre-release project, no backward compat
needed.

## Risks

Low. All removals are dead code confirmed by
both graph analysis and grep. Tests provide
regression safety net.
