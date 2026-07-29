# CLAUDE.md — lore-mcp

## 1. Project overview

### What

**lore-mcp** (LORE — Local Offline Retrieval
Engine) is an MCP (Model Context Protocol)
server for semantic search over a corpus of
technical documents. Runs locally on the
workstation with no mandatory network dependency.
Uses sqlite-vec for portable vector storage
(single file).

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
   `/v1/embeddings`.
3. **Local CPU**: sentence-transformers in CPU
   mode. Slower (~200ms) but self-contained.

### Environment variables

| Variable | Role | Default |
|----------|------|---------|
| `LORE_DB_PATH` | SQLite database file path | `./lore.db` |
| `LORE_MODEL` | Embedding model name | `BAAI/bge-m3` |
| `LORE_EMBED_MODE` | Embedding mode: `auto`, `gpu`, `api`, `cpu` | `auto` |
| `LORE_API_URL` | Remote `/v1/embeddings` endpoint URL | *(none — required if mode is `api`)* |
| `LORE_API_MODEL` | Model name for the remote API | same as `LORE_MODEL` |

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

CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
-- Stores: model_name, model_dim, created_at
-- The server refuses to query an index whose
-- stored model does not match the current
-- LORE_MODEL value.
```

### Ingestion

CLI tool to index a directory of Markdown/text
files:
1. Recursive directory traversal
2. Preprocessing: strip NUL characters, strip
   base64 image data (captioning is out of
   scope for v1)
3. Recursive chunking (configurable size and
   overlap, defaults: 2048/128)
4. Embedding (GPU → API → CPU)
5. Insert into SQLite with model metadata

### MCP tools exposed

- `search_docs(query, top_k=5)`: semantic search,
  returns chunks with score and source.
  `top_k` is a parameter with default 5.
- `list_sources()`: list indexed files with
  chunk counts

## 3. AI-assisted development

This project uses AI-assisted development.
All public-facing content must comply with the
guidelines in `docs/ai-guidelines.md`.

Key rules:
- **Human review**: all AI output reviewed,
  tested, validated before inclusion
- **Marking**: commits with substantial AI
  content use `Co-Authored-By` trailer
- **No confidential data** in prompts, code,
  or examples
- **No copyright claim** on substantially
  AI-generated content with minimal human input
- **Upstream respect**: check AI policies of
  any project we contribute to

Public reference:
https://www.redhat.com/en/blog/ai-assisted-development-supercharging-open-source-way

## 4. Technical constraints

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

| Component | Technology | License | Why |
|-----------|-----------|---------|-----|
| Language | Python ≥ 3.10 | PSF | ML ecosystem, sentence-transformers native |
| MCP SDK | FastMCP (mcp) | MIT | Official Anthropic SDK |
| Embedding | sentence-transformers | Apache 2.0 | De facto standard, native GPU, HuggingFace |
| Vector store | sqlite-vec | MIT | Single file, portable, SQL standard |
| Chunking | langchain-text-splitters | MIT | RecursiveCharacterTextSplitter, popular |
| Default model | BAAI/bge-m3 | MIT | Multilingual, 1024d, recommended by Red Hat |

All dependencies must have a free/libre license
compatible with GPL v3. Verify license before
adding any dependency.

### Performance targets

- `search_docs` query: < 500ms CPU, < 50ms GPU
- Ingestion: GPU > remote API > CPU
- The `.db` file is loaded on first query,
  not at MCP startup

### Embedding model

- Configurable via `LORE_MODEL` environment
  variable
- Default: BAAI/bge-m3 (1024d, multilingual,
  MIT, recommended by Red Hat for AutoRAG)
- Changing the model invalidates the existing
  index. The `meta` table stores the model name
  and dimension; the server raises an error if
  the current model does not match.

## 5. License and publication

### License

**GPL-3.0-or-later** — copyleft, patent
protection, ensures derivative works remain free
software. See `docs/adr/001-license-gpl-v3.md`
for the full study.

Compatible with all project dependencies (MIT,
Apache 2.0) and with the MCP ecosystem (separate
process communication, no code linking).

### GitHub publication

- **Public** repository on GitHub
- Name: **lore-mcp**
  (see `docs/adr/002-project-name.md`)
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

## 6. Git workflow

### Branches

- `main`: protected branch, stable. Its history
  contains **only merge commits** (no direct
  work commits).
- **Direct commits to main are forbidden** —
  always go through a branch + merge.
- One branch per topic/feature.
- Branch naming: `feat/<topic>`, `fix/<topic>`,
  `docs/<topic>`.
- **Sub-branches**: if a topic has sub-topics,
  create sub-branches (e.g.
  `feat/store/meta-table`). The same merge rule
  applies recursively — a sub-branch merges into
  its parent branch only when the sub-topic is
  closed.
- **Do not delete branches after merge** —
  history is preserved in the branch.
- **Push all branches** to the GitHub remote.

### Commits

- Messages in English
- Format: imperative verb + short description
- No sensitive data (see §5)
- Check `git diff --cached` before every commit
  to detect secrets

### Merge

- Merge with `--no-ff` (always create a merge
  commit). This ensures `main` history shows
  only merge points, and the detailed work
  history lives in the branches.
- Merge to parent only when the topic is
  considered **closed** (feature complete,
  reviewed, tested).
- Keep branches after merge.

### Synchronization

At every **pause** (end of work session, context
switch, or user request):
1. All changes committed (no uncommitted work)
2. All branches pushed to the remote
3. README and documentation synchronized with
   the current state

## 7. Example data

The repository must include a sample `.db` file
for quick testing. The example corpus **must not**
be Red Hat documentation (access-controlled).

Use a **freely available** online documentation
with illustrations whose understanding requires
the images. For example: an open-source book, a
creative commons comic, or a freely licensed
technical manual.

### Selection criteria

- License: CC BY, CC BY-SA, MIT, Apache 2.0, or
  equivalent free/libre license
- Language: English (primary) or multilingual
- Content: technical documentation with images
- Size: sufficient to demonstrate chunking and
  search (10+ pages)

Selection is tracked in the backlog (§8).

## 8. Backlog

### MVP (v0.1.0) — TDD approach

Development follows Test-Driven Development:
write tests first, then implement.

- [ ] Core: SQLite + sqlite-vec storage backend
  with meta table
- [ ] Core: embedding with GPU/API/CPU fallback
- [ ] Core: MCP server with `search_docs` and
  `list_sources` tools
- [ ] Core: CLI ingestion tool
- [ ] Quality: unit tests and integration tests
  (written before implementation)
- [ ] Docs: README with quickstart
- [ ] Packaging: `pyproject.toml` with entry
  points

### Post-MVP

- [ ] Example: census of candidate corpora for
  the sample `.db`
- [ ] Example: select and index the example
  corpus
- [ ] Feature: incremental re-indexing (add new
  files without full rebuild)
- [ ] Feature: configurable chunking strategies
  (recursive, fixed, semantic)
- [ ] Feature: metadata filtering in queries
  (by source file, by date)
- [ ] Feature: hybrid search (vector + keyword)
- [ ] Feature: image captioning during ingestion
  (v2 — replace base64 stripping with
  AI-generated captions)
- [ ] Feature: export/import between pgvector
  and SQLite
- [ ] Feature: multi-model support (switch
  embedding models, maintain separate indexes)
- [ ] Quality: CI/CD with GitHub Actions
- [ ] Docs: architecture decision records (ADRs)
  for future decisions
- [ ] Packaging: `pip install lore-mcp`
- [ ] Packaging: Docker image for standalone use

## 9. Context — where this project comes from

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

The `docs/studies/reference/` directory contains
the working prototype from the lab. It serves as
an **implementation reference**, not code to copy
as-is (it contains lab-specific patterns like
pgvector and hardcoded URLs).

## 10. Project structure

```
lore-mcp/
├── CLAUDE.md              # Claude instructions
├── LICENSE                # GPL v3
├── README.md              # Showcase: presentation,
│                          #   quickstart, roadmap
├── pyproject.toml         # Packaging
│
├── docs/                  # Documentation
│   ├── ai-guidelines.md   #   AI-assisted dev rules
│   ├── architecture.md    #   Technical
│   ├── configuration.md   #   Technical
│   ├── adr/               #   Studies/reflections
│   │   ├── 001-license-gpl-v3.md
│   │   └── 002-project-name.md
│   └── studies/           #   Studies/reflections
│       └── reference/     #   Lab prototypes
│
├── src/                   # Code
│   └── lore_mcp/
│       ├── __init__.py
│       ├── server.py      # MCP server
│       ├── embedder.py    # GPU/API/CPU embedding
│       ├── store.py       # SQLite + sqlite-vec
│       └── ingest.py      # Chunking + indexing
│
├── tests/                 # Code (tests)
│
└── examples/              # Showcase
    └── mcp-config.example.json
```

## 11. Workspace organization

The project is organized into four conceptual
spaces, each with a clear purpose:

| Space | Purpose | Location |
|-------|---------|----------|
| **Studies** | Research, ADRs, reflections, lab prototypes | `docs/adr/`, `docs/studies/` |
| **Technical docs** | Architecture, configuration, API reference | `docs/` (root-level `.md` files) |
| **Code** | Source code and tests | `src/`, `tests/` |
| **Showcase** | Files for GitHub visitors: project presentation, quickstart, examples | `README.md`, `LICENSE`, `examples/` |

All documentation must be kept in sync with the
code. The README must always reflect the current
state of the project (features implemented,
installation procedure, roadmap).

## 12. Instructions for Claude

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

### Development methodology

- **TDD**: write tests before implementation
- **Commits**: check `git diff --cached` before
  every commit to detect secrets or unintended
  changes. Follow the pre-commit checklist in
  `docs/ai-guidelines.md` §5.
- **Marking**: every commit with AI-assisted
  content must include a `Co-Authored-By` trailer
- **Pause protocol**: at every pause, ensure all
  changes are committed and all branches pushed.
  Update README and docs if the project state
  has changed.
