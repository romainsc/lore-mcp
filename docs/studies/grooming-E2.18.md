# Grooming E2.18 — Modular CI

## Problème

Un seul job `test` monolithique. Un test qui
échoue → "all jobs have failed" → pas de
visibilité sur quel module est cassé.

## Fix

Split en 5 jobs parallèles. Chaque job installe
les deps et exécute son sous-ensemble de tests.
`fail-fast` implicitement false (pas de matrice).

| Job | Tests | Dep système |
|-----|-------|-------------|
| `unit` | store, embedder, ingest, config, recipe, narrate, format_registry, collections, progress, dedup, pii, lint, validate, chunk_config, parent_child, model_exposure, build_config, smart_batch, batch_size, unload_gc, resource_cleanup | Non |
| `preprocess` | preprocess, parse, enrich, enrich_prompts, checkpoint, sequential_phases, service | tesseract-ocr |
| `build` | build, build_preprocess, pipeline_wiring, metadata, optimize_manifest, integration | tesseract-ocr |
| `server` | server, mcp_tools, get_config, task_manager | Non |
| `eval` | eval, eval_report, heading_eval, autorag_multimodel, ragas_explicit, ragas_guard, ragas_scoring, ragas_stub, api_resilience, per_model_verify_ssl, verify_ssl | Non |

## DoD

- 5 jobs dans .github/workflows/test.yml
- Chaque job exécute son sous-ensemble
- Un job fail ne bloque pas les autres
- CI badge reste fonctionnel
- Tous les fichiers test couverts (aucun oublié)
- CI green sur les 5 jobs
