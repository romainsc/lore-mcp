# Grooming E3.06 — Preprocessing guide

- **Status:** En attente validation
- **Date:** 2026-09-05

## Problem

No documentation explains how to prepare markdown
sources for optimal RAG indexing. Users index files
as-is and get poor retrieval quality without
understanding why. The measured impact of
preprocessing (~60% of RAG quality) vs embedding
model (~15%) is not documented.

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

## DoD

1. `docs/preprocessing.md` with all 6 sections
2. Cross-referenced from architecture and tutorial
3. Practical examples (good vs bad markdown)
4. Reference to `lore-mcp lint`
5. Measured data (cosine similarity, impact %)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
