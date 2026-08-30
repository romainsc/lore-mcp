# Sync lore-mcp → openshift

> Dernière MàJ : 2026-08-30
> Source : session lore-mcp
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## Accusé de réception

Rattachement cross-workspace reçu et appliqué
(2026-08-30).

Décisions appliquées :
- Licence code : AGPL-3.0-or-later (migration depuis GPL-3.0)
- Licence études : CC-BY-SA 4.0
- Multi-collection avec classification licence : backlog E9.01-E9.05
- sqlite-vec confirmé
- Team Topologies : lore-mcp = Platform component, interactions documentées
- Sync cross-workspace documenté dans CLAUDE.md §6

Multi-collection prérequis MVP1 openshift : intégré
au backlog avec specs détaillées (LORE_DB_DIR,
search_docs collection param, list_collections,
ingestion --collection, nommage <theme>-<level>.db).

## État du projet

### Implémenté (MVP)

- store.py : SQLite + sqlite-vec (cosine, meta table)
- embedder.py : GPU/API/CPU fallback avec évaluation des capacités
- server.py : FastMCP (search_docs, list_indexed_sources), transport stdio + SSE
- ingest.py : preprocessing, chunking, batch indexing
- 85 tests, 86% coverage

### Contrat d'interface

**MCP tools :**
- `search_docs(query: str, top_k: int = 5) -> str`
- `list_indexed_sources() -> str`

**Variables d'environnement :**
- `LORE_DB_PATH` : chemin du fichier .db
- `LORE_MODEL` : modèle d'embedding (défaut: BAAI/bge-m3)
- `LORE_EMBED_MODE` : auto/gpu/api/cpu
- `LORE_API_URL` : endpoint /v1/embeddings
- `LORE_API_MODEL` : nom modèle côté API

**Transport :** stdio (subprocess) ou SSE (HTTP, `--transport sse`)
