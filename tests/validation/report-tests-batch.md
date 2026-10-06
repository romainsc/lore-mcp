# Rapport de validation MCP — session "tests mcp"

## Résumé

Session de validation exhaustive du pipeline lore-mcp via les outils MCP.
21 items de backlog identifiés (E12.101-E12.121), 13 corrigés, 5 en cours.
3 tests validés (E2.06, E2.11, E2.12), 3 échoués (E2.14, E2.15, E2.13 partiel).

## Tests validés

### E2.06 — Full pipeline via add_recipe ✓
- 21/21 sources, 1505 chunks, 7/7 DoD
- Optimize: ndcg@5=0.66, recall@5=0.67
- Biblio: .json (21 sources), .bib (21 entries), .md ✓
- search_docs score 0.91 sur "open source AI definition"
- Durée: ~10h (PPTX captioning CPU dominant)

### E2.11 — Code narration unitaire Python ✓
- 3 modules (server.py, store.py, embedder.py), 367 chunks
- search_docs scores >0.89 pour toutes les requêtes
- Narration AST fonctionne (headings fonctions/classes)
- Note: enrichissement appliqué par défaut (bug E12.118)

### E2.12 — Cancel task ✓
- cancel_task arrête un add_source running en ~34s
- Annulation coopérative (check_cancelled aux frontières de phase)
- État propre après annulation

## Tests échoués

### E2.14 — Project scan via add_directory ✗
- **Blocker**: E12.115 + E12.121
- Symptôme: 28 fichiers scannés mais tous "File not found"
- Cause racine: config singleton muté dans le thread TaskManager, subprocess ne reçoit pas orig_dir
- Fonctionne en appel Python direct, échoue via MCP
- **Fix requis**: E12.121 (copy.copy(cfg) par tâche)

### E2.15 — Code narration sans enrichissement ✗
- **Blocker**: E12.118 incomplet
- Symptôme: enrich="none" n'a aucun effet sur add_source
- Chunks quasi identiques (363 vs 367), contenu enrichi visible
- E12.118 marqué Implémenté mais ne couvre pas add_source
- **Fix requis**: vérifier le wiring de enrich="none" dans add_source

### E2.13 — MCP stability (partiel)
- **MCP stability PASS** ✓ — serveur reste connecté après build terminé/échoué
- E12.113 (stdout isolation) fonctionne
- **Build FAIL** — "no such table: chunks" car preprocess=false sur collection neuve
- Test complet (optimize + search immédiat) non validé

### E2.16 — Scan + enrichissement ✗
- **Bloqué** par E2.14

## Bugs identifiés dans cette session (total cumulé)

### Corrigés (Implémenté, CI green)

| ID | Description |
|----|-------------|
| E12.101 | Download vers build_dir |
| E12.102 | Recipe orig_dir fallback |
| E12.103 | add_recipe collection override |
| E12.104 | YouTube video ID |
| E12.105 | skip_optimize chunk params |
| E12.106 | add_recipe progress reporting |
| E12.107 | URL extension fallback + dotted basenames |
| E12.108 | Sources manquantes du rapport |
| E12.109 | Sources poor indexées par défaut |
| E12.110 | Evaluation balanced round-robin |
| E12.111 | cancel_task coopératif |
| E12.112 | TEI restart self-contained |
| E12.113 | MCP stdout isolation |
| E12.116 | FormatRegistry configs (yaml/toml/Containerfile) |
| E12.117 | CLI build auto-scan preprocess=True |

### À corriger (bloquent les tests)

| ID | Sévérité | Description | Tests bloqués |
|----|----------|-------------|---------------|
| **E12.121** | **Critique** | Config singleton: `prep_cfg = cfg` est une référence. Concurrent tasks mutent le même objet. Fix: `copy.copy(cfg)` par tâche + orig_dir dans recipe YAML | E2.14, E2.16, potentiellement E2.07-E2.10 |
| **E12.115** | **Critique** | add_directory: orig_dir non propagé au subprocess (conséquence de E12.121) | E2.14, E2.16 |
| **E12.118** | **Majeur** | enrich="none" ne fonctionne pas pour add_source (seulement add_sources/add_recipe) | E2.15 |

### À faire (non bloquants immédiatement)

| ID | Description |
|----|-------------|
| E12.120 | Docling enrichment options study |
| E12.100 | HybridChunker hierarchical mode study |

## Tests non lancés (en attente des corrections)

| Test | Durée estimée | Dépend de |
|------|---------------|-----------|
| E2.07 | ~10h | — (prêt, mais inutile tant que E12.121 n'est pas corrigé car même bug potentiel sur add_sources) |
| E2.08 | ~12h | — |
| E2.09 | ~10h | — |
| E2.10 | ~10h | — |
| E2.14 | ~10 min | E12.115 + E12.121 |
| E2.15 | ~2 min | E12.118 |
| E2.16 | ~30 min | E2.14 |

## Recommandations pour la session d'implémentation

### Priorité 1 : E12.121 — Config singleton isolation
C'est la cause racine de E12.115 et potentiellement de tous les outils MCP qui modifient la config. Fix :
1. `import copy; task_cfg = copy.copy(cfg)` dans chaque `_do_*` closure
2. OU passer orig_dir via la recipe YAML au lieu de config.orig_dir
3. Tester avec `add_directory` sur `src/lore_mcp/` et vérifier 28/28 sources indexées

### Priorité 2 : E12.118 — enrich="none" dans add_source  
Vérifier le code de `add_source._do_add()` — le paramètre `enrich` n'est probablement pas traité pour "none". Comparer avec `add_sources._do_adds()` où ça fonctionne.

### Priorité 3 : E2.13 complet
Le test E2.13 nécessite une collection avec des données (pas preprocess=false sur une collection neuve). Utiliser la collection `full-recipe` existante ou un build complet.

### Vérification après corrections
1. `add_directory src/lore_mcp --collection test --enrich none` → 28 sources indexées
2. `add_source server.py --collection test2 --enrich none` → chunks sans enrichissement
3. `add_recipe recipe.yaml --collection test3 --optimize true` → MCP reste connecté + search immédiat OK
