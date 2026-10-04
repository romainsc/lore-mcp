# E2.06 Full run report — add_recipe (avec optimize)

## Task
- Task ID: 4251c05f
- Start: 2026-10-04 10:13
- End: 2026-10-04 16:18 (MCP disconnected at completion)
- Duration: ~21771s (~6h03)
- Status: **completed — 15/21 sources**

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
- Phase 1 (parse): ~10 min (17/21 sources, 4 not found)
- Phase 2 (granite-vision): ~90 min (PPTX dominant)
- Phase 2 (molmo-7b): ~210 min (3h30, PPTX CPU 7B)
- Phase 3 (enrich): ~20 min
- Optimize: ~15 min
- Indexing + metadata: ~5 min
- **Total: ~6h03**

## Optimization results
- Best config: chunk_size=2048, overlap=64, top_k=3
- NDCG@5: 0.7786
- Recall@5: 0.86
- MRR: 0.7667
- Hit rate: 0.86
- Word overlap: 0.6697

## DoD validation

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Task completes without error | ✓ |
| 2 | Sources in DB | **15/21** ⚠️ (4 errors) |
| 3 | Each source has chunks > 0 | ✓ (1191 total) |
| 4 | Metadata matches recipe | To verify (MCP disconnected) |
| 5 | Biblio .json/.bib/.md produced | ✓ (5735 + 3870 + 3542 bytes) |
| 6 | search_docs returns results | Not tested (MCP disconnected) |
| 7 | list_indexed_sources detail | Not tested (MCP disconnected) |

## Per-source results

### OK (15/21)
| Source | Format |
|--------|--------|
| test-markdown-sample.md | MD (file:) |
| test-data-sample.csv | CSV (file:) |
| DUDH_2008.png | Image (file:) |
| free-sw.en.html | HTML |
| open-source-ai-definition.html | HTML |
| l-osi-publie-une-definition-de-l-ia-opensource-mais-pas-trop.html | HTML |
| fsf-is-working-on-freedom-in-machine-learning-applications.html | HTML |
| open-weights.html | HTML |
| OECD-LEGAL-0449.html | HTML |
| 623da898-en.pdf | PDF |
| governing_ai_for_humanity_final_report_en.pdf | PDF |
| S-GEN-UNACT-2021-PDF-E.pdf | PDF |
| jl42g3kh0r9f9c6kj79lr2ft7mc4.docx | DOCX |
| Reunion-Parents...pptx | PPTX |
| pexels-photo-33121483.jpeg | Image |

### Error (4/21) — E12.107 residual
| Source | File exists | Issue |
|--------|-------------|-------|
| 2606.03019v1.html | ✓ | URL basename truncated at first dot |
| eEBv0STiYhI.webm | ✓ | YouTube video ID, extension not matched |
| WYszRcHzqw8.mkv | ✓ | YouTube video ID, extension not matched |
| T3UKZGEXbVk.mkv | ✓ | YouTube video ID, extension not matched |

### Missing from report (2/21) — E12.108
| Source | Status |
|--------|--------|
| aout-2026.xlsx | Not in report (E12.108 residual?) |
| worldcup.json | Not in report (E12.108 residual?) |

## Bug fixes verified (cumulative)
| Bug | Status |
|-----|--------|
| E12.102 — Recipe orig_dir | ✓ Fixed |
| E12.103 — Collection override | ✓ Fixed |
| E12.104 — YouTube URL collision | ✓ Fixed (unique IDs) |
| E12.105 — Wrong chunk params | ✓ Fixed (optimize ran correctly) |
| E12.106 — Progress reporting | ✓ Fixed ("Preprocessing sources" visible) |
| E12.107 — URL extension fallback | Partial (15/21 vs 9/21 before) |
| E12.108 — Missing from report | Partial (still 2 missing) |

## Remaining issues
- E12.107 residual: 4 sources not found (arxiv dot-in-name, YouTube video IDs)
- E12.108 residual: 2 sources (XLSX, JSON) missing from report
- MCP server disconnected at end of build — search/list validation deferred
- DoD criteria 4, 6, 7 not validated (need MCP restart)

## Comparison with dry-run
| Metric | Dry-run | Full run |
|--------|---------|----------|
| Sources | 9/21 | 15/21 |
| Chunks | 2110 | 1191 |
| Duration | 5h56 | 6h03 |
| Optimize | no | yes (2048/64) |
| Chunk config | 1024/128 | 2048/64 (optimized) |

Note: fewer chunks in full run because optimize chose larger chunk_size (2048 vs 1024).
