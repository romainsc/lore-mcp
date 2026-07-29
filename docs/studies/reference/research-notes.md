# Research notes — technology choices

## Embedding model

### Choice: BAAI/bge-m3

- 1024 dimensions, multilingual (FR, EN, ZH...)
- License: **MIT**
- Recommended by Red Hat for AutoRAG
  (doc "Working with AutoRAG" §3)
- Verified by AutoRAG benchmark: +13%
  answer_correctness vs nomic-embed-text-v1.5
  on Red Hat technical corpus
- ~2.3 GB FP32, ~1.2 GB FP16
- Max tokens: 8192
- GitHub: 4k+ stars, active community

### Alternatives evaluated

| Model | Dim | Score | License |
|-------|-----|-------|---------|
| BAAI/bge-m3 | 1024 | 0.4772 | MIT |
| nomic-embed-text-v1.5 | 768 | 0.4221 | Apache 2.0 |

## Local vector store

### Choice: sqlite-vec

- License: **MIT**
- GitHub: 6k+ stars, active development
- Author: Alex Garcia (solo maintainer, prolific)
- Version tested: 0.1.9
- Supported by the SQLite ecosystem

Sources:
- https://dev.to/aairom/embedded-intelligence-how-sqlite-vec-delivers-fast-local-vector-search-for-ai-3dpb
- https://github.com/asg017/sqlite-vec/issues/94
- https://localaimaster.com/blog/vector-databases-comparison

### Comparative

| Criteria | FAISS | ChromaDB | sqlite-vec |
|----------|-------|----------|-----------|
| License | **MIT** | **Apache 2.0** | **MIT** |
| Suited volume | Billions | < 10M | Thousands-millions |
| Portability | Binary file | Directory | **Single .db file** |
| Standard | No | No | **SQL** |
| Persistence | Manual | Built-in | SQLite native |
| Maturity | Very mature | Young | Young (v0.1.9) |
| GitHub stars | 33k+ | 18k+ | 6k+ |

sqlite-vec selected because: single file, SQL
standard, zero infrastructure, suited to our
volume (~40-50k chunks), MIT license.

### Noted alternative: sqlite-vector

Different project from sqlite-vec. Benchmarks:
17x faster with quantization. But newer, smaller
community. Worth monitoring.

## Existing MCP RAG projects evaluated

| Project | License | bge-m3 compatible | Local GPU |
|---------|---------|-------------------|-----------|
| shinpr/mcp-local-rag | MIT | No (Transformers.js/ONNX) | Experimental |
| Daniel-Barta/mcp-rag-server | Unspecified | No (Transformers.js) | No |

Neither supports our stack
(sentence-transformers Python, CUDA GPU,
bge-m3 1024d). Custom project justified.

Note: this project USES sqlite-vec as a
dependency. It does not reimplement sqlite-vec.
The value added is the MCP integration, the
embedding fallback (GPU→API→CPU), and the
ingestion pipeline.

## Chunking

### Choice: RecursiveCharacterTextSplitter

- From langchain-text-splitters (license: **MIT**)
- chunk_size=2048, chunk_overlap=128
- Markdown separators: \n## , \n### , \n\n, \n
- Validated by AutoRAG on Red Hat corpus

## MCP SDK

### Choice: FastMCP (package: mcp)

- Official Anthropic SDK for Python
- License: **MIT**
- from mcp.server.fastmcp import FastMCP
- Stdio transport (simplest for Claude Code)
- Version tested: 1.28.1

## Preprocessing

### Filtering (conditional)

- NUL characters (\x00): some converted PDFs
  contain NUL that crash PostgreSQL and SQLite.
  Always filter.
- Base64 image data: Markdown from Docling PDF
  conversion contains base64-encoded images.
  A 70 KB text document can weigh 1 MB with
  images. Filter lines containing "base64,"
  **only if captioning is not implemented**.
  Once images are captioned, keep the captions
  and remove only the raw base64.
