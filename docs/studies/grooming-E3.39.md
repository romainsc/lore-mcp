# Grooming E3.39 — Documentation sync with code

## Context

Exhaustive audit (2026-10-03) compared all
technical documentation against current code.
15 categories of incohérences found. Root cause:
rapid iteration (E12.xx, E3.xx — 20+ items)
without proportional doc updates.

## Scope

### MVP1 — CLAUDE.md (source of truth)

Fix CLAUDE.md as priority — it drives all AI
interaction.

| Section | Fix |
|---------|-----|
| §2 SQL schema | Add `lang`, `extra`, `parent_id` to `sources`/`chunks`. Add `parent_chunks`, `chunks_fts` tables. Remove `chunk_count` from `sources` (computed dynamically) |
| §2 Embedding model | Remove `LORE_MODEL` env var reference — configurable via `config.yaml` |
| §4 Chosen technologies | Chunking: `langchain-text-splitters` → `Docling HybridChunker` (docling-core, MIT) |
| §10 Project structure | Remove `manifest.py`, add `config.py`, `recipe.py`, `checkpoint.py`, `progress.py`, `task_manager.py`, `lint.py`. Add `prompts.yaml`, `bootstrap.yaml` |
| §2 MCP tools | Add 14 missing tools to the list (currently only 3 documented) |

### MVP2 — code-guide.md (most affected)

Near-complete rewrite needed. Current state:
line numbers wrong, functions renamed/deleted,
modules restructured.

| Section | Fix |
|---------|-----|
| `manifest.py` section | Rename to `recipe.py`, update API (`parse_recipe`, etc.) |
| `server.py` section | Remove `_single_db`, `_get_single_db()`, `_is_multi_collection()`. Document `_get_db(collection)`, `_db_cache`, all 17 MCP tools |
| `ingest.py` section | Remove `preprocess()`, update chunker (HybridChunker), fix `EMBED_BATCH_SIZE` 64→32, remove `get_chunk_config()` |
| CLI section | Add 5 missing subcommands: `preprocess`, `enrich`, `lint`, `state`, `init`, `version` |
| All sections | Fix line number references (all wrong) |
| New sections | Add `config.py`, `task_manager.py`, `checkpoint.py`, `lint.py` |

### MVP3 — architecture.md

| Section | Fix |
|---------|-----|
| Chunking | Replace MarkdownTextSplitter → HybridChunker description |
| Env vars | Remove all `LORE_*` references (~15) |
| `EMBED_BATCH_SIZE` | 64→32 |
| MCP tools | Update signatures (search_docs 4 params, list_indexed_sources 3 params), add missing tools |
| Scoring | Document that RRF changes score semantics |
| bge-m3 section | Update/remove "Why bge-m3?" (default is nomic-v2) |

### MVP4 — configuration.md + preprocessing.md

| File | Fix |
|------|-----|
| `configuration.md` | Remove `LORE_*` env var sections. Update `manifest.py` → `recipe.py`. Update CLI args (deprecated `--docs-base-dir`, `--output-dir`) |
| `preprocessing.md` | Update ownership scope (lore-mcp now covers all 6 steps). Fix `manifest.py` → `recipe.py`. Remove `MD_SEPARATORS` reference |

## DoD

- All 15 incohérence categories resolved
- Every file/function/parameter mentioned in docs
  exists in code under that exact name
- Every MCP tool documented with correct signature
- Every CLI subcommand documented
- No `LORE_*` env var reference in docs (E12.60)
- No `manifest.py` reference in docs (E12.93)
- No `MarkdownTextSplitter` reference (E12.99)
- SQL schema matches `store.py:create_tables()`
- Line numbers in code-guide.md are correct
- CI green (no code changes, but verify)

## Dependencies

- E2.05 (dead code cleanup) should be done first
  — no point documenting code that will be
  removed

## Risks

- Line numbers will drift again on next code
  change. Consider: reference by function name
  rather than line number in code-guide.md.
  Decision: use function names as primary
  anchor, line numbers as secondary hint
  (acceptable drift).

## Effort estimate

MVP1 (CLAUDE.md): small — targeted edits.
MVP2 (code-guide.md): large — near-rewrite of
several sections.
MVP3 (architecture.md): medium — scattered edits.
MVP4 (config+preprocessing): small — search and
replace mostly.
