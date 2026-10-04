# E2.06 Dry-run report — add_recipe (sans optimize)

## Task
- Task ID: b0714e85
- Start: 2026-10-03 23:21
- End: 2026-10-04 05:17
- Duration: 21394s (5h56m)
- Status: **completed with partial success**

## Configuration
- Embedding: nomic-ai/nomic-embed-text-v2-moe via TEI API (port 8082)
- Chunking: 1024/128 (HybridChunker)
- Parse: Tesseract OCR fra+eng, Docling multi-format
- Caption: granite-vision (primary) + molmo-7b (additional), judge granite-8b
- Enrich: context + qa + meta via granite-8b (concurrency 8)
- STT: canary-1b-v2
- Frames: scene strategy
- Reranking: granite-embedding-reranker-english-r2
- Optimize: disabled (dry-run)

## Timing
- Phase 1 (parse): ~10 min
- Phase 2 (captioning granite-vision): ~90 min (PPTX dominant)
- Phase 2 (captioning molmo-7b): ~210 min (3h30, PPTX CPU 7B)
- Phase 3 (enrich): ~15 min
- Indexing: ~5 min
- Metadata: <1 min
- **Total: 5h56m**

## Results
- Collection: full-recipe ✓ (E12.103 fix verified)
- Model: nomic-ai/nomic-embed-text-v2-moe ✓
- Chunk size: 1024, overlap: 128 ✓ (E12.105 fix verified)
- Sources: **9/21** ⚠️
- Chunks: 2110
- DB size: 13 MB

## Per-source results

### OK (9/21)
| Source | Format | Status |
|--------|--------|--------|
| test-markdown-sample.md | MD (file:) | ✓ |
| test-data-sample.csv | CSV (file:) | ✓ |
| DUDH_2008.png | Image (file:) | ✓ |
| free-sw.en.html | HTML (url, ext in URL) | ✓ |
| 623da898-en.pdf | PDF (url, ext in URL) | ✓ |
| governing_ai_for_humanity_final_report_en.pdf | PDF (url, ext in URL) | ✓ |
| S-GEN-UNACT-2021-PDF-E.pdf | PDF (url, ext in URL) | ✓ |
| Reunion-Parents...pptx | PPTX (url, ext in URL) | ✓ |
| pexels-photo-33121483.jpeg | Image (url, ext in URL) | ✓ |

### Error (10/21) — E12.107: URL basename without extension
| Source | Format | File in orig_dir | Issue |
|--------|--------|------------------|-------|
| open-source-ai-definition | HTML | .html exists | No ext in URL path |
| l-osi-publie-une-definition-de-l-ia-opensource-mais-pas-trop | HTML | .html exists | No ext in URL path |
| fsf-is-working-on-freedom-in-machine-learning-applications | HTML | .html exists | No ext in URL path |
| 2606.03019v1 | HTML | .html exists | No ext in URL path |
| open-weights | HTML | .html exists | No ext in URL path |
| OECD-LEGAL-0449 | HTML | .html exists | No ext in URL path |
| jl42g3kh0r9f9c6kj79lr2ft7mc4 | DOCX | .docx exists | No ext in URL path |
| eEBv0STiYhI | Audio | .webm exists | YouTube video ID |
| WYszRcHzqw8 | Video | .mkv exists | YouTube video ID |
| T3UKZGEXbVk | Video | .mkv exists | YouTube video ID |

### Missing from report (2/21) — E12.108
| Source | Format | File in orig_dir |
|--------|--------|------------------|
| aout-2026.xlsx | XLSX | exists |
| worldcup.json | JSON | exists |

## Bug fixes verified
| Bug | Status |
|-----|--------|
| E12.102 — Recipe orig_dir | ✓ Fixed (9 sources found) |
| E12.103 — Collection override | ✓ Fixed (collection=full-recipe) |
| E12.104 — YouTube URL collision | ✓ Fixed (3 unique video IDs) |
| E12.105 — Wrong chunk params | ✓ Fixed (1024/128) |

## New bugs identified
| Bug | Severity | Description |
|-----|----------|-------------|
| E12.106 | Minor | add_recipe progress not reported in get_task_status |
| E12.107 | Blocker | URL-only sources not found when URL has no extension |
| E12.108 | Major | 2 sources silently dropped from preprocess report |

## Bibliographic indexes
- full-recipe.json: not checked (only 9 sources)
- full-recipe.bib: not checked
- full-recipe.md: not checked
(Deferred to full run after E12.107 fix)

## Conclusion
Pipeline structurellement fonctionnel. Bug fixes E12.102-105 vérifiés.
**Bloqué par E12.107** (URL-to-filename resolution) — 10/21 sources
manquantes. Le vrai E2.06 (avec optimize) ne peut pas être lancé
tant que E12.107 n'est pas corrigé.

Performance note: molmo-7b CPU captioning du PPTX Parcoursup = 3h30.
C'est un cas extrême mais à considérer pour les estimations des
tests E2.07-E2.10.
