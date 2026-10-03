# Sync lore-mcp → openshift

> Dernière MàJ : 2026-10-03 (sync 46)
> Source : session lore-mcp 1-3 oct
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 17 modules Python (dont preprocess/), 630 tests
- Branche active : feat/E12-preprocessing-tool
- Release tag : v0.1.0
- 14 outils MCP (add_source, add_sources, add_recipe, search_docs, list_indexed_sources, list_collections, remove_source, start_eval, start_optimize, get_service_status, get_version, lint_source, list_tasks, get_task_status, cancel_task, list_pipeline_state, purge_pipeline_state)

### Implémenté cette itération (1-3 oct)

**Architecture MCP** :
- E3.19 XDG directories + database.dir + default_collection + lore-mcp init
- E3.18 Pipeline unifié add_source/add_sources/add_recipe (start_build/preprocess/enrich supprimés)
- E3.14 Incremental ingest (ingest_source, purge_absent=False)
- E3.16 DB connection lifecycle (health check, cleanup services)
- E3.33 Version command (hatch-vcs + get_version MCP)
- E3.30 Format detection (puremagic + heuristiques texte)
- E3.35 Heuristic text detection (HTML avec whitespace)
- E3.27 Collection wildcard (fnmatch *, ?, [seq])
- E3.34 orig_dir in recipe
- E3.36 Task progress reporting (phase info dans get_task_status)
- E3.37 Bibliographic index (detail/bibtex/json/markdown)
- E3.38 Fix embedder restart after preprocess
- E3.28 add_source by URL (via preprocess_sources)
- E3.32 Test .db fixtures versionnées
- E1.05 INNER JOIN (fix orphan vectors)
- E3.26 Options naming (chunking.size/overlap)

**Validation par format (E3.20-25)** :
- Markdown: 23 chunks, 20s ✓
- HTML: 122 chunks, 10s ✓
- PDF: 129 chunks, 156s ✓
- XLSX: 32 chunks, 117s ✓
- CSV: 6 chunks, 19s ✓
- Image: 5 chunks, 562s (VLM captioning) ✓
- Video: 149 chunks, 2226s (STT + frames) ✓

**Services auto-start/stop confirmés** : TEI, Granite Vision, Molmo, STT Canary, Granite 8B (remote)

**Bugs corrigés** :
- add_source écrasait la .db (run_build → preprocess+ingest)
- Pre-filter FTS bypassait les filtres metadata
- TEI timeout après preprocess (cleanup services + health check)
- XLSX UTF-8 decode (errors=replace)
- collection_db flat vs nested priority
- Prep file search multi-locations

### Groomé (études, pas d'implémentation)

- E12.100 HybridChunker hierarchical vs parent-child
- E3.29 Source identification (DOI/ISBN/canonical cascade)
- E3.31 Structured data to knowledge

### Prochaines étapes

- Session dédiée implémentation : E3.29, E3.31, E12.100
- Session dédiée tests MCP : validation exhaustive tous formats avec toutes options
- PR Docling #4392 en attente merge
