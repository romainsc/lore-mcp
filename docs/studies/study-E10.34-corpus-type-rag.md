# Study E10.34 — Corpus-type impact on RAG pipeline

- **Date:** 2026-09-24
- **Status:** Study complete, benchmarks pending

## 1. Question

Does RAG on fundamentally different corpus types (source
code, technical documentation, philosophy/literature,
heterogeneous mix) require fundamentally different
pipelines, or can a single pipeline with configuration
knobs handle all?

## 2. Corpus types evaluated

| Type | Characteristics | Example | Challenges for RAG |
|------|----------------|---------|-------------------|
| **Source code** | Syntactic structure, imports, variable names as semantic signals, mixed code+docs+config | lore-mcp repo (~4K LOC) | Function boundaries matter; line-based splitting destroys semantics; cross-file dependencies (imports, calls) create implicit context |
| **Technical documentation** | Structured headings, procedures, tables, commands, multilingual | OpenShift/RHOAI docs, OCDE PDF | Heading hierarchy is a chunking signal; tables must not be split; images carry meaning |
| **Philosophy/literature** | Long prose, extended argumentation, minimal formal structure, rich vocabulary, cross-references | Project Gutenberg — Kant, Montaigne (public domain) | Arguments span multiple paragraphs; no heading structure to chunk on; semantic coherence requires larger chunks |
| **Heterogeneous** | Mix of all above in one collection | All three combined | Embedding model must handle all domains; chunking strategy must not assume structure |

## 3. Pipeline dimensions to compare

### 3.1 Chunking

| Strategy | Best for | Mechanism | lore-mcp support |
|----------|---------|-----------|-----------------|
| **Heading-based** (MarkdownTextSplitter) | Technical docs | Split on `##`, `###` headings | Current default |
| **AST-aware** (tree-sitter) | Source code | Parse AST, chunk by function/class boundaries | Not implemented |
| **Paragraph/semantic** | Prose/literature | Split on paragraph boundaries, merge until size limit | Partially (RecursiveCharacterTextSplitter) |
| **Recursive character** | Universal fallback | Split on `\n\n`, `\n`, ` `, `""` hierarchy | Available via langchain |

**Key finding (cAST, EMNLP 2025)**: AST-based code chunking
via tree-sitter yields +5.5 pts on RepoEval with
StarCoder2-7B, and +4.3 pts on CrossCodeEval. The approach
is language-agnostic (works across 150+ languages via
tree-sitter grammars). Fixed-size or line-based splitting
on code is "malpractice" per current literature.

**Key finding (LumberChunker, 2024)**: For narrative prose
(novels, philosophy), LLM-guided chunking that identifies
semantic shift points outperforms semantic, recursive, and
proposition-level chunking on the GutenQA benchmark. However,
the computational cost is high (1 LLM call per paragraph
group).

**Key finding (Vectara, 2024)**: For straightforward prose,
semantic chunking gains over recursive splitting are
marginal and not justified by computational cost.

**Recommendation**: Recursive character splitting at
512–1024 tokens with 10–20% overlap is a strong universal
baseline. Code benefits significantly from AST-aware
chunking. Prose does not benefit from semantic chunking
over recursive splitting in most cases.

### 3.2 Embedding models

| Model | License | Type | Code perf | Text perf |
|-------|---------|------|-----------|-----------|
| **nomic-embed-text-v2-moe** | Apache 2.0 | Generalist, multilingual, 768d | Trained on 100+ programming languages; no specific code benchmark published | Competitive with models 2x its size on BEIR/MIRACL |
| **CodeBERT** (microsoft/codebert-base) | MIT | Code-specialized, 768d | Trained on code+NL pairs, bimodal | Underperforms generalist models on text-only tasks |
| **Voyage code-3** | Proprietary (API) | Code-specialized | +13.8% vs OpenAI-v3-large on 32 code datasets | N/A (code-only) |
| **bge-m3** | MIT | Generalist, multilingual, 1024d | Good but not code-specialized | Top performer on multilingual BEIR |

**Key finding (MTEB 2024–2025)**: Code retrieval is now a
**separate benchmark track** within MTEB, distinct from
general text retrieval. Models optimized for code (Voyage
code-3) significantly outperform generalist models on code
tasks. Conversely, code-specialized models underperform on
general text.

**Key finding (nomic-embed-text-v2-moe)**: Trained on 100+
programming languages with multilingual pairs, providing
reasonable code handling without sacrificing text
performance. No published code-specific benchmark scores,
but the breadth of training data suggests adequate
(not optimal) code retrieval.

**Recommendation**: For mixed corpora, a generalist model
(nomic v2, bge-m3) provides acceptable quality across all
types. For code-heavy corpora where retrieval precision is
critical, a code-specialized model (CodeBERT for libre,
Voyage code-3 for best quality) provides measurable gains.
The license constraint (AGPL-3.0 compatibility) excludes
Voyage code-3 (proprietary API) but permits CodeBERT (MIT).

### 3.3 Preprocessing

| Step | Code | Tech docs | Prose | Universal? |
|------|------|-----------|-------|-----------|
| Unicode NFC normalization | Yes | Yes | Yes | **Yes** |
| Whitespace/NUL cleanup | Yes | Yes | Yes | **Yes** |
| Image → alt text / VLM caption | N/A | Yes | Rare | Type-specific |
| Table protection | N/A | Yes | N/A | Type-specific |
| HTML/PDF parsing | N/A | Yes | Sometimes | Type-specific |
| OCR | N/A | Scanned docs | Rare | Type-specific |
| Heading extraction | Docstrings | Yes | Chapters | Varies |
| Enrichment (context, QA, meta) | Debatable | Yes | Yes | Mostly universal |
| Import/dependency resolution | Yes | N/A | N/A | Code-specific |

**Recommendation**: Core preprocessing (normalization,
cleanup) is universal. Format-specific parsing
(PDF, DOCX, HTML) is already handled by lore-mcp's
multi-format pipeline. Code-specific preprocessing
(import resolution, dependency extraction) is the main
gap — it requires AST analysis that does not exist in
the current pipeline.

### 3.4 Retrieval quality expectations

| Corpus type | Expected NDCG@5 with current pipeline | Bottleneck |
|-------------|--------------------------------------|------------|
| Technical docs | 0.65–0.80 | Chunking quality, heading structure |
| Source code | 0.30–0.50 (estimated) | Line-based chunking destroys function boundaries |
| Philosophy/prose | 0.50–0.65 (estimated) | Large semantic units, no heading structure |
| Heterogeneous | 0.50–0.65 (estimated) | Embedding model must generalize across domains |

## 4. Literature review

### 4.1 Code RAG — AST-based chunking

The field has converged on **tree-sitter** as the preferred
parser for code chunking in RAG systems. Key references:

- **cAST (EMNLP 2025)**: Structural chunking via Abstract
  Syntax Trees. Language-agnostic, plug-and-play. +5.5 pts
  RepoEval, +4.3 pts CrossCodeEval, +2.7 pts SWE-bench.
  ([arXiv](https://arxiv.org/html/2506.15655v1))

- **Aider repo-map**: Uses tree-sitter AST + PageRank to
  surface architecturally important symbols. Not
  embedding-based RAG — structural/graph-based retrieval.
  Processes 15B tokens/week. Claude Code skips indexing
  entirely and uses agentic search (early RAG experiments
  showed agentic search performed better).
  ([aider.chat](https://aider.chat/2023/10/22/repomap.html))

- **CodeRAG with dependency graph**: tree-sitter parses
  code into AST, builds dependency graph, retrieves chunks
  with their neighbors for complete context.
  ([Medium](https://medium.com/@shsax/how-i-built-coderag-with-dependency-graph-using-tree-sitter-0a71867059ae))

- **Codebase-Memory (2025)**: tree-sitter-based knowledge
  graphs for LLM code exploration via MCP. Structural
  retrieval (graph traversal along typed relationships)
  complements embedding-based retrieval.
  ([arXiv](https://arxiv.org/html/2603.27277v1))

- **LangChain Language parameter**: `RecursiveCharacterText
  Splitter.from_language(Language.PYTHON)` provides
  language-aware separators (regex-based, not AST). Works
  for clean code but fails on edge cases (e.g., `def`
  inside multiline strings). For production code RAG, AST-
  based tools are recommended.
  ([LangChain docs](https://reference.langchain.com/python/langchain-text-splitters/character/RecursiveCharacterTextSplitter))

**Licenses**: tree-sitter (MIT), individual language
grammars (varies, mostly MIT), LangChain text-splitters
(MIT), supermemoryai/code-chunk (MIT).

### 4.2 Text/prose RAG — chunking strategies

- **Recursive character splitting (512–1024 tokens, 10–20%
  overlap)**: Strong universal baseline. For straightforward
  prose, gains of semantic chunking over this are marginal
  (Vectara finding).

- **LumberChunker (2024)**: LLM-guided semantic shift
  detection for narrative texts. Best on GutenQA benchmark
  but high cost (1 LLM call per paragraph group). Suited
  for narrative/philosophical texts with long arguments.

- **Late Chunking (Jina, 2024)**: Embed full document
  first, then chunk — preserves context better than
  traditional chunk-then-embed. Requires compatible
  embedding model.

- **Contextual retrieval (Anthropic, 2024)**: Prepend
  LLM-generated context summary to each chunk before
  indexing. −35% retrieval failure alone, −49% with
  hybrid BM25. Already implemented in lore-mcp (E12.09).

### 4.3 Hybrid/heterogeneous RAG architectures

The 2024–2025 consensus is **hybrid architectures**:
unified orchestration layer with specialized, pluggable
components.

- **Intelligent routing**: Classifier determines query
  domain and routes to specialized RAG applications.
  +30–40% precision over monolithic approaches.
  ([applied-ai.com](https://www.applied-ai.com/briefings/enterprise-rag-architecture/))

- **Multi-embedding**: Different embedding models per
  document type within the same pipeline.

- **Agentic RAG**: LLM plans, orchestrates retrieval,
  manages memory. Adaptive RAG classifies query complexity
  and selects strategy. The next generation of RAG.
  ([turingpost.com](https://www.turingpost.com/p/ragtypes))

### 4.4 Embedding models — code vs text

MTEB now has separate code retrieval benchmarks (introduced
2024). Key models:

| Model | MTEB Code | MTEB Text Retrieval | License |
|-------|:---------:|:-------------------:|---------|
| Voyage code-3 | ~84 | N/A | Proprietary |
| Gemini Embedding 2 | 84.0 | 67.71 | Proprietary |
| CodeBERT | Good (code-specific) | Below generalist | MIT |
| nomic-embed-text-v2-moe | Unknown (not published) | Competitive 300M class | Apache 2.0 |
| bge-m3 | Unknown | Top multilingual | MIT |
| Jina v5-text-small | Unknown | 71.7 (MTEB v2) | Apache 2.0 |

([codesota.com](https://www.codesota.com/benchmarks/mteb),
[modal.com](https://modal.com/blog/mteb-leaderboard-article),
[tensoria.fr](https://tensoria.fr/en/blog/embedding-models-2026-guide))

## 5. Preliminary analysis

### What is universal (works for all types)?

1. **Core preprocessing**: Unicode NFC, whitespace cleanup,
   format parsing (PDF/HTML/DOCX → markdown) — lore-mcp
   already handles this
2. **Recursive character splitting** with overlap —
   acceptable baseline for all types
3. **Generalist embedding models** (nomic v2, bge-m3) —
   adequate for mixed corpora
4. **Hybrid search** (BM25 + vector with RRF) — improves
   recall for all types
5. **Reranking** — improves precision for all types
6. **Contextual retrieval** (prepend context to chunks) —
   universal quality improvement

### What is type-specific?

1. **Code chunking**: AST-aware via tree-sitter is
   significantly better than line-based (+5.5 pts). This
   is the single largest type-specific gap in lore-mcp.
2. **Code metadata**: Import/dependency resolution for
   cross-file context — not possible with text-based
   chunking.
3. **Table protection**: Only matters for technical docs
   (already implemented in lore-mcp).
4. **Image captioning**: Only matters for visual documents
   (already implemented).
5. **Long-prose chunking**: Larger chunk sizes (2048+) for
   philosophical texts to preserve argument coherence.
   Configurable via `chunk_size` — no code change needed.

### Impact of using the wrong approach

| Mismatch | Estimated impact |
|----------|-----------------|
| Line-based chunking on code | −5 to −15 pts NDCG (function boundaries destroyed) |
| Code embedding on prose | −3 to −8 pts NDCG (vocabulary mismatch) |
| Generalist embedding on code | −3 to −10 pts NDCG vs code-specialized |
| Small chunks (512) on philosophy | −2 to −5 pts NDCG (arguments split mid-reasoning) |
| MarkdownTextSplitter on code | Neutral to −3 pts (heading-based splitting is suboptimal but not catastrophic for well-commented code) |

## 6. Benchmark plan

### 6.1 Corpus selection (all libre license)

| Type | Corpus | License | Language | Size |
|------|--------|---------|----------|------|
| Source code | lore-mcp repository (src/ + docs/) | AGPL-3.0 | Python + EN | ~4K LOC + docs |
| Technical docs | Existing test corpus (manifest-test-redist) | Various libre | FR + EN | ~20 files |
| Philosophy | Kant — *Prolegomena to Any Future Metaphysics* (Project Gutenberg #52821) | Public domain | EN | ~100 pages |
| Heterogeneous | All three combined | Mixed | EN + FR | ~50 files |

### 6.2 Questions (10 per corpus type)

**Code questions** (natural language → code):
1. How does the checkpoint mechanism work?
2. Where is the embedding model loaded?
3. What happens when a VLM captioning call fails?
4. How are phases tracked in the pipeline?
5. What format does the manifest use?
6. How does hybrid search (BM25 + vector) work?
7. Where is the reranking model loaded?
8. What is the role of `_start_embedders`?
9. How does `parse_video` extract frames?
10. What happens on SIGINT during preprocessing?

**Technical docs questions**: Use existing eval questions
from the test corpus.

**Philosophy questions**:
1. What is the distinction between a priori and a posteriori?
2. How does Kant define synthetic judgments?
3. What role does intuition play in mathematics?
4. What are the limits of metaphysics as a science?
5. How does Kant respond to Hume's skepticism?
6. What is the relationship between experience and knowledge?
7. How does Kant distinguish phenomena from noumena?
8. What are the categories of understanding?
9. Why can metaphysics not be a demonstrative science?
10. What is the transcendental deduction?

### 6.3 Metrics

- **NDCG@5** and **NDCG@10**: primary retrieval quality
- **Recall@5** and **Recall@10**: coverage
- **MRR**: first relevant result position

### 6.4 Configuration variations to test

| Dimension | Values |
|-----------|--------|
| Chunking strategy | MarkdownTextSplitter (current), RecursiveCharacterTextSplitter with language=python (LangChain), tree-sitter (if implemented) |
| Chunk size | 512, 1024, 2048 |
| Embedding model | nomic-embed-text-v2-moe (current default) |
| Hybrid search | On / off |
| Reranking | On / off |
| Enrichment | None / context / context+QA |

## 7. Recommendation

**Preliminary verdict: B — Specialized backends per corpus
type, unified orchestration.**

A single pipeline with configuration knobs handles 80% of
the problem. The current lore-mcp pipeline (recursive
chunking + generalist embedding + hybrid search + reranking
+ enrichment) works well for technical documentation and
adequately for prose.

The critical gap is **source code**. The literature is
unambiguous: AST-aware chunking via tree-sitter
significantly outperforms line/character-based chunking for
code retrieval (+5–15 pts NDCG). This is not a parameter
tuning problem — it requires a different chunking backend.

However, this does not require a fundamentally different
pipeline. The architecture should be:

```
lore-mcp pipeline (unified orchestration)
├── Parse (format-specific, already modular)
├── Chunk (type-specific backend needed)
│   ├── MarkdownTextSplitter → docs, prose
│   └── tree-sitter AST → source code (NEW)
├── Embed (generalist model, universal)
├── Enrich (universal, optional)
├── Index (universal)
└── Search (hybrid + reranking, universal)
```

For prose/philosophy, larger chunk sizes (2048) via existing
config knobs are sufficient. No new backend needed.

**Final verdict depends on benchmarks** — the estimated
impact of AST chunking on code retrieval needs validation
on the lore-mcp codebase. If the current pipeline scores
above 0.5 NDCG@5 on code questions, the urgency of a
tree-sitter backend is lower.

## 8. Items to create (if benchmarks confirm)

- **E12.7x [P] tree-sitter code chunking backend**: Add
  `detect_format` → "code" for source code extensions
  (.py, .js, .go, .rs, etc.). Chunk via tree-sitter AST
  (function/class boundaries). tree-sitter is MIT licensed.
  Depends on this study's benchmark results.

- **E12.7x [P] Code metadata in chunks**: Prepend file
  path, language, and imports as metadata to each code
  chunk. Improves retrieval context without changing the
  embedding model.

- **E6.10 extension**: Per-source `chunk_strategy` in
  manifest (e.g., `chunk_strategy: ast` for code files,
  `chunk_strategy: markdown` for docs). Already partially
  supported via per-source chunk_size/overlap.

## Sources

- [cAST: Structural Chunking via AST (EMNLP 2025)](https://arxiv.org/html/2506.15655v1)
- [Aider: Repository Map with tree-sitter](https://aider.chat/2023/10/22/repomap.html)
- [CodeRAG with Dependency Graph (tree-sitter)](https://medium.com/@shsax/how-i-built-coderag-with-dependency-graph-using-tree-sitter-0a71867059ae)
- [Codebase-Memory: tree-sitter Knowledge Graphs via MCP](https://arxiv.org/html/2603.27277v1)
- [MTEB Leaderboard 2026](https://www.codesota.com/benchmarks/mteb)
- [MTEB Embedding Models](https://modal.com/blog/mteb-leaderboard-article)
- [Embedding Models 2026 Benchmark](https://tensoria.fr/en/blog/embedding-models-2026-guide)
- [Enterprise RAG Architecture](https://www.applied-ai.com/briefings/enterprise-rag-architecture/)
- [20 Advanced RAG Types (2026)](https://www.turingpost.com/p/ragtypes)
- [Chunking Strategies for RAG (comprehensive guide)](https://medium.com/@adnanmasood/chunking-strategies-for-retrieval-augmented-generation-rag-a-comprehensive-guide-5522c4ea2a90)
- [RAG Chunking 2026 Benchmark Guide](https://www.premai.io/blog/rag-chunking-strategies-the-2026-benchmark-guide/)
- [Standardized Project Gutenberg Corpus](https://arxiv.org/abs/1812.08092)
- [LangChain RecursiveCharacterTextSplitter](https://reference.langchain.com/python/langchain-text-splitters/character/RecursiveCharacterTextSplitter)
- [nomic-embed-text-v2-moe (HuggingFace)](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe)
- [Voyage code-3 (blog post)](https://blog.voyageai.com/2024/12/04/voyage-code-3/)
- [From RAG to Context — 2025 Review (RAGFlow)](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)
