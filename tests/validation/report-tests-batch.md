# Rapport de validation MCP — session "tests mcp"

Dernière mise à jour : 2026-10-06

## Résumé

Session de validation exhaustive du pipeline lore-mcp via les outils MCP.
24 items de backlog identifiés (E12.101-E12.123), 18 corrigés, 3 en cours.
5 tests validés (E2.06, E2.11, E2.12, E2.14, E2.15), 1 partiel (E2.13).

## Tests validés

### E2.06 — Full pipeline via add_recipe ✓
- 21/21 sources, 1505 chunks, 7/7 DoD
- Optimize: ndcg@5=0.66, recall@5=0.67
- Biblio: .json (21 sources), .bib (21 entries), .md ✓
- search_docs score 0.91 sur "open source AI definition"
- Durée: ~10h (PPTX captioning CPU dominant)
- Rapport: tests/validation/report-full-recipe.md

### E2.11 — Code narration unitaire Python ✓
- 3 modules (server.py, store.py, embedder.py), 367 chunks
- search_docs scores >0.89 pour toutes les requêtes
- Narration AST fonctionne (headings fonctions/classes)
- Enrichissement appliqué par défaut (E12.118 corrigé)
- Rapport: tests/validation/report-code-py.md

### E2.12 — Cancel task ✓
- cancel_task arrête un add_source running en ~34s
- Annulation coopérative (check_cancelled aux frontières de phase)
- État propre après annulation
- Rapport: tests/validation/report-cancel-task.md

### E2.14 — Project scan via add_directory ✓
- add_directory("src/lore_mcp", enrich="none", include_pattern="*.py")
- 27/28 sources indexées (856 chunks, 0 erreurs)
- _version.py exclu (trop petit pour produire des chunks)
- search_docs score 0.9177 sur "search_docs function semantic search"
- Valide: E3.42 (narration AST), E12.115, E12.123
- Durée: 99s
- Trace: tests/validation/trace-E2.14-final.md

### E2.15 — Code narration sans enrichissement ✓
- add_source(store.py, enrich="none") → 52 chunks
- Comparé à E2.11 (store.py avec enrich) → 100 chunks (-48%)
- Contenu: narration AST pure (docstring + code), pas de LLM
- enrich="none" fonctionne correctement
- Trace: tests/validation/trace-E2.14-2026-10-06.md (section E2.15)

## Tests partiels

### E2.13 — MCP stability (partiel)
- **MCP stability PASS** ✓ — serveur reste connecté après build terminé/échoué
- E12.113 (stdout isolation) fonctionne
- **Build FAIL** — "no such table: chunks" car preprocess=false sur collection neuve
- E12.122 corrigé (_get_db refuse .db inexistant)
- Test complet (optimize + search immédiat) non validé sur collection neuve
- Retest requis avec collection existante

## Tests non lancés

| Test | Durée estimée | Prérequis | Description |
|------|---------------|-----------|-------------|
| E2.07 | ~10h | — | Full pipeline via add_sources |
| E2.08 | ~12h | — | Full pipeline via add_source unaire |
| E2.09 | ~10h | — | Full pipeline via download |
| E2.10 | ~10h | — | Full pipeline mixte (local + download) |
| E2.16 | ~30 min | — | Scan + enrichissement |

## Bugs identifiés et corrigés (24 items)

### Corrigés (Implémenté, CI green) — 18 items

| ID | Description |
|----|-------------|
| E12.101 | Download vers build_dir (pas orig_dir) |
| E12.102 | Recipe orig_dir fallback |
| E12.103 | add_recipe collection override |
| E12.104 | YouTube video ID (pas "watch") |
| E12.105 | skip_optimize chunk params |
| E12.106 | add_recipe progress reporting |
| E12.107 | URL extension fallback + dotted basenames |
| E12.108 | Sources manquantes du rapport (phase 4) |
| E12.109 | Sources poor indexées par défaut |
| E12.110 | Evaluation balanced round-robin |
| E12.111 | cancel_task coopératif |
| E12.112 | TEI restart self-contained |
| E12.113 | MCP stdout isolation |
| E12.116 | FormatRegistry configs (yaml/toml/Containerfile) |
| E12.117 | CLI build auto-scan preprocess=True |
| E12.118 | enrich="none" désactive enrichissement |
| E12.121 | Config singleton isolation (copy.copy per task) |
| E12.122 | Guard _get_db against empty .db |
| E12.123 | Preprocess→ingest handoff robuste |

### En cours — 3 items

| ID | Description | Bloque |
|----|-------------|--------|
| E12.115 | add_directory MCP tool (core OK, edge cases) | — |
| E12.79 | Upstream contribution Docling PR #4392 | — |
| E12.114 | FormatRegistry class | — |

## Chronologie des runs E2.06

| Run | Sources OK | Problème | Fix appliqué |
|-----|-----------|----------|--------------|
| 1 | 0/21 | Tous "File not found" | E12.101-E12.107 |
| 2 | 9/21 | URL-only, YouTube, PPTX | E12.107-E12.109 |
| 3 | 15/21 | Report incomplet, poor exclus | E12.108-E12.110 |
| 4 | 21/21 ✓ | TEI restart nécessaire | E12.112 |

## Chronologie des runs E2.14

| Run | Sources OK | Problème | Fix appliqué |
|-----|-----------|----------|--------------|
| 1 | 0/28 | Config singleton | E12.121 |
| 2 | 0/28 | Recipe stale + wrong collection | E12.123 |
| 3 | 27/28 ✓ | _version.py trop petit | — |

## Recommandations

### Tests prioritaires à lancer
1. **E2.13 complet** (~5 min) : tester sur collection existante (full-recipe)
2. **E2.16** (~30 min) : scan + enrichissement, débloqué par E2.14
3. **E2.07-E2.10** (~10h chacun) : validation exhaustive des chemins d'ingestion

### Améliorations identifiées (non bloquantes)
- E12.120 : Docling enrichment options study
- E12.100 : HybridChunker hierarchical mode study
- E3.29 : Source identification (DOI, ISBN, URL)
