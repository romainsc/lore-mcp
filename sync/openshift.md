# Sync lore-mcp → openshift

> Dernière MàJ : 2026-10-02 (sync 45)
> Source : session lore-mcp 1-2 oct
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 17 modules Python (dont preprocess/), 630 tests
- Branche active : feat/E12-preprocessing-tool
- Release tag : v0.1.0-dev
- 14 outils MCP (était 17 — 3 supprimés)

### Backlog — itération 1-2 oct

**`Implémenté`** cette itération :
- E3.14 Chemin d'ingest incrémental : ingest_source() lit params .db
- E3.16 Connexion .db : connexions séparées pour écriture, invalidation
- E3.17 Validation exhaustive : 17/17 outils MCP testés (cycle add/search/remove)
- E1.05 MVP1 Store : LEFT JOIN → INNER JOIN (fix orphan vectors NULL)
- E3.19 Répertoires XDG : data_dir, default_collection, _get_db(collection), lore-mcp init
- E3.30 Détection format : puremagic (MIT, pure Python) par contenu
- E3.18 Pipeline unifié : add_source (preprocess+ingest, tous formats), add_sources (JSON batch), add_recipe (YAML). start_build/start_preprocess/start_enrich supprimés
- E12.79 PR Docling #4392 : review adressée, CI verte, en attente merge

**Groomés** cette itération :
- E3.20-25 Validation par format (markdown, HTML, PDF, vidéo, image, CSV)
- E3.26 Options naming + tiered help
- E3.27 Collection wildcard (fnmatch)
- E3.28 add_source by URL
- E3.29 Source identification (DOI/ISBN/canonical)
- E3.31 Structured data to knowledge
- E3.32 Test .db fixtures versionnées

### Résultats clés

**Refactoring MCP majeur** :

- **Pipeline unifié** (E3.18) : `add_source` = preprocess + ingest pour tout format. `add_sources` (JSON) et `add_recipe` (YAML) pour le batch. `start_build`/`start_preprocess`/`start_enrich` supprimés — c'étaient des détails d'implémentation, pas des intentions utilisateur
- **Collection-based** (E3.19) : `_get_db(collection)` remplace `_single_db`/`_is_multi_collection`. Résolution XDG par défaut. `lore-mcp init` génère config bootstrap
- **Format detection** (E3.30) : puremagic détecte par contenu (magic bytes), pas seulement par extension. DOCX/PPTX/EPUB disambiguées nativement
- **Source identification** (E3.29, groomé) : cascade DOI → ISBN → canonical URL → file path. Pattern ChromaDB/LlamaIndex confirmé

**Bugs corrigés** :
- add_source écrasait la .db (E3.14)
- Orphan vectors causaient crash reranker (E1.05)
- Connexion stale après add/remove (E3.16)
- charset-normalizer détectait UTF-16 sur markdown avec NUL (CI fix)

### Demandes

Aucune nouvelle demande.

### Prochaines étapes

- E3.20-25 : validation par format via MCP LLM
- E3.28 : add_source by URL
- E3.29 : implémentation source identification
- E3.26 : options naming et tiered help
