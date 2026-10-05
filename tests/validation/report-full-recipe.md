# E2.06 Final report — add_recipe (optimize=true)

## Task
- Preprocess task: e1fa3b0e (21/21 ok, failed at TEI start)
- Indexing task: 8cabbd10 (preprocess=false, resume)
- Total duration: ~10h (9h38 preprocess + TEI fix + ~15 min optimize/index)
- Status: **completed — 21/21 sources**

## Configuration
- Embedding: nomic-ai/nomic-embed-text-v2-moe via TEI API
- Chunking: 1024/128 (config), **optimized to 2048/64**
- Parse: Tesseract OCR fra+eng, Docling multi-format
- Caption: granite-vision (primary) + molmo-7b (additional), judge granite-8b
- Enrich: context + qa + meta via granite-8b (concurrency 8)
- STT: canary-1b-v2
- Frames: scene strategy
- Reranking: granite-embedding-reranker-english-r2
- Optimize: **enabled**

## Timing (estimated from monitoring)
- Phase 1 (parse + STT): ~2h30 (21 sources, 3 YouTube videos)
- Phase 2 (granite-vision): ~4h (PPTX dominant + videos)
- Phase 2 (molmo-7b): ~2h30
- Phase 3 (enrich): ~20 min
- TEI restart (E12.112): ~10 min manual fix
- Optimize + indexing: ~15 min
- **Total: ~10h**

## Optimization results
- Best config: chunk_size=2048, overlap=64, top_k=10
- NDCG@5: 0.6562
- Recall@5: 0.6727
- MRR: 0.6598
- Source diversity: 0.002
- Result diversity: 0.0

## DoD validation

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Task completes without error | ✓ (after TEI restart) |
| 2 | 21/21 sources in DB | **✓** |
| 3 | Each source has chunks > 0 | ✓ (1505 total) |
| 4 | Metadata matches recipe | ✓ (21 sources with title, lang, author, license, date, url) |
| 5 | Biblio .json produced | ✓ (7664 bytes, 21 sources) |
| 5 | Biblio .bib produced | ✓ (5206 bytes, 21 BibTeX entries) |
| 5 | Biblio .md produced | ✓ (4635 bytes) |
| 6 | search_docs returns results | Deferred (MCP reconnect needed) |
| 7 | list_indexed_sources detail | Deferred (MCP reconnect needed) |

## All 21 sources

| Source | Format | Lang |
|--------|--------|------|
| 2606.md | HTML (arxiv) | eng |
| 623da898-en.md | PDF | fra |
| DUDH_2008.md | Image OCR | fra |
| OECD-LEGAL-0449.md | HTML | fra |
| Reunion-Parents...md | PPTX | fra |
| S-GEN-UNACT-2021-PDF-E.md | PDF | eng |
| T3UKZGEXbVk.md | Video (YouTube) | fra |
| WYszRcHzqw8.md | Video (YouTube) | fra |
| aout-2026.md | XLSX | fra |
| eEBv0STiYhI.md | Audio (YouTube) | eng |
| free-sw.en.md | HTML | eng |
| fsf-is-working-on-freedom-in-machine-learning-applications.md | HTML | eng |
| governing_ai_for_humanity_final_report_en.md | PDF | eng |
| jl42g3kh0r9f9c6kj79lr2ft7mc4.md | DOCX | fra |
| l-osi-publie-une-definition-de-l-ia-opensource-mais-pas-trop.md | HTML | fra |
| open-source-ai-definition.md | HTML | eng |
| open-weights.md | HTML | eng |
| pexels-photo-33121483.md | Image (photo) | eng |
| test-data-sample.md | CSV | eng |
| test-markdown-sample.md | MD | eng |
| worldcup.md | JSON | fra |

## Bug fixes verified (cumulative across all runs)

| Bug | Status |
|-----|--------|
| E12.101 — Download to build_dir | ✓ Implémenté |
| E12.102 — Recipe orig_dir | ✓ Implémenté |
| E12.103 — Collection override | ✓ Implémenté |
| E12.104 — YouTube URL collision | ✓ Implémenté |
| E12.105 — Wrong chunk params | ✓ Implémenté |
| E12.106 — Progress reporting | ✓ Implémenté (visible: "Preprocessing", "Optimizing", "Indexing") |
| E12.107 — URL extension fallback | ✓ Implémenté (21/21, including 2606.03019v1 + 3 YouTube) |
| E12.108 — Missing from report | ✓ Implémenté (21/21 in report) |
| E12.109 — Poor sources indexed | ✓ Implémenté (worldcup + aout-2026 = ok) |
| E12.110 — Eval balanced | ✓ Implémenté |

## Issues encountered during validation

| Bug | Description |
|-----|-------------|
| E12.112 | TEI fails to start after long VLM phase (/tmp/is-logs/ cleaned by tmpfiles) |

## Comparison across runs

| Metric | Run 1 (fail) | Run 2 (dry) | Run 3 (15/21) | Run 4 (21/21) |
|--------|-------------|-------------|---------------|---------------|
| Sources | 0/21 | 9/21 | 15/21 | **21/21** |
| Chunks | 0 | 2110 | 1191 | 1505 |
| Duration | 11s | 5h56 | 6h03 | ~10h |
| Optimize | no | no | yes | yes |
| Bugs found | 4 | 3 | 0 (residual) | 1 (E12.112) |
