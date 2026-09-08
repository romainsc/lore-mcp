# Grooming E3.06 — Preprocessing guide

- **Status:** Implémenté
- **Date:** 2026-09-05
- **Context:** Platform enabling for openshift
  workspace consumers (AI Serving, Veille)

## Problem

No documentation explains how to prepare markdown
sources for optimal RAG indexing. Users index files
as-is and get poor retrieval quality without
understanding why. The measured impact of
preprocessing (~60% of RAG quality) vs embedding
model (~15%) is not documented.

## Platform enabling context

lore-mcp is a Platform component in the openshift
Team Topologies. The openshift workspace indexes
large corpora (94k+ chunks, 7 collections) and
encounters quality issues that preprocessing
documentation would prevent.

This guide is **self-service documentation** for
Platform consumers: AI Serving (corpus indexing),
Veille (source preparation). It enables consumers
to prepare quality inputs without requiring
Platform team intervention — a core Platform
responsibility.

## Solution

A documentation page `docs/preprocessing.md` with
practical guidance for preparing markdown sources.

### Content outline

1. **Why preprocessing matters**
   - Measured impact: preprocessing ~60%, chunking
     ~20%, model ~15%, search params ~5%
   - "Semantic" search = statistical similarity,
     not meaning comprehension
   - Garbage in → garbage out

2. **Headings as structural signal**
   - Headings are preserved in chunks (not noise)
   - Structure-aware chunking splits on headings
   - Strip `#` from search queries (measured:
     0.69 vs 0.61 cosine with `##`)
   - Use heading path as metadata

3. **Image handling**
   - Replace `![alt](src)` with alt text
   - Base64 images inflate chunks with no semantic
     value
   - Alt text carries the semantic signal
   - Nested brackets handled: `![chart [2024]](img.png)`

4. **Noise detection**
   - Numeric sequences (ANN weights, coordinates)
   - Trivial content ("P", "f", single characters)
   - OCR artifacts
   - Use `lore-mcp lint` to detect before indexing

5. **Text quality checklist**
   - Text density > 0.7 (alpha chars / total)
   - Sections with content (not just headings)
   - Consistent heading hierarchy
   - No embedded binary data
   - Front matter with metadata (title, author,
     license)

6. **Common pitfalls**
   - Presentation slides converted to markdown
     (mostly headings, little prose)
   - PDF-to-markdown OCR artifacts
   - HTML-to-markdown residual tags
   - Mixed languages in same document

### Cross-references

- `docs/architecture.md` → link from evaluation
  section
- `docs/tutorial.md` → link from build workflow
- `lore-mcp lint` → reference in preprocessing
  guide
- openshift E14.17 study → sourced data and
  academic references

## Data sources (from E14.17 study)

The Veille E14.17 study (845 lines, 29 products,
21 patterns, 17 academic refs) provides sourced
data for this guide:

- Recursive chunking > semantic chunking (69% vs
  54%, FloTorch 2026)
- Context cliff: >~2500 tokens/chunk → quality
  drops (validates 512-1024 range)
- Scope: lore-mcp = steps 4-6 (split, enrich,
  index); steps 1-3 (parse, clean, dedup) are
  upstream consumer responsibility
- Multi-collection: "3 targeted stores > 1 noisy
  store" (OpenAI)
- LLM enrichments (contextual retrieval, Q&A mode)
  are upstream, not lore-mcp code

The guide should reference these findings with
proper attribution to E14.17.

## Decision: preprocessing tool scope

The preprocessing tool (E12) stays in lore-mcp
as a separable module (`src/lore_mcp/preprocess/`)
rather than a separate project.

**Rationale:**
- One self-service tool for consumers
- Shared config (build-config YAML, manifest)
- `preprocess()` already exists in `ingest.py`
- Single repo to maintain (one developer)
- trafilatura GPL-3.0+ is compatible with AGPL
- P10: don't create a second project until the
  first can't hold it

**Extraction criteria:** if the preprocessing
module grows to the point where it has its own
release cadence, its own consumers outside
lore-mcp, or license conflicts — extract to a
separate project.

## DoD

1. `docs/preprocessing.md` with all 7 sections
2. Cross-referenced from architecture and tutorial
3. Practical examples (good vs bad markdown)
4. Reference to `lore-mcp lint`
5. Measured data (cosine similarity, impact %)
6. E14.17 study findings integrated with
   attribution
7. E12 backlog created for preprocessing tool

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
