# Sync lore-mcp → openshift

> Dernière MàJ : 2026-08-31 (sync 4)
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
- Règles cross-workspace appliquées : cycle de vie
  item (grooming → MVPs → clôture), principes agile
  (P10 simplicité, P3 livrer fréquemment, P2
  répondre au changement), posture Platform (CLAUDE.md §12)
- Besoins grooming E1.04 intégrés au backlog :
  multi-backend E7.01/E7.03, int8 quantification
  E5.05, hybrid search E5.03/E5.04, CLI index
  E4.04, dépôt .db E4.05, plaidoyer gris E4.06
- Revue formelle des items réalisés : 18 findings
  corrigés (doc sync après E9 et migration AGPL)

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
- server.py : MCPServer v2 (search_docs, list_indexed_sources, list_collections), transport stdio + SSE
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
- `LORE_API_VERIFY` : vérification SSL (true/false, défaut: true)
- `LORE_API_CA_BUNDLE` : chemin CA personnalisé

**Transport :** stdio (subprocess) ou SSE (HTTP, `--transport sse`)

## Réponse aux demandes

### BUG — model_dim crash en mode API
**Statut : corrigé** (commit 422a9a2)
Détection de la dimension via appel API test.

### BUG — SSL certificate verify failed
**Statut : corrigé** (commit 422a9a2)
Ajout de `LORE_API_VERIFY` et `LORE_API_CA_BUNDLE`.

### BUG — incompatibilité MCP SDK v2
**Statut : corrigé** (commit 422a9a2)
Migration FastMCP → MCPServer, contrainte `mcp>=2.0`.
