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
- Multi-collection avec classification licence : E9.01-E9.05 **terminé**
- sqlite-vec confirmé
- Team Topologies : lore-mcp = Platform component, interactions documentées
- Sync cross-workspace documenté dans CLAUDE.md §6

## Multi-collection — implémenté

Prérequis MVP1 openshift **satisfait**. Tout est
mergé sur main.

Implémentation :
- `collections.py` : discover, search single/across, theme/level parsing
- `LORE_DB_DIR` : pointe vers un répertoire de `.db`
- `search_docs(query, top_k, collection)` : recherche cross-corpus ou ciblée
- `list_collections()` : nouveau tool MCP
- Ingestion `collection=` + `db_dir=` : fichier .db déterminé par le nom
- Convention de nommage : `<theme>-<level>.db`
- 101 tests, 87% coverage

## État du projet

### Implémenté

- store.py : SQLite + sqlite-vec (cosine, meta table)
- embedder.py : GPU/API/CPU fallback avec évaluation des capacités
- server.py : FastMCP (search_docs, list_indexed_sources, list_collections), transport stdio + SSE
- ingest.py : preprocessing, chunking, batch indexing, collection mode
- collections.py : multi-collection (discover, search, theme/level)
- 101 tests, 87% coverage

### Contrat d'interface

**MCP tools :**
- `search_docs(query: str, top_k: int = 5, collection: str = "") -> str`
- `list_indexed_sources(collection: str = "") -> str`
- `list_collections() -> str`

**Variables d'environnement :**
- `LORE_DB_PATH` : chemin du fichier .db (mono-collection)
- `LORE_DB_DIR` : répertoire de .db (multi-collection)
- `LORE_MODEL` : modèle d'embedding (défaut: BAAI/bge-m3)
- `LORE_EMBED_MODE` : auto/gpu/api/cpu
- `LORE_API_URL` : endpoint /v1/embeddings
- `LORE_API_MODEL` : nom modèle côté API

**Transport :** stdio (subprocess) ou SSE (HTTP, `--transport sse`)
