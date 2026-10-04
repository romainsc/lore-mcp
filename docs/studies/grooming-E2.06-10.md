# Grooming E2.06-E2.10 — Full pipeline validation

## Context

Five validation tests exercising the complete pipeline with
recipe-test-redist.yaml (21 sources, all formats), all features
enabled. Same corpus, same validation criteria, five different
ingestion paths.

## Configuration (all tests)

- Embedding: nomic-embed-text-v2-moe via TEI API (port 8082)
- Chunking: 1024/128 via HybridChunker
- Parse: Tesseract OCR fra+eng, Docling multi-format
- Caption: granite-vision primary + molmo-7b additional, judge granite-8b
- Enrich: context + qa + meta via granite-8b (concurrency 8)
- STT: canary-1b-v2 (port 8093)
- Frames: scene strategy (threshold 0.3)
- Reranking: granite-embedding-reranker-english-r2

## Common DoD

1. Task completes without error
2. .db exists, expected source count in sources table
3. Each source has chunk_count > 0
4. Metadata matches recipe declarations
5. generate_all() produces .json, .bib, .md
6. search_docs returns results
7. list_indexed_sources(detail=True) shows all sources
8. Duration recorded per phase

## E2.06 — add_recipe

- Entry: add_recipe(recipe, collection="full-recipe")
- Recipe autoporteuse (orig_dir in recipe)
- 21 sources, all from orig_dir (pre-downloaded)
- Report: tests/validation/report-full-recipe.md

## E2.07 — add_sources

- Entry: add_sources(JSON, collection="full-add_sources", orig_dir=...)
- JSON built from recipe YAML
- 21 sources, all from orig_dir
- Comparison with E2.06 chunk counts
- Report: tests/validation/report-full-add_sources.md

## E2.08 — add_source (unary)

- Entry: 21x add_source(file, collection="full-add_source_unary", ...)
- Sequential, poll each to completion
- Per-source timing
- Comparison with E2.06/E2.07
- Report: tests/validation/report-full-add_source_unary.md

## E2.09 — download (no orig_dir)

- Entry: add_recipe or add_sources, 18 URL sources only
- No orig_dir, --allow-download
- Tests download path end-to-end
- Documents E12.101 behavior (download destination)
- Report: tests/validation/report-full-download.md

## E2.10 — mixed (orig_dir + download)

- Entry: add_recipe, full 21 sources
- orig_dir contains only 3 local files (copied to temp)
- 18 URL sources downloaded
- Verifies orig_dir integrity (hash before/after)
- Report: tests/validation/report-full-mixed.md

## Duration estimate

- E2.06: ~60-90 min
- E2.07: ~60-90 min
- E2.08: ~90-120 min
- E2.09: ~70-100 min
- E2.10: ~70-100 min
- Total: ~6-8 hours
