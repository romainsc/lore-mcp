# CLAUDE.md — mcp-rag-local

## 1. Project overview

### What

MCP (Model Context Protocol) server for semantic
search over a corpus of technical documents.
Runs **locally** on the workstation with no
mandatory network dependency. Uses sqlite-vec
for portable vector storage (single file).

### Why

Enable an LLM (Claude Code, Claude Desktop, or
any MCP client) to query a locally indexed
documentation corpus. The RAG is embedded — no
remote server required.

### For whom

Developers and platform administrators who want
to query their technical documentation from
their IDE or CLI.

## 2. Architecture

### Embedding (vector generation)

Priority order (automatic fallback):
1. **Local GPU** (CUDA): sentence-transformers,
   configurable model (default: BAAI/bge-m3,
   1024 dimensions). Fastest (~20ms/query).
2. **Remote API** (OpenAI-compatible): vLLM,
   Llama Stack, or any service implementing
   `/v1/embeddings`. URL configurable.
3. **Local CPU**: sentence-transformers in CPU
   mode. Slower (~200ms) but self-contained.

### Vector storage

**SQLite + sqlite-vec**: a single portable `.db`
file. No server, no network. The file is
distributable.

Table schema:
```sql
CREATE VIRTUAL TABLE chunks_vec USING vec0(
  embedding float[1024]
);
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  source_file TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  metadata TEXT DEFAULT '{}'
);
```

### Ingestion

CLI tool to index a directory of Markdown/text
files:
1. Recursive directory traversal
2. Preprocessing (NUL characters, optionally
   base64 image data if captioning is not
   available)
3. Recursive chunking (configurable size and
   overlap, defaults: 2048/128)
4. Embedding (GPU → API → CPU)
5. Insert into SQLite

### MCP tools exposed

- `search_docs(query, top_k)`: semantic search,
  returns chunks with score and source
- `list_sources()`: list indexed files with
  chunk counts

## 3. Technical constraints

### Rigor regime

Any technical assertion (configuration, component
behavior, compatibility, procedure) is
**Unverified** by default. Training memory alone
is never sufficient.

Promotion to **Verified** only if traceable to:
- Official component documentation
- Test performed and result recorded
- Verifiable community source (GitHub issue,
  Stack Overflow accepted answer)

### Technology selection criteria

Technologies must be selected based on:
1. **Free/libre license** (MIT, Apache 2.0, BSD,
   LGPL, GPL) — proprietary or restrictive
   licenses are excluded
2. **Red Hat recommendations** when applicable
3. **Community vitality** (GitHub stars, forks,
   commit frequency, forum activity, releases)
4. **Performance** (benchmarks, not claims)
5. **Popularity and ecosystem** (adoption,
   integrations, documentation quality)

### Recommendation hierarchy

1. **Red Hat recommendations** — official docs,
   supported procedures, vendor best practices
2. **Upstream software recommendations** —
   official project docs, best practices
3. **Community recommendations** — articles,
   blogs, verified experience reports

### Chosen technologies

| Component | Technology | License | Stars | Why |
|-----------|-----------|---------|-------|-----|
| Language | Python | PSF | — | ML ecosystem, sentence-transformers native |
| MCP SDK | FastMCP (mcp) | MIT | — | Official Anthropic SDK |
| Embedding | sentence-transformers | Apache 2.0 | 17k+ | De facto standard, native GPU, HuggingFace |
| Vector store | sqlite-vec | MIT | 6k+ | Single file, portable, SQL standard |
| Chunking | langchain-text-splitters | MIT | — | RecursiveCharacterTextSplitter, popular |
| Default model | BAAI/bge-m3 | MIT | 4k+ | Multilingual, 1024d, recommended by Red Hat |

All dependencies must have a free/libre license.
Verify license before adding any dependency.

### Performance targets

- `search_docs` query: < 500ms CPU, < 50ms GPU
- Ingestion: GPU > remote API > CPU
- The `.db` file is loaded on first query,
  not at MCP startup

### Embedding model

- Configurable via environment variable
- Default: BAAI/bge-m3 (1024d, multilingual,
  MIT, recommended by Red Hat for AutoRAG)
- Changing the model invalidates the existing
  index

## 4. License and publication

### License

**MIT** — maximally permissive, compatible with
the Red Hat ecosystem and all dependency
licenses.

### GitHub publication

- **Public** repository on GitHub
- Name: `mcp-rag-local` (or to be validated)
- All code, comments, documentation in **English**

### Security — sensitive data

**FORBIDDEN** in commits:
- Passwords, tokens, API keys
- Private IP addresses, internal domain names
- Machine-specific absolute paths
- `.db` index files (contain the corpus)
- Corpus files (indexed documents)

Examples use generic placeholder values.
Real credentials are passed via environment
variables.

## 5. Git workflow

### Branches

- `main`: protected branch, stable
- **Direct commits to main are forbidden** —
  always go through a branch + merge
- One branch per topic/feature
- Branch naming: `feat/<topic>`, `fix/<topic>`,
  `docs/<topic>`
- **Do not delete branches after merge** —
  history is preserved in the branch
- **Push all branches** to the GitHub remote

### Commits

- Messages in English
- Format: imperative verb + short description
- No sensitive data (see §4)
- Check `git diff --cached` before every commit
  to detect secrets

### Merge

- Merge with fast-forward (no `--no-ff`) —
  history lives in branches
- Keep branches after merge

## 6. Example data

The repository must include a sample `.db` file
for quick testing. The example corpus **must not**
be Red Hat documentation (access-controlled).

Use a **freely available** online documentation
with illustrations whose understanding requires
the images. For example: an open-source book, a
creative commons comic, or a freely licensed
technical manual.

**Research and selection of the example corpus
is a task for the mcp-rag-local session.**

## 7. Initial backlog

Proposed feature roadmap:

- [ ] Core: SQLite + sqlite-vec storage backend
- [ ] Core: embedding with GPU/API/CPU fallback
- [ ] Core: MCP server with search_docs and
  list_sources tools
- [ ] Core: CLI ingestion tool
- [ ] Core: example `.db` with freely licensed
  corpus
- [ ] Feature: incremental re-indexing (add new
  files without full rebuild)
- [ ] Feature: configurable chunking strategies
  (recursive, fixed, semantic)
- [ ] Feature: metadata filtering in queries
  (by source file, by date)
- [ ] Feature: hybrid search (vector + keyword)
- [ ] Feature: export/import between pgvector
  and SQLite
- [ ] Feature: multi-model support (switch
  embedding models, maintain separate indexes)
- [ ] Quality: unit tests and integration tests
- [ ] Quality: CI/CD with GitHub Actions
- [ ] Docs: comprehensive README with quickstart
- [ ] Docs: architecture decision records (ADRs)
- [ ] Packaging: pip installable (`pip install
  mcp-rag-local`)
- [ ] Packaging: Docker image for standalone use

## 8. Context — where this project comes from

This project was extracted from work done in an
OpenShift AI (RHOAI 3.4) lab on a personal SNO
cluster. Study E1.08 (SDG Hub + AutoRAG)
validated bge-m3 as the optimal embedding model
(+13% vs nomic-embed on a Red Hat corpus). Study
E1.04 produced a working MCP prototype with
pgvector.

This project makes the MCP component standalone,
independent of OpenShift infrastructure (pgvector,
Llama Stack, Milvus).

### Validated technical decisions

- bge-m3 1024d: best score on multilingual
  technical corpus (verified by AutoRAG benchmark)
- Recursive chunking 2048/128: best score with
  bge-m3 on 6 documents (verified)
- Cosine similarity: standard distance for
  normalized embeddings
- sqlite-vec: community choice for single-file
  local vector store (verified by comparative
  research)
- sentence-transformers: de facto standard for
  Python embedding, native CUDA GPU support

### Reference prototype

The `reference/` directory contains the working
prototype from the lab. It serves as an
**implementation reference**, not code to copy
as-is (it contains lab-specific patterns).

## 9. Project structure

```
mcp-rag-local/
├── CLAUDE.md
├── LICENSE            (MIT)
├── README.md
├── pyproject.toml
├── src/
│   └── mcp_rag_local/
│       ├── __init__.py
│       ├── server.py      (MCP server)
│       ├── embedder.py    (GPU/API/CPU embedding)
│       ├── store.py       (SQLite + sqlite-vec)
│       └── ingest.py      (chunking + indexing)
├── tests/
├── examples/
│   ├── config.json    (.mcp.json example)
│   └── sample.db      (example index)
├── reference/         (lab prototypes)
└── .gitignore
```
