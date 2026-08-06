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
  content use `Assisted-by` and `Co-Authored-By`
  trailers
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

Development follows TDD: write tests before
implementation for all `[P]` items.

Item types: `[E]` study/grooming, `[P]` PoC
(implementation), `[D]` demo/tutorial.

### E0. Project initialization

- [x] E0.01 [E] License study: evaluate MIT, Apache 2.0, GPL v3 against FSF/APRIL/OSI positions
- [x] E0.02 [E] Project name study: explore naming candidates, select lore-mcp (LORE)
- [x] E0.03 [P] Initialize repository: git, directory structure (4 spaces), .gitignore, GPL v3 LICENSE
- [x] E0.04 [D] Write ADR-001 (license choice) and ADR-002 (project name)
- [x] E0.05 [P] Write CLAUDE.md with all project decisions
- [x] E0.06 [D] AI-assisted development guidelines (docs/ai-guidelines.md)
- [x] E0.07 [P] README skeleton with quickstart placeholder and roadmap
- [x] E0.08 [P] pyproject.toml skeleton with dependencies and entry points
- [x] E0.09 [D] CONTRIBUTING.md with git workflow, AI guidelines, and license terms

### E1. Core (MVP v0.1.0)

- [x] E1.01 [P] SQLite + sqlite-vec storage backend with meta table
- [x] E1.02 [P] Embedding engine with GPU/API/CPU automatic fallback
- [x] E1.03 [P] MCP server exposing search_docs and list_sources tools
- [x] E1.04 [P] CLI ingestion tool (directory traversal, preprocessing, chunking, indexing)

### E2. Quality

- [x] E2.01 [P] Unit tests for store, embedder, and ingest modules (TDD — written before E1)
- [x] E2.02 [P] Integration tests for MCP server end-to-end
- [ ] E2.03 [P] CI/CD with GitHub Actions

### E3. Documentation

- [x] E3.01 [D] Architecture documentation (docs/architecture.md)
- [x] E3.02 [D] Configuration reference (docs/configuration.md)
- [x] E3.03 [D] README quickstart with working end-to-end examples

### E4. Packaging

- [x] E4.01 [P] MCP client configuration example (examples/mcp-config.example.json)
- [ ] E4.02 [P] pip installable package (publish to PyPI)
- [ ] E4.03 [P] Docker image for standalone use

### E5. Search enhancements

- [ ] E5.01 [E] Per-source result cap study (max N chunks per file) — see rag-quality-observations.md
- [ ] E5.02 [P] Metadata filtering in queries (by source file, by date)
- [ ] E5.03 [P] Hybrid search (vector + keyword)

### E6. Ingestion enhancements

- [ ] E6.01 [P] Incremental re-indexing (add/update files without full rebuild)
- [ ] E6.02 [E] Configurable chunking strategies study (recursive, fixed, semantic)
- [ ] E6.03 [P] Image captioning during ingestion (replace base64 stripping with AI-generated captions)

### E7. Interoperability

- [ ] E7.01 [P] Export/import between pgvector and SQLite
- [ ] E7.02 [P] Multi-model support (switch embedding models, maintain separate indexes)

### E8. Example corpus

- [ ] E8.01 [E] Census of candidate corpora for the sample .db (license, content, size evaluation)
- [ ] E8.02 [E] Select example corpus based on E8.01 criteria
- [ ] E8.03 [P] Index selected corpus and include sample.db in repository

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
├── CONTRIBUTING.md        # Showcase: contribution rules
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

### Language

- Conversation with the user: **French**
- Code, comments, docstrings, documentation,
  commit messages, PR descriptions: **English**

### Development methodology

- **TDD cycle**: write test → verify it fails →
  implement → verify it passes → refactor.
  No implementation without a failing test first.
- **Commits**: check `git diff --cached` before
  every commit to detect secrets or unintended
  changes. Follow the pre-commit checklist in
  `docs/ai-guidelines.md` §5.
- **Marking**: every commit with AI-assisted
  content must include both `Assisted-by` and
  `Co-Authored-By` trailers (see CONTRIBUTING.md)
- **Pause protocol**: at every pause, ensure all
  changes are committed and all branches pushed.
  Update README and docs if the project state
  has changed.

### Documentation strategy

Two layers, always in sync:

- **In code** (docstrings, inline comments):
  minimal exhaustive — full breadth, not full
  depth. Every public function, class, and module
  gets a short docstring (1-3 lines). Cover the
  entire public surface. Reference the relevant
  technical doc for details
  (e.g. `See docs/architecture.md`).
- **In technical docs** (`docs/`): full depth —
  rationale, design considerations, trade-offs,
  pedagogy. Reference specific code locations
  (e.g. `store.py:open_db()`). Explain WHY, not
  just WHAT.

Cross-references are **bidirectional**: code
points to docs, docs point to code.

### Upstream contributions

Before proposing a contribution to any upstream
or external open source project:
1. Check the project's contribution guidelines
   (CONTRIBUTING.md, DCO, CLA requirements)
2. Check the project's policy on AI-generated
   contributions — some projects prohibit them
3. Verify license compatibility
4. Comply with all applicable policies

If a project prohibits AI-generated contributions,
do not contribute AI-assisted code to it.

### Backlog management

- **Format**: epics numbered `E<n>`, items
  identified `E<epic>.<seq>`, checkboxes
  `[x]`/`[ ]`, one descriptive line per item.
  Types: `[E]` study, `[P]` PoC, `[D]` demo.
- **IDs are permanent**: never renumber or recycle
  an ID. Deleted or merged items stay marked as
  such. New items get the next sequential number
  in their epic.
- **Reference IDs** in conversation and commit
  messages (e.g. "Implement E1.01").
- **Keep in sync**: update §8 after each
  significant change (item added, completed,
  reprioritized).
- **On "la suite?" or "backlog"**: display the
  full backlog from §8 with status, including
  recently completed items. Do not summarize
  or omit items.
- **End of iteration**: remind the full backlog
  with priorities and status.
