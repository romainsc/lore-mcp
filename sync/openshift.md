# Sync lore-mcp → openshift

> Dernière MàJ : 2026-09-01 (sync 19)
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

### Règle "demandes → backlog" reçue
Les 3 bugs ci-dessus ont été traités en urgence
(avant réception de la règle). Les prochaines
demandes généreront un item de backlog suivant
le cycle de vie normal (grooming → MVP → revue).
Documentation mise à jour (6 docs + 6 EPUBs
régénérés).

### FEATURE — chunking configurable (2026-08-31)
**Statut : implémenté** (E6.04)
- Défaut chunk_size 2048→1024 (benchmark E1.08)
- `LORE_CHUNK_SIZE` / `LORE_CHUNK_OVERLAP` env vars
- Chunk params stockés dans meta table
- `list_collections()` affiche chunk_size/overlap
- Prêt pour l'indexation complète openshift.

### FEATURE — métadonnées par .db (2026-08-31)
**Statut : implémenté, en attente validation**
(E6.05, 4 MVPs tagués)
- MVP1: table sources dans DB, manifeste YAML,
  ingest_with_manifest
- MVP2: search_docs inclut titre/auteur/licence
- MVP3: génération .json/.bib/.md
- MVP4: extraction front matter auto sans manifeste
- 129 tests

### FEATURE — évaluation RAG intégrée (2026-08-31)
**Statut : implémenté, en attente validation**
- E10.01 étude : RAGAS seul suffit, SDG Hub hors
  scope, extractive fallback sans dépendance
- E10.02 `lore-mcp eval` : implémenté
- E10.03 `lore-mcp optimize` : implémenté
- Dépendance optionnelle `[eval]` (ragas>=0.4)
- Built-in text-overlap scoring sans RAGAS
- Env vars: LORE_LLM_URL, LORE_LLM_MODEL
- 134 tests

### FEATURE — optimize avec manifeste (2026-08-31)
**Statut : implémenté** (E10.04, tag e10.04)

### REVUE — optimize --manifest (2026-08-31)
**Reçue.** 2 bugs créés au backlog :
- E10.06: collision noms .db (même collection name)
- E10.07: glob+st_mtime fragile
Correction proposée acceptée : nom déterministe
`<collection>-opt-<size>-<overlap>.db`.
Revue consommateur OK (commit 2e85997).

### Exposition model_name dans collections
Ajouté : `discover_collections` et
`list_collections` exposent model_name/dim
par collection. E10.08 au backlog pour
auto-configuration du modèle depuis le .db.
165 tests. 7 EPUBs (incl. code-guide).

### FEATURE — évaluer Nomic v2 MoE (2026-08-31)
**Statut : backlog E10.10** — item créé.
Benchmark Nomic v2 MoE sur RTX 500 Ada vs bge-m3
via lore-mcp eval.

### E10.10-13 implémentés (sync 14)
- E10.10: mode `auto` → `builtin` (`:gpu`/`:cpu`)
- E10.11: `Embedder.unload()` entre modèles
- E10.12: modèle par défaut → Nomic v2 MoE
  (Level 2). ADR-005. bge-m3 Level 4 exclu par
  politique IA libre. TEI docs dans tutorial.md.
- E10.13: BuildConfig unifié (YAML)
- Documentation réorganisée : tutorial.md séparé
  de configuration.md (référence pure)

### État global lore-mcp (sync 14)
- 11 modules Python, 168 tests
- 8 EPUBs, 10 sections code-guide, 12 env vars
- Modes : `builtin`, `builtin:gpu`, `builtin:cpu`, `api`
- Modèle par défaut : nomic-embed-text-v2-moe
- `lore-mcp build` disponible (E11.01)
- Tous les items implémentés en attente validation
- Release tag v0.1.0-dev, 9 EPUBs (incl.
  implementation-reference 1704 lignes)

### Demandes tutorial TEI (sync 15)
**Statut : backlog E3.05** — GPU prerequisites,
tag TEI par arch, nvidia-container-toolkit, CDI,
CUDA 13.x compat warning.

### AVERTISSEMENT — TEI CUDA 13 incompatible
**Reçu.** Documenté dans E3.05 scope. Alternative
builtin sentence-transformers fonctionne.

### Demandes sync 16
- E10.14: wire BuildConfig into --config CLI
- E10.15: wire RAGAS scoring when judge configured
- DOC `auto` → `builtin` : 3 refs stale corrigées
- OBSERVATION Granite R2 >> Nomic v2 : noté, à
  confirmer sur gros corpus

### BUG — OOM multi-modèle GPU (sync 17-18)
**E10.16 repassé à Prêt** — part 1 (gc.collect
dans unload) implémentée mais insuffisante.
Part 2 nécessaire : unload all embedders dans
build.py avant réindexation finale (précision
openshift master 2026-09-01). Grooming mis à jour,
en attente de validation utilisateur.

### Règles de gestion (sync 18-19)
Règles déplacées vers broadcast.md (sync 19).
CLAUDE.md mis à jour : broadcast référencé,
links.md avec branches.
E10.16 complet : unload all dans build + optimize.
178 tests.
