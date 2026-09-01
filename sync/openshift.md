# Sync lore-mcp → openshift

> Dernière MàJ : 2026-09-01 (sync 27)
> Source : session lore-mcp
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 12 modules Python, 211 tests
- 9 EPUBs (architecture, code-guide,
  implementation-reference, configuration,
  tutorial, ADRs, ai-guidelines, research,
  quality observations)
- Release tag : v0.1.0-dev

### Backlog par statut

**`Revue`** (27 items) : E0.01-09, E1.01-04,
E2.01-02, E3.01-03, E4.01, E9.01-05

**`Implémenté`** (25 items, en attente validation) :
E6.04-05, E10.01-04, E10.06-07, E10.09-21, E10.23,
E11.01

**`À faire`** (22 items) :
E2.03, E3.04-05, E4.02-04, E5.01-05, E6.01-03,
E7.01-03, E10.05, E10.08, E10.22

### Contrat d'interface

**MCP tools :**
- `search_docs(query, top_k=5, collection="")` —
  recherche sémantique (cross-corpus ou ciblée)
- `list_indexed_sources(collection="")` — fichiers
  indexés avec comptage
- `list_collections()` — collections disponibles

**CLI subcommands :**
- `lore-mcp` — serveur MCP (stdio ou `--transport sse`)
- `lore-mcp eval --db ... --config ...` — évaluation RAG
- `lore-mcp optimize --config ... --source-dir ...` — optimisation
- `lore-mcp build manifest.yaml --config ... --docs-dir ... --output-dir ...` — build complet

**Variables d'environnement :**
- `LORE_DB_PATH` : fichier .db (mono-collection)
- `LORE_DB_DIR` : répertoire de .db (multi-collection)
- `LORE_MODEL` : modèle d'embedding (défaut: nomic-embed-text-v2-moe)
- `LORE_EMBED_MODE` : `builtin` (défaut), `builtin:gpu`, `builtin:cpu`, `api`
- `LORE_API_URL` : endpoint /v1/embeddings
- `LORE_API_MODEL` : nom modèle côté API
- `LORE_API_VERIFY` : vérification SSL (true/false)
- `LORE_API_CA_BUNDLE` : chemin CA
- `LORE_CHUNK_SIZE` : taille chunk (défaut: 1024)
- `LORE_CHUNK_OVERLAP` : overlap (défaut: 128)
- `LORE_BATCH_SIZE` : taille batch embedding (défaut: 64)
- `LORE_LLM_URL` : endpoint juge LLM (pour RAGAS)
- `LORE_LLM_MODEL` : modèle juge (défaut: granite-8b-instruct)

**Config YAML** (clé `embedding:`, pas `models:`) :
```yaml
embedding:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: builtin
judge:
  model: granite-8b-instruct
  api_url: http://localhost:11434/v1
metrics: [score_spread, source_diversity, mrr]
optimize:
  chunk_sizes: [512, 1024, 2048]
  chunk_overlaps: [64, 128]
  top_ks: [3, 5, 10]
  num_questions: 50
```

**Transport :** stdio (subprocess) ou SSE (HTTP)

### Fonctionnalités clés

- Multi-collection (`LORE_DB_DIR`, nommage
  `<theme>-<level>.db`)
- Métadonnées biblio (table sources, manifeste
  YAML, .json/.bib/.md en sortie)
- AutoRAG multi-modèle (`--config` avec
  plusieurs modèles d'embedding)
- Évaluation 3 niveaux (embedding, retrieval, LLM)
- Build workflow complet (manifest → optimized
  .db + metadata + report)
- Résilience API (retry backoff, batch reduction,
  fail fast)
- `Embedder.unload()` avec gc.collect()
- RAGAS 0.4.3 stub (langchain-community sunset)
- Modèle par défaut : Nomic v2 MoE (Level 2,
  Apache 2.0). ADR-005.

## Historique des demandes

Toutes les demandes reçues ont été traitées en
items de backlog conformément aux règles
cross-workspace. Statuts actuels visibles dans
la section backlog ci-dessus.

### RAGAS scoring (sync 25-26)
**E10.15 corrigé** — evaluate_retrieval appelle
_score_with_ragas quand métriques RAGAS demandées
+ juge configuré. compute_retrieval_metrics
remplace _score_retrieval (ajoute mrr).
Régression --config corrigée (E10.21).
214 tests.

### Précision RAGAS run 3 (sync 27)
**E10.15 repassé à Prêt** — retrieval metrics OK
(hit/mrr/word_overlap). Embedding metrics et
RAGAS metrics non transmis du config au pipeline
(run_optimize/run_build ne passent pas metrics/
judge au evaluate_retrieval). --verbose non câblé.
