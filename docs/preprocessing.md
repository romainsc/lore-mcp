# Preprocessing — Preparing sources for RAG

This guide explains how to prepare markdown
sources before indexing them with lore-mcp.
Preprocessing is the single most impactful
factor in retrieval quality.

For build workflow, see [`tutorial.md`](tutorial.md).
For source quality analysis, see `lore-mcp lint`.
For design rationale, see
[`architecture.md`](architecture.md).

## 1. Why preprocessing matters

Retrieval quality depends on four factors, in
order of measured impact:

| Factor | Impact | What you control |
|--------|--------|------------------|
| **Source preprocessing** | ~60% | Text quality, noise removal, structure |
| **Chunking parameters** | ~20% | chunk_size, overlap (use `lore-mcp optimize`) |
| **Embedding model** | ~15% | Model choice (see ADR-005) |
| **Search parameters** | ~5% | top_k, similarity threshold |

Investing 30 minutes cleaning your sources gives
more return than switching embedding models.

### "Semantic" search is statistical

Vector search computes statistical similarity
between token distributions — it does not
understand meaning. A chunk full of numeric
coordinates will match queries about numbers.
A heading like `## Performance` will match
queries about theater performances. The model
has no domain knowledge; it matches patterns.

This means: **garbage in, garbage out**. The
quality of what goes into the index determines
the quality of what comes out.

> Source: openshift E14.17 study (29 products,
> 21 patterns, 17 academic references).

## 2. Headings as structural signal

Markdown headings (`##`, `###`) are **structural
markers**, not noise. lore-mcp uses them as
primary split boundaries for chunking
(`ingest.py:MD_SEPARATORS`).

### Headings are preserved in chunks

When a chunk starts with a heading, the heading
text becomes part of the chunk content. This
gives the embedding model structural context:
a chunk starting with `## Authentication` will
rank higher for auth-related queries than the
same content without the heading.

### Heading hierarchy matters

Use consistent heading levels. Each `##` starts
a major section, `###` a subsection. The chunker
splits on `##` first, then `###`, then `####`.

Good:
```markdown
## Installation

### Prerequisites

Python 3.10+ is required...

### Steps

1. Clone the repository...
```

Bad:
```markdown
#### Installation

## Prerequisites

# Steps
```

Inconsistent levels confuse the chunker: it may
split in the middle of a subsection or merge
unrelated sections.

### Strip `#` from search queries

When querying lore-mcp, **do not include `#` in
your query**. Measured impact on cosine similarity:

| Query | Cosine score |
|-------|-------------|
| `authentication setup` | 0.69 |
| `## authentication setup` | 0.61 |

The `#` characters dilute the query vector.
Headings are **preserved** in indexed chunks —
they are structural signal for both chunking
(`MD_SEPARATORS`) and retrieval context. Do not
strip `#` from source content.

This is handled automatically in `eval.py`
heading-based question generation
(`eval.py:_generate_heading_questions`).

## 3. Image handling

lore-mcp replaces markdown images with their
alt text during preprocessing
(`ingest.py:preprocess`):

```
![Architecture diagram showing three layers](img/arch.png)
```

becomes:

```
Architecture diagram showing three layers
```

### Why this matters

- **Base64 images** inflate chunk size with
  bytes that have no semantic value. A single
  embedded image can consume an entire chunk
  budget with meaningless data.
- **Alt text carries the semantic signal**:
  `Architecture diagram showing three layers`
  is indexable and searchable. The base64 data
  is not.
- **Nested brackets are handled**: the regex
  in `preprocess()` supports patterns like
  `![chart [2024]](img.png)`.

### Write good alt text

Since alt text is what survives into the index,
write it to be searchable:

Good:
```markdown
![CPU usage graph showing 80% spike during indexing](img/cpu.png)
```

Bad:
```markdown
![image1](img/cpu.png)
![](img/cpu.png)
```

The first example will match queries about CPU
usage and indexing performance. The second two
contribute nothing to retrieval.

## 4. Noise detection

Some content degrades retrieval quality by
adding irrelevant matches. Use `lore-mcp lint`
to detect these patterns before indexing.

### Common noise patterns

**Numeric sequences**: ANN weight matrices,
coordinate lists, table rows with only numbers.
These match any numeric query regardless of
context.

```markdown
<!-- noise: no semantic value -->
0.234 0.567 0.891 0.123
0.456 0.789 0.012 0.345

<!-- useful: context makes it searchable -->
The model achieved 0.89 F1 score on the
validation set, up from 0.76 in the previous
iteration.
```

**Trivial content**: single characters, isolated
letters, bullet points with no context.

```markdown
<!-- noise -->
- P
- f
- x

<!-- useful -->
- Python 3.10+ required
- FIPS mode enabled
- x86_64 architecture
```

**OCR artifacts**: garbled text from PDF-to-
markdown conversion. Check for character
sequences that don't form words. OCR quality
has massive impact: RAG accuracy varies from
8.6% to 83.5% depending on parser quality
alone (E14.17).

**Tables split across chunks**: never let the
chunker break a table in half. A partial table
row has no semantic value. If your document
contains data tables, ensure they fit within a
single chunk or extract them as structured
metadata.

**PII in sources**: embedding vectors are not
anonymization. Sensitive data (names, emails,
internal IDs) indexed in chunks will surface
in search results. Remove PII before indexing,
not after.

### Running lint

```bash
lore-mcp lint manifest.yaml --docs-dir /path/to/docs
```

Output is a per-file quality report with text
density, heading count, noise/empty sections,
and a verdict (good/warn/poor). Files with
`poor` verdict should be cleaned before
indexing. Files with `warn` deserve review.

See `lint.py` for current thresholds and
metrics — this tool is under active development
and may gain additional checks from upstream
research.

## 5. Text quality checklist

Before indexing, verify each source file against
this checklist:

- [ ] **Text density > 0.7**: at least 70% of
  characters are alphabetic. Low density
  indicates numeric data, code blocks, or
  binary content
- [ ] **Sections have content**: headings
  followed by body text, not just headings
  stacked on headings. Heading-only files
  (like converted presentation slides) produce
  chunks with no prose for the model to match
- [ ] **Consistent heading hierarchy**: `##`
  before `###` before `####`. No skipped levels
- [ ] **No embedded binary data**: no base64
  images, no inline binary blobs. Use
  `preprocess()` or remove manually
- [ ] **Tables intact**: no table split across
  chunk boundaries. Keep tables small enough to
  fit in one chunk, or extract as metadata
- [ ] **No PII**: no personal data in indexed
  sources (vectors are not anonymization)
- [ ] **Don't over-clean**: do not lowercase
  everything, do not expand all abbreviations,
  do not strip all punctuation. Over-cleaning
  degrades embedding quality — the model uses
  casing and punctuation as signals
- [ ] **Front matter with metadata**: title,
  author, license, date. lore-mcp extracts
  front matter via `manifest.py` and stores it
  in the `sources` table for bibliographic
  output

### Context window budget

Chunks larger than ~2500 tokens show quality
degradation (context cliff). lore-mcp defaults
to 1024 characters (~256 tokens) with 128
character overlap, well within the safe range.
Use `lore-mcp optimize` to find the best
chunk_size/overlap for your corpus.

> Source: FloTorch 2026, confirmed by E14.17
> study. Recursive chunking outperforms semantic
> chunking (69% vs 54% retrieval accuracy).

## 6. Common pitfalls

### Presentation slides → markdown

Slide decks converted to markdown produce files
that are mostly headings with minimal prose.
Each slide becomes a heading with 1-3 bullet
points. The chunks contain too little text for
meaningful embedding.

**Fix**: expand bullet points into full
sentences, or exclude slide-derived files from
indexing.

### PDF-to-markdown OCR artifacts

PDF extraction tools produce garbled text,
especially from scanned documents: missing
spaces, merged words, wrong characters. The
impact is dramatic: RAG accuracy varies from
8.6% to 83.5% depending on parser quality alone.

**Fix**: choose your parser carefully. Recommended
tools (E14.17): Docling (MIT, 97.9% accuracy)
for PDF/DOCX, trafilatura (Apache 2.0, F1 0.966)
for web content. See E6.06 for the multi-format
ingestion study. Run `lore-mcp lint` to detect
low text density after conversion.

### HTML-to-markdown residual tags

Some converters leave HTML tags in the markdown:
`<div>`, `<span class="...">`, `&nbsp;`. These
add noise to chunks without semantic value.

**Fix**: strip residual HTML tags. Most markdown
renderers ignore them, but embedding models do
not — they consume token budget.

### Mixed languages in same document

Embedding models handle multilingual content,
but mixing languages within a single chunk
degrades similarity scores. A chunk that is
half English, half French will partially match
queries in both languages but excel in neither.

**Fix**: keep each document in a single
language. If bilingual content is required,
separate sections by language and ensure chunk
boundaries align with language boundaries.

### Collection strategy

Indexing everything into one large collection
degrades retrieval precision. Three targeted
collections outperform one noisy collection.

**Fix**: use lore-mcp's multi-collection
support (`LORE_DB_DIR`). Group sources by theme
and confidentiality level. See
[ADR-004](adr/004-multi-collection.md) for
the naming convention (`<theme>-<level>.db`).

## 7. Advanced upstream techniques

These techniques are applied **before** passing
sources to lore-mcp. They require no lore-mcp
code — they are upstream enrichments that the
source provider performs on the markdown files.

### Contextual retrieval

An LLM (Claude) reads each section and prepends
a short paragraph (50-100 tokens) explaining
where it sits in the document. The chunk
carries its own context summary.

Measured impact: −35% retrieval failures with
embeddings alone, −49% with hybrid BM25+dense,
−67% with BM25+dense+reranking (Anthropic).
Cost: ~$1.02/M tokens with prompt caching.

How to apply: for each section of your source
document, ask Claude to generate a context
paragraph. Prepend it to the section content
before indexing.

### Q&A mode

An LLM generates 2-3 questions per section.
The questions are concatenated with the section
content before indexing. This makes chunk
vectors closer to how users actually query.

How to apply: ask Claude to generate questions
from each section, append them to the source
markdown. No lore-mcp code needed.

### Proposition indexing

An LLM decomposes each chunk into atomic,
self-contained propositions ("Python 3.10 is
required for installation"). Each proposition
is indexed independently.

Measured impact: +22.5% over passage retrieval,
+35% over sentence retrieval. Costly: one LLM
call per paragraph. Suited for high-value
corpora, not bulk indexing.

### Deduplication

Duplicate content (copy-paste between docs,
multiple versions of the same paragraph)
pollutes retrieval results. Three levels:

1. **Exact**: SHA-256 hash before chunking —
   skip identical files
2. **Near-duplicate**: MinHash+LSH after
   chunking — detect paraphrased content
3. **Semantic**: cosine threshold at retrieval
   — deduplicate results (MMR)

Measured duplication rates: ~0.16% clean
academic corpora, ~24% enterprise docs, ~80%
conversational data (E14.17).

### HyDE (Hypothetical Document Embedding)

The LLM generates a hypothetical answer to the
user's query. That answer is embedded and used
for vector search instead of the raw query.

Measured impact: +10-20% on ambiguous queries.
Implemented in the MCP client, not in lore-mcp.

### Metadata enrichment

Add structured metadata to chunks before
embedding: heading path (already done by
lore-mcp), section summaries (Claude),
keywords (TextRank), named entities (SpaCy
NER), generated questions (Claude).

Measured impact: +9.2 points RAG accuracy with
TF-IDF weighted metadata, +14.8 points with
document hierarchy metadata (Contextual AI).

> All measured impacts sourced from E14.17
> study. See the full study for implementation
> details per product.

## Scope — what lore-mcp handles

lore-mcp covers steps 4-6 of the RAG pipeline:

| Step | Description | Owner |
|------|-------------|-------|
| 1. Parse | Convert source format to text | You (upstream) |
| 2. Clean | Remove noise, fix encoding | You (upstream) |
| 3. Deduplicate | Remove duplicate content | You (upstream) |
| 4. Split | Chunk text into segments | lore-mcp (`ingest.py`) |
| 5. Enrich | Embed + metadata | lore-mcp (`embedder.py`, `manifest.py`) |
| 6. Index | Store vectors | lore-mcp (`store.py`) |

This guide focuses on steps 1-3 — your
responsibility as the source provider. The
better your input, the better lore-mcp's output.

---

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
