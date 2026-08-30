# ADR-004: Multi-collection with license classification

- **Status:** Accepted
- **Date:** 2026-08-30
- **Decision:** Support multiple independent `.db` files in a directory, each representing a collection with a license level tag

## Context

lore-mcp was originally designed around a single `.db` file (`LORE_DB_PATH`). The openshift workspace MVP1 requires indexing multiple corpora with different redistribution rights. A Red Hat documentation corpus under NDA cannot be stored in the same file as a freely licensed open-source corpus — they must be separable for independent distribution and access control.

Four license levels were identified:

| Level | Tag | Redistributable | Criteria |
|-------|-----|-----------------|----------|
| NDA | `nda` | No | Sources under subscription or NDA |
| Libre | `libre` | Yes | License permits redistribution as a RAG database |
| Restreint | `restreint` | No | Public license that forbids redistribution in RAG form |
| Gris | `gris` | Yes (with caveat) | Redistribution rights uncertain; personal use assumed |

## Options evaluated

### Option A: Single database with a collection column

Add a `collection TEXT` column to the `chunks` table. All data lives in one file.

- **Pros:** Simpler queries (no cross-file merge), single connection, atomic operations.
- **Cons:** Cannot distribute individual collections separately — an NDA corpus would be in the same file as a libre one. Cannot grant file-system-level access control per collection. No way to hand someone a single `.db` file containing only the libre content without exporting/re-creating.

### Option B: One `.db` file per collection (selected)

Each collection is a self-contained `.db` file with its own vec0 index, chunks table, and meta table. A directory of `.db` files constitutes the full corpus.

- **Pros:** Each file is independently portable and redistributable. File-system permissions control access (NDA files stay in a private directory). The producer (openshift workspace) can publish `libre` and `gris` files in a public repository while keeping `nda` files private. No schema change needed — the existing single-file schema works as-is.
- **Cons:** Cross-corpus search requires querying each file and merging results. More file descriptors opened during cross-corpus queries. Slightly more complex server logic.

## Decision

**Option B — one `.db` file per collection.**

The portability and access-control benefits are decisive. The naming convention `<theme>-<level>.db` (e.g. `ia-libre.db`, `docs-nda.db`) encodes both the topic and the redistribution level in the filename.

### Implementation

**Environment variable:** `LORE_DB_DIR` points to a directory of `.db` files. `LORE_DB_PATH` is kept for single-collection backward compatibility. When `LORE_DB_DIR` is set, it takes precedence.

**Module:** `src/lore_mcp/collections.py`

- `discover_collections(db_dir)`: scan directory, parse theme/level from filenames, read chunk/file counts from each `.db`
- `search_collection(db_dir, name, query_embedding, top_k)`: search within a single named collection
- `search_across(db_dir, query_embedding, top_k)`: query every `.db` independently, merge all results by descending score, return global top-k

**MCP tools updated:**

- `search_docs(query, top_k, collection)`: optional `collection` parameter. Without it, searches across all collections.
- `list_indexed_sources(collection)`: optional `collection` parameter.
- `list_collections()`: new tool listing available `.db` files with counts and level tags.

**Ingestion:** `ingest_directory()` accepts `collection` and `db_dir` parameters. The collection name determines the output `.db` filename.

### Cross-corpus merge strategy

The current merge is a simple score-based sort: each collection runs its own KNN search independently, all results are pooled, sorted by descending similarity score, and truncated to `top_k`. This is correct for cosine similarity with the same embedding model across all collections, which is enforced by the `meta` table model validation.

A more sophisticated merge (e.g. weighted by collection priority or Reciprocal Rank Fusion) is not needed at this stage but could be added without changing the interface.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.

## Consequences

- The `.db` file remains the unit of distribution — consumers can receive individual collection files
- NDA and restreint files are never committed to public repositories (enforced by `.gitignore` and convention, not by lore-mcp code)
- The producer (openshift workspace / AI Serving session) is responsible for license classification, NOTICE files, and redistribution decisions — lore-mcp provides the tooling, not the policy
- All collections must use the same embedding model (enforced by `meta` table validation per `.db` file)
