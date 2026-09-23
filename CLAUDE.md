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
   configurable model (default: nomic-embed-text-v2-moe,
   768 dimensions). Fastest (~20ms/query).
2. **Remote API** (OpenAI-compatible): vLLM,
   Llama Stack, or any service implementing
   `/v1/embeddings`.
3. **Local CPU**: sentence-transformers in CPU
   mode. Slower (~200ms) but self-contained.

### Environment variables

| Variable | Role | Default |
|----------|------|---------|
| `LORE_DB_PATH` | SQLite database file path | `./lore.db` |
| `LORE_MODEL` | Embedding model name | `nomic-ai/nomic-embed-text-v2-moe` |
| `LORE_EMBED_MODE` | Embedding mode: `builtin`, `builtin:gpu`, `builtin:cpu`, `api` | `builtin` |
| `LORE_API_URL` | Remote `/v1/embeddings` endpoint URL | *(none — required if mode is `api`)* |
| `LORE_API_MODEL` | Model name for the remote API | same as `LORE_MODEL` |
| `LORE_DB_DIR` | Directory of `.db` files (multi-collection) | *(none)* |
| `LORE_API_VERIFY` | SSL verification for API (`true`/`false`) | `true` |
| `LORE_API_CA_BUNDLE` | Custom CA certificate path | *(system CA)* |
| `LORE_CHUNK_SIZE` | Chunk size in characters | `1024` |
| `LORE_CHUNK_OVERLAP` | Chunk overlap in characters | `128` |
| `LORE_LLM_URL` | Chat LLM endpoint for eval | *(required for eval)* |
| `LORE_LLM_MODEL` | Judge model name | `granite-8b-instruct` |

### Vector storage

**SQLite + sqlite-vec**: a single portable `.db`
file. No server, no network. The file is
distributable.

Table schema:
```sql
CREATE VIRTUAL TABLE chunks_vec USING vec0(
  embedding float[768]
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
- `list_indexed_sources()`: list indexed files
  with chunk counts
- `list_collections()`: list available `.db`
  collections (multi-collection mode)

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
| MCP SDK | MCPServer (mcp v2) | MIT | Official Anthropic SDK |
| Embedding | sentence-transformers | Apache 2.0 | De facto standard, native GPU, HuggingFace |
| Vector store | sqlite-vec | MIT | Single file, portable, SQL standard |
| Chunking | langchain-text-splitters | MIT | RecursiveCharacterTextSplitter, popular |
| Default model | nomic-embed-text-v2-moe | Apache 2.0 | Level 2 libre, multilingual, 768d, MoE. See ADR-005 |

All dependencies must have a free/libre license
compatible with AGPL v3. Verify license before
adding any dependency.

### Performance targets

- `search_docs` query: < 500ms CPU, < 50ms GPU
- Ingestion: GPU > remote API > CPU
- The `.db` file is loaded on first query,
  not at MCP startup

### Embedding model

- Configurable via `LORE_MODEL` environment
  variable
- Default: nomic-ai/nomic-embed-text-v2-moe
  (768d, multilingual, Apache 2.0, Level 2 libre).
  See ADR-005
- Changing the model invalidates the existing
  index. The `meta` table stores the model name
  and dimension; the server raises an error if
  the current model does not match.

## 5. License and publication

### License

**AGPL-3.0-or-later** — copyleft with network
clause (section 13), patent protection. If
someone forks lore-mcp and deploys it as a
service, they must provide the source. Migrated
from GPL-3.0 per openshift sync decision
(2026-08-30). See `docs/adr/001-license-gpl-v3.md`
for the original study.

Studies and original documentation are under
**CC-BY-SA 4.0** (share-alike, copyleft content).

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

### Cross-workspace sync

The `sync/` directory handles synchronization
between lore-mcp and linked workspaces.

- `sync/links.md`: table of linked projects
  with paths to their sync files and branches
- `sync/<project>.md`: outgoing sync file
  (maintained by lore-mcp, read by the linked
  project)
- Incoming sync files live in the linked
  project's workspace (read-only from here)
- **Broadcast** (`claude/sync/broadcast.md`):
  transversal rules shared across all projects.
  Read at every sync alongside project-specific
  files.

**Read incoming files from the main branch**, not
the current working tree. The linked workspace
may be on a feature branch with unvalidated
changes. Use `git -C <workspace> show main:<path>`
to read the version merged on main.

Note: the default branch may be `master` instead
of `main` — check per workspace.

At every **pause**, read incoming sync files
from linked projects (see `sync/links.md`) and
apply any new decisions. Update outgoing sync
files with lore-mcp's current state.

Each repository maintains only its own outgoing
files. Incoming files are never copied — they
are read from the linked workspace's path.

Consumer demands (bugs, missing docs) in incoming
sync files are **not fixed directly at sync**.
Each demand generates a backlog item following
the normal lifecycle (grooming → MVP → review).

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

- `Revue` E0.01 [E] License study: evaluate MIT, Apache 2.0, GPL v3 against FSF/APRIL/OSI positions
- `Revue` E0.02 [E] Project name study: explore naming candidates, select lore-mcp (LORE)
- `Revue` E0.03 [P] Initialize repository: git, directory structure (4 spaces), .gitignore, GPL v3 LICENSE
- `Revue` E0.04 [D] Write ADR-001 (license choice) and ADR-002 (project name)
- `Revue` E0.05 [P] Write CLAUDE.md with all project decisions
- `Revue` E0.06 [D] AI-assisted development guidelines (docs/ai-guidelines.md)
- `Revue` E0.07 [P] README skeleton with quickstart placeholder and roadmap
- `Revue` E0.08 [P] pyproject.toml skeleton with dependencies and entry points
- `Revue` E0.09 [D] CONTRIBUTING.md with git workflow, AI guidelines, and license terms

### E1. Core (MVP v0.1.0)

- `Revue` E1.01 [P] SQLite + sqlite-vec storage backend with meta table
- `Revue` E1.02 [P] Embedding engine with GPU/API/CPU automatic fallback
- `Revue` E1.03 [P] MCP server exposing search_docs and list_indexed_sources tools
- `Revue` E1.04 [P] CLI ingestion tool (directory traversal, preprocessing, chunking, indexing)

### E2. Quality

- `Revue` E2.01 [P] Unit tests for store, embedder, and ingest modules (TDD — written before E1)
- `Revue` E2.02 [P] Integration tests for MCP server end-to-end
- `Implémenté` E2.03 [P] CI/CD with GitHub Actions: pytest on push/PR, Python 3.13, pip cache, tesseract-ocr-fra, badge in README

### E3. Documentation

- `Revue` E3.01 [D] Architecture documentation (docs/architecture.md)
- `Revue` E3.02 [D] Configuration reference (docs/configuration.md)
- `Revue` E3.03 [D] README quickstart with working end-to-end examples
- `Implémenté` E3.04 [D] Documentation reorganization: separate tutorial from configuration reference, update README to reflect current state
- `À faire` E3.05 [D] Tutorial GPU prerequisites: TEI tag by GPU arch (sm_89→1.9.3, sm_120→120-1.9.3), nvidia-container-toolkit for Podman, CDI setup, CUDA 13.x compatibility warning
- `Implémenté` E3.06 [D] Preprocessing guide: best practices for preparing markdown sources for RAG indexing. Cover image stripping (alt text preserved), heading structure (structural signal for chunking, strip # from queries), noise detection (numeric sequences, trivial content), text density, heading/content coherence. Reference measured impact: preprocessing ~60% of RAG quality vs model ~15%.

### E4. Packaging

- `Revue` E4.01 [P] MCP client configuration example (examples/mcp-config.example.json)
- `Implémenté` E4.02 [P] pip installable package: wheel builds, installs, CLI works. Version 0.1.0.dev1. Missing deps added (charset-normalizer, pyyaml). PyPI publish pending (needs account + token)
- `À faire` E4.03 [P] Docker image for standalone use
- E4.04 — removed (covered by `lore-mcp build --skip-optimize` since E11.01)
- E4.05 — moved to openshift workspace (data repository, not tooling)
- E4.06 — moved to openshift workspace (data repository, not tooling)

### E5. Search enhancements

- `Implémenté` E5.01 [E] Per-source result cap study (max N chunks per file) — see rag-quality-observations.md
- `Implémenté` E5.02 [P] Metadata filtering in queries (by source file, by date)
- `Implémenté` E5.03 [E] Hybrid search study: BM25 (FTS5) + vector (sqlite-vec) with RRF fusion — ref: sqlite-rag-mcp. Priority: high (+13pts recall@10, E14.17)
- `Implémenté` E5.04 [P] Hybrid search implementation
- `Implémenté` E5.05 [E] int8/binary quantification study: float32 sufficient for <50K chunks, int8 ~99.5% recall (4x compact), bit ~95% (32x). Nomic v2 supports Matryoshka 768→256. Implementation deferred. See study-E5.05-quantization.md
- `Implémenté` E5.06 [E] Reranking study: cross-encoder reranking after vector retrieval (+5-15pts nDCG@10 per E14.17). Evaluate cross-encoder models (bge-reranker, ms-marco), integration point, latency budget
- `Implémenté` E5.07 [P] Reranking implementation
- `Implémenté` E5.08 [P] Adjacent-chunk retrieval: return surrounding chunks merged at retrieval time (window_size configurable). No ingestion change. Depends on E5.11 study
- `Implémenté` E5.11 [E] Context window retrieval study: evaluate adjacent-chunk (dynamic window at retrieval, E5.08) vs parent-child (double indexation, E6.08). Benchmarks, cohabitation or exclusion, LlamaIndex SentenceWindow vs AutoMerging patterns. Determine: merge results before LLM (industry standard). Informs E10.29 optimize dimension
- E5.10 — removed (no concrete need — E14.17 identifies the problem as retrieval redundancy, not indexation duplication. Solutions: E5.01 per-source cap, E5.12 MMR at retrieval)
- `Implémenté` E5.12 [P] MMR at retrieval: Maximal Marginal Relevance to diversify search results. Penalize similarity between already-selected chunks. −30-50% redundant tokens per E14.17. Configurable via config.yaml
- `Implémenté` E5.13 [P] Pre-filtering: metadata pre-filter via rowid IN before KNN. Replaces post-filter anti-pattern. source_file, level, license, title, author, date_from/to all pre-filtered via SQL JOIN on chunks+sources tables. _apply_filters removed. See grooming-E5.13.md
- `Implémenté` E5.09 [E] Heading markers in RAG pipeline study: evaluate impact of `#` in indexed chunks vs queries. Current clean_text strips `#` from headings before chunking — this breaks MD_SEPARATORS (`\n## `, `\n### `). E14.17 found no external source for strip benefit. Determine: keep `#` in chunks (structural signal for chunking), strip from queries only (search_docs), or strip after chunking. Revert clean_text strip if confirmed harmful

### E9. Multi-collection and license classification (prérequis MVP1 openshift)

- `Revue` E9.01 [E] Multi-collection design: one .db per theme, naming `<theme>-<level>.db`, levels: nda/libre/redist/gray
- `Revue` E9.02 [P] `LORE_DB_DIR` env var: point to a directory of .db files (LORE_DB_PATH kept for single-collection compat)
- `Revue` E9.03 [P] `search_docs(query, top_k, collection)`: optional collection param, cross-corpus merge by score without param
- `Revue` E9.04 [P] `list_collections()`: new MCP tool listing available .db files with chunk/file counts per collection
- `Revue` E9.05 [P] Ingestion `--collection`: collection name determines output .db file

### E6. Ingestion enhancements

- `Implémenté` E6.01 [P] Declarative DB sync: manifest is source of truth. On build, purge DB entries absent from manifest, skip unchanged (hash match), re-ingest changed (hash mismatch), add new. Full rebuild = special case (empty DB or --force). See grooming-E6.01.md
- `Implémenté` E6.02 [P] Migrate to MarkdownTextSplitter: replace RecursiveCharacterTextSplitter with MarkdownTextSplitter (same langchain-text-splitters package). Tables, headings, code blocks protected natively. Remove custom sentinel code (tables.py). No study needed — standard solution
- `Implémenté` E6.04 [P] Configurable chunk_size/overlap via env vars — default changed from 2048 to 1024 per AutoRAG E1.08 benchmark. Chunk params stored in meta table for traceability.
- E6.03 — absorbed by E12.15 (detection) + E12.16 (VLM captioning) + E12.26 (sequential pipeline phase 2)
- `Implémenté` E6.05 [P] Per-collection metadata: sources table in DB, manifest YAML input, biblio in search results, .json/.bib/.md output, front matter extraction.
- `Implémenté` E6.06 [E] Multi-format ingestion study: evaluate markitdown, pymupdf4llm, trafilatura for PDF/HTML/DOCX/EPUB → text conversion. Assess integration as preprocessing step before chunking. E14.17 recommends: Docling (MIT, 97.9%), trafilatura (Apache 2.0, F1 0.966)
- `À faire` E6.07 [P] Lint improvements: add heading hierarchy validation (## before ###, no skipped levels), binary/base64 content detection, numeric sequence detection. Enhance existing `lint.py` analysis
- `Implémenté` E12.51 [P] Clean repeated non-alpha characters: collapse non-alphanumeric 4+ to 3 (preserves ellipsis, headings, table pipes). Collapse spaces 2+ to 1. Remove whitespace-only lines. Fixes false POOR quality gate on DOCX/XLSX
- `Implémenté` E6.08 [P] Parent-child chunking: double indexation (parent + child chunks), parent_id link, retrieve parent for context (+15-25% answer precision per E14.17). Depends on E5.11 study
- E6.09 — absorbed by E12.02 (preprocessing hardening)
- `Implémenté` E6.10 [E] Per-source chunking params study: vary chunk_size/overlap per source or collection in build-config YAML. Content-dependent chunking (E14.17 Cohere pattern)

### E7. Interoperability

- E7.01 — deferred (no second backend = premature abstraction. Revisit when pgvector is needed — the second backend will guide what to abstract)
- E7.02 — absorbed by E9 (multi-collection: one .db per model)
- E7.03 — deferred (pgvector is an openshift infra need, not lore-mcp standalone. Depends on E7.01)

### E10. RAG evaluation (openshift demand 2026-08-31)

- `Implémenté` E10.01 [E] RAG evaluation design. RAGAS seul suffit, SDG Hub hors scope. Extractive fallback sans dépendance. LORE_LLM_URL/MODEL pour RAGAS.
- `Implémenté` E10.02 [P] `lore-mcp eval` — evaluate retrieval quality.
- `Implémenté` E10.03 [P] `lore-mcp optimize` — auto-optimize chunking params.
- `Implémenté` E10.04 [P] `lore-mcp optimize --manifest` — optimize with manifest to preserve bibliographic metadata.
- E10.05 — absorbed by E10.09 (multi-model optimize already implemented)
- `Implémenté` E10.08 [P] Auto-configure embedding model from .db meta: if config has no embedding.model, read model_name from DB meta at first load. Error if neither configured nor in DB
- `Implémenté` E10.10 [P] Rename mode `auto` → `builtin` with `:gpu`/`:cpu` suffix.
- `Implémenté` E10.11 [P] `Embedder.unload()` — free GPU/CPU memory between models.
- `Implémenté` E10.12 [D] TEI docs + default model → Nomic v2 MoE (Level 2) + ADR-005.
- `Implémenté` E10.13 [E] Unified build config YAML (BuildConfig).
- `Implémenté` E10.14 [P] Wire BuildConfig into build/optimize CLI (--config flag).
- `Implémenté` E10.15 [P] RAGAS scoring wired. metrics/judge passed through pipeline. Embedding metrics stored.
- `Implémenté` E10.16 [P] Fix OOM multi-model GPU (gc.collect in unload).
- `Implémenté` E10.17 [P] Configurable batch size: `LORE_BATCH_SIZE` env var (default 64).
- `Implémenté` E10.18 [E] Embedding API resilience: retry with backoff, batch reduction on 422, fail fast on 401/404, consecutive error threshold.
- `Implémenté` E10.19 [P] RAGAS guard: warning judge unused, error RAGAS without judge/ragas.
- `Implémenté` E10.20 [P] Observability: ProgressReporter with ★ best column, sections, timing, Markdown summary.
- `Implémenté` E10.21 [P] Config unification: `embedding:` key only, `--models` removed, error on old keys.
- E10.22 — removed (no value, shelved since creation)
- `Implémenté` E10.24 [P] Output management: clean default output (no lib noise), --verbose for detailed lore-mcp output, --debug for internal logs. Silence all third-party loggers (httpx, numexpr, sentence-transformers, huggingface_hub). Wire ProgressReporter with --verbose.
- `À faire` E10.25 [P] Per-model verify_ssl in embedding config: honor `verify_ssl: false` per embedding model in build-config.yaml (currently only supported for judge LLM).
- `Implémenté` E10.26 [P] Extractive question quality: filter garbage sentences (min alpha ratio, min word count, skip markdown headers, skip base64/numeric-only lines) in `_generate_extractive`.
- `Implémenté` E10.27 [P] Heading-based evaluation: generate QA pairs from document headings (heading → query, section content → ground truth) before chunking. Replace chunk-extracted questions. NDCG@k + Recall@k metrics (ir_measures or manual). Eliminates chunking bias.
- `Implémenté` E10.30 [P] Unified config file: replace all LORE_* env vars with a single `config.yaml`. Manifest = sources (portable, shareable). Config = pipeline settings (models, keys, params — local, not committed). No env var fallback. Rename build-config.yaml → config.yaml. All commands read config: serve, build, preprocess, eval, enrich
- `À faire` E10.31 [E] Default models study: decide default embedding model, reranking model, and LLM model when config does not specify them. Criteria: libre license, multilingual, quality benchmarks. Depends on E5.07 (reranking impl) — decide defaults after features exist
- `Implémenté` E10.32 [P] Config refactoring: LLM registry pattern. `llm:` top-level = list of available models (name, model, api_url, api_key). Each section (enrich, judge, parse) references models by name. List of models per section = dimensions for optimize. Replaces current flat `llm:` section. Depends on E10.30
- E10.33 — shelved (E6.10 already allows manual per-source params in manifest. Auto-detection adds complexity for marginal gain — chunking impact ~5% vs preprocessing ~60%. Revisit if benchmarks show otherwise)
- `Implémenté` E10.29 [E] End-to-end optimize: extend `lore-mcp optimize` to vary all pipeline parameters — preprocessing (dedup threshold, enrich techniques, table protection) + chunking (chunk_size, overlap) + search (top_k, reranking). Single optimization run evaluates the full pipeline against retrieval quality (NDCG, recall). Currently optimize only varies chunking params
- `À faire` E10.28 [D] Detailed eval report: markdown file with full questions, ground truths, per-model chapters, per-config sections with exhaustive Q&A and scores, scoring methodology appendix.
- `Implémenté` E10.23 [P] Fix RAGAS import crash: stub langchain_community.chat_models.vertexai before import.
- `Implémenté` E10.09 [P] AutoRAG multi-model implementation. `--models` CLI, embedding metrics (score_spread, source_diversity), MRR, model config YAML/CLI.
- `Implémenté` E10.06 [P] Fix optimize .db naming collision.
- `Implémenté` E10.07 [P] Fix optimize glob+st_mtime fragility.

### E11. Build workflow

- `Implémenté` E11.01 [P] `lore-mcp build` — single command: manifest + models → optimized .db + metadata + report. Pre-flight validation, resumability.

### E12. Preprocessing tool (E14.17 recommendations)

CLI `lore-mcp preprocess` implementing RAG
pipeline steps 1-3 (parse, clean, deduplicate).
Self-service tooling for Platform consumers.
Input: raw sources (PDF, HTML, DOCX, markdown).
Output: clean markdown + enriched manifest
(`-prep` suffix), ready for `lore-mcp build`.
Module: `src/lore_mcp/preprocess/` (separable).
CLI: `--docs-base-dir`, `--orig-subdir`,
`--prep-subdir`, `--manifest-out`.
Manifest is never modified — enriched copy only.

- `Implémenté` E12.01 [E] Preprocessing tool design: manifest field cascade (orig/path/title generated), resolve + parse + clean + extract + dedup + validate + enrich pipeline, enriched manifest output. Design v2 validated
- `Implémenté` E12.02 [P] Text normalization: Unicode NFC, strip HTML residual tags, strip NUL, image → alt text. Module `preprocess/clean.py`. Supersedes E6.09
- `Implémenté` E12.03 [P] Multi-format parsing: 4-tier cascade — md passthrough, HTML via trafilatura (Apache 2.0, F1 0.966), PDF/DOCX/PPTX/XLSX/EPUB/images via Docling (MIT, 97.9%), CSV/JSON/XML via markitdown (MIT). All optional deps. Depends on E6.06 study
- `Implémenté` E12.04 [P] Deduplication: exact hash SHA-256 + near-duplicate MinHash+LSH (datasketch, academic defaults: k=5, 128 perms, threshold=0.8). Report-only — warns on duplicates, does not remove. Measured rates: ~24% enterprise docs (E14.17)
- `Implémenté` E12.05 [P] PII detection: warn on patterns (emails, IPs, API keys, internal domains) before indexing. Report-only mode (no auto-removal). Vectors are not anonymization
- `Implémenté` E12.06 [P] Table protection: detect markdown tables, ensure they are not split across chunk boundaries. Extract large tables as structured metadata. 4-pillar approach (E14.17)
- `Implémenté` E12.07 [P] Quality gate: integrate `lore-mcp lint` as pre-flight validation. Block indexing of `poor` files unless `--force`. Warn on low text density, noise sections, heading hierarchy issues
- `Implémenté` E12.08 [E] Transversal LLM capability: study + wiring of shared LLM client for preprocessing. Evaluate techniques — contextual retrieval (−35% failures alone, −49% with hybrid BM25), Q&A mode, proposition indexing (+22.5%), metadata enrichment (+14.8pts). Define "complex document" (image-heavy, bad OCR, complex layout) and detection criteria (lint score on parser output, text density threshold). Subsumes E6.03 (image captioning). Cost/benefit, LORE_LLM_URL integration, opt-in config. Foundation for E12.03 LLM fallback and E12.09 enrich
- `Implémenté` E12.09 [P] LLM enrichment implementation: optional `--enrich` flag calling LLM to add context paragraphs (contextual retrieval) and/or generated questions (Q&A mode) per section. Depends on E12.08 study
- `Implémenté` E12.10 [P] Build integration: pipeline steps resolve params from LoreConfig autonomously. preprocess_sources(), _run_optimization() accept config param. run_build passes config to each step. Explicit params override config. CLI `--preprocess` + config YAML both work

### Bugs

- E12.11 — removed (double clean is idempotent, clean needed in both preprocess and ingest for all use cases)
- `Implémenté` E12.20 [E] Auto-manifest and full-auto mode: `lore-mcp build --docs-dir /files/ --output-dir /db/` without manifest. Scan directory for supported formats, generate manifest with extracted metadata (title, author, license from front matter or document content), preprocess, index. Manifest is optional — if absent, generated; if provided, used and enriched. All existing modes (manual manifest, external preprocess, build-only) remain valid
- E12.12 — removed (custom sentinels unnecessary — E6.02 migrates to MarkdownTextSplitter which handles tables natively)

### E12.08 implementation items

- E12.13 — shelved (ROI faible pour doc technique structurée: recursive+hybrid+reranking performe aussi bien. Gain +22.5% éprouvé uniquement sur corpus non-structurés denses — Chen et al. 2023 Dense X Retrieval, datasets HotpotQA/NQ. Coût: 1 LLM call/section. Réservé aux corpus haute valeur non-structurés — juridique, médical. Approche si besoin: LLM décompose sections en propositions atomiques, indexées comme chunks enfants via parent_id)
- `Implémenté` E12.14 [P] Metadata enrichment: LLM generates section summaries and keywords. Add `--enrich meta` mode. +9.2-14.8pts RAG per E14.17
- `Implémenté` E12.25 [P] Inference service lifecycle: config commands to start/stop model servers before/after use. Example: `start: "ollama run molmo2"`, `stop: "ollama stop molmo2"`. Free GPU between models. Configured per model in llm registry
- `Implémenté` E12.26 [P] Sequential model processing: organize ALL pipelines (preprocess, build, optimize) to process model-by-model. Load model → process all items needing it → unload → next model. Extends existing Embedder.unload() pattern to VLM, LLM, reranker. Avoid loading multiple models simultaneously on limited VRAM
- E12.24 — removed (scanned documents handled by Tesseract OCR via E12.43. granite-docling-258M VLM path failed (hallucinations FR). PaddleOCR blocked by Python 3.14. The underlying need is met — see audit-prep-full-tesseract-2026-09-22.md)
- `Implémenté` E12.35 [P] Judge prompt robustness + --keep-intermediates
- `Implémenté` E12.36 [P] Enrichment in source language: language detection via langdetect + prompt templates per language (FR, EN, fallback)
- `Implémenté` E12.37 [P] Whole-document enrichment: when no headings found, treat entire document as one section (## Document) for enrichment
- `Implémenté` E12.38 [P] OCR correction: reverted LLM approach (truncation issue), restored regex _fix_ocr_artifacts in clean_text
- `Implémenté` E12.39 [P] Preserve content: reverted LLM prompt approach, enrichment adds alongside without rewriting
- E12.40 — removed (title "w" is author metadata, not a bug. Manifest title field is the override mechanism. Principle: never override user declarations)
- `Implémenté` E12.41 [P] Caption prompt quality: investigate why multi-model prompt (OCR+classify+caption) degrades Molmo quality vs simple caption prompt. Pexels photo identified as "slide" in multi-model vs correct "photo" in single-model: detect repetition loops in VLM output (discard), keep phase2 files for diagnosis, improve judge prompt (anti-repetition, prefer completeness, prefer source language). See docs/studies/grooming-E12.35.md
- `Implémenté` E12.34 [P] CUDA check in subprocess: torch.cuda.is_available() allocates 3 MiB VRAM that cannot be freed. Run CUDA diagnostic check in a short-lived subprocess to avoid polluting main process VRAM before IS start
- `Implémenté` E12.43 [P] Tesseract OCR + langue par source: Tesseract (Level 1-2) replaces RapidOCR (Level 3). lang field in manifest per source. Config fallback ocr_engine/ocr_lang. tesserocr binding. Do NOT install tesseract-osd. See docs/studies/grooming-E12.43.md
- `Implémenté` E12.44 [P] Configurable timeout per model in LLM registry: add `timeout` field to llm registry entries. Used by PictureDescriptionApiOptions and caption_with_docling. Default 180s. Molmo CPU needs 600s for PPTX images
- `Implémenté` E12.45 [P] Standalone photo/infographic fallback: when Docling produces empty output on a standalone image (0 pictures, 0 texts in JSON), fall back to direct VLM captioning via API. Pexels photo produces 0 bytes currently. See audit-prep-full-tesseract-2026-09-22.md
- E12.46 — removed (no change needed: Summary/Keywords labels are LLM formatting instructions, not RAG signals. Content is already in source language via E12.36. Labels are noise for embedding — a few EN tokens in FR text have no measurable impact on retrieval. See grooming-E12.46.md)
- `Implémenté` E12.47 [P] Minimal function signatures: preprocess_sources 3 params, run_build 5 params. All pipeline params resolved from LoreConfig. Tests migrated to LoreConfig fixtures. See grooming-E12.47.md
- `Implémenté` E12.48 [P] Audio ingestion: transcribe_audio() calls STT API (OpenAI-compatible /v1/audio/transcriptions). Markdown with timestamp headings. Config: parse.stt_model references LLM registry. See study-E12.48-audio-ingestion.md
- `Implémenté` E12.49 [P] Video ingestion: parse_video() extracts audio (ffmpeg) + scene change frames → single .md with transcription + base64 inline frames at temporal position. See grooming-E12.49.md
- `Implémenté` E12.52 [P] Video frame captioning: frames extracted by ffmpeg are base64 inline but never captioned by VLM. Detect inline base64 images after STT and caption via caption_standalone_image (E12.45 pattern). Without this, frames are stripped to empty alt text by clean_text
- `Implémenté` E12.50 [P] Format detection via mimetypes: _BACKEND_MAP for explicit backends, mimetypes.guess_type() for audio/video. Covers all formats automatically. See grooming-E12.50.md
- `Implémenté` E12.42 [P] Multi-model via Docling natif: parse once → save_as_json → pour chaque modèle: load + PictureDescriptionApiModel → export. Zéro code VLM custom. Vérifié: images survivent à la sérialisation JSON. See docs/studies/grooming-E12.42.md
- `Implémenté` E12.33 [P] Test infrastructure for subprocess phase 1: test _phase1_worker directly (5 tests: parse, missing, multiple, report structure, orig_dir). See grooming-E12.33.md
- `Implémenté` E12.32 [P] VLM diagnostic traces: VRAM before each VLM call, payload size, image dimensions, response body on error. Visible with --debug only. Requested by IS provider for 507 diagnosis
- `Implémenté` E12.31 [P] Subprocess isolation for phase 1 parse: run Docling parse in a subprocess (fork) so that the CUDA context (~128 MiB) is released when it exits. Phase 2 starts with fully clean VRAM (22 MiB vs 150 MiB). Resolves granite-vision 507 on high-res images at the edge of VRAM capacity
- `Implémenté` E12.30 [P] Full Docling integration: use Docling natively for granite-docling (VlmPipeline in phase 1, not standalone API in phase 2), picture description via PictureDescriptionApiOptions for granite-vision, classification allow/deny. granite-docling is a page converter (DocTags→structured markdown), not a captioner — must be called through Docling only (IBM recommendation)
- `Implémenté` E12.23 [P] OCR artifact correction: Part A — regex fixes (I'→l') in clean.py. Part B — bbox column reorder on Docling object before export_to_markdown() (images only). Plus PPTX generic alt text fix. See docs/studies/grooming-E12.23.md
- `Implémenté` E12.15 [P] Document type detection: classify input as text-native PDF, scanned document, photo, infographic, or data. Route to appropriate parser (Docling text, Docling VLM, VLM captioning). Prerequisite for E12.16 and E12.24
- `Implémenté` E12.16 [P] Image captioning via VLM: LLM vision generates descriptions for photos and infographics. Requires general-purpose VLM (Claude vision, LLaVA, Qwen-VL). Also enriches alt text of images in markdown documents. Depends on E12.15 (detection). Related to E6.03
- E12.17 — moved to E10.29 (end-to-end optimize)
- `Implémenté` E12.18 [P] CLI separation: `lore-mcp enrich` as standalone command (currently only `--enrich` option on preprocess). Same modules, separate entry point. `lore-mcp preprocess --enrich` remains as shortcut
- `Implémenté` E12.19 [P] Analyze integration: dedup + PII reports as implicit analysis during preprocess (not separate action). `lore-mcp lint` already exists as standalone. Wire dedup+PII into lint if not already
- `Implémenté` E12.20 [E] Auto-manifest and full-auto mode: `lore-mcp build --docs-dir /files/ --output-dir /db/` without manifest. Scan directory for supported formats, generate manifest with extracted metadata (title, author, license from front matter or document content), preprocess, index. Manifest is optional — if absent, generated; if provided, used and enriched. All existing modes (manual manifest, external preprocess, build-only) remain valid
- `Implémenté` E12.21 [P] URL list input: accept a simple text file of URLs as input (one URL per line) instead of a full manifest. lore-mcp fetches, generates manifest entries, preprocesses. Simplest possible input format
- `Implémenté` E12.27 [P] Progressive output and VLM resilience: phase-suffixed files on disk (phase1-parse.md, phase2-caption.md, phase3-enrich.md → final .md), phase announcement in stdout+report, VLM per-image try/except + skip <10KB + content-hash dedup + circuit breaker + progressive write per image. See docs/studies/grooming-E12.27.md
- E12.28 — absorbed by E12.42 (Docling native multi-model) + E12.35 (judge) + E12.41 (caption quality). All described functionality implemented
- E12.29 — absorbed into E12.28
- `Implémenté` E12.22 [P] Untreated files report: preprocess must produce a clear report of all files NOT processed (missing, errors, URL fetch failed, format not supported, quality gate failed). Machine-readable output for pipeline integration

### E8. Example corpus — moved to openshift workspace

- E8.01-E8.03 — moved to openshift workspace
  (data selection and indexing, not tooling)

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

### Team Topologies

lore-mcp is a **Platform component** in the
openshift workspace Team Topologies.

Interactions:
- **AI Serving** consumes lore-mcp as
  X-as-a-Service (corpus indexing, MCP config)
- **Veille** (Enabling) feeds the corpus with
  sources (Facilitating)
- **Deep Research** and **Cogliq** consume via
  MCP tools (X-as-a-Service)

Interface contract: MCP tools (`search_docs`,
`list_indexed_sources`), environment variables
(`LORE_*`), transport (stdio or SSE).

Cross-workspace sync: `sync/` directory. See §6.

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
├── LICENSE                # AGPL v3
├── README.md              # Showcase: presentation,
│                          #   quickstart, roadmap
├── pyproject.toml         # Packaging
│
├── docs/                  # Documentation
│   ├── ai-guidelines.md   #   AI-assisted dev rules
│   ├── architecture.md    #   Technical (design)
│   ├── code-guide.md      #   Technical (code)
│   ├── configuration.md   #   Technical (reference)
│   ├── preprocessing.md   #   Technical (source prep)
│   ├── tutorial.md        #   Tutorial (how to run)
│   ├── adr/               #   Studies/reflections
│   │   ├── 001-license-gpl-v3.md
│   │   ├── 002-project-name.md
│   │   ├── 003-license-agpl-migration.md
│   │   └── 004-multi-collection.md
│   └── studies/           #   Studies/reflections
│       └── reference/     #   Lab prototypes
│
├── src/                   # Code
│   └── lore_mcp/
│       ├── __init__.py
│       ├── server.py      # MCP server
│       ├── embedder.py    # GPU/API/CPU embedding
│       ├── store.py       # SQLite + sqlite-vec
│       ├── collections.py # Multi-collection mgmt
│       ├── manifest.py    # Manifest + front matter
│       ├── metadata.py    # Output .json/.bib/.md
│       ├── eval.py        # RAG evaluation + optimize
│       ├── build.py       # Build workflow
│       ├── build_config.py # Unified build config
│       └── ingest.py      # Chunking + indexing
│
├── tests/                 # Code (tests)
│
├── examples/              # Showcase
│   └── mcp-config.example.json
│
└── sync/                  # Cross-workspace sync
    ├── links.md           #   Linked projects table
    └── openshift.md       #   Outgoing sync → openshift
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
- **Bugs**: bugs follow the same lifecycle as
  other items — backlog entry, grooming, TDD,
  branch, merge. No ad hoc fixes outside the
  backlog.
- **Never override user declarations**: lore-mcp
  does not correct or override values declared
  by the user (manifest fields, config). If a
  document title is "w" in its metadata and the
  user does not override it in the manifest,
  lore-mcp uses "w". The manifest is the
  mechanism for the user to declare corrections.
- **Input files are never modified**: all
  commands (preprocess, enrich, build, lint)
  write to output directories, never modify
  files provided as input. The manifest is
  never modified — lore-mcp produces an
  enriched copy (`-prep` suffix).
- **Background commands**: always provide the
  output file path immediately after launching
  any background or long-running command, so
  the user can follow with `tail -f <path>`.
  No exceptions.
- **No implementation without grooming**: every
  backlog item must be groomed and validated by
  the user before implementation starts. No
  exceptions, even for "small" fixes. If a fix
  is identified during implementation of another
  item, create a new backlog item and groom it.
  This includes code changes during debugging —
  do not modify production code to "try something"
  without a groomed item. Diagnostic traces and
  temporary instrumentation follow the same rule.
- **Design documents before refactoring**: before
  any refactoring that changes pipeline behavior,
  write the design document first, have it
  validated, then verify the implementation
  matches. Do not make incremental fixes that
  diverge from the validated design. If the
  design is wrong, update it and get it
  validated — do not patch around it.
  Reference: `docs/studies/design-captioning-
  pipeline.md` for captioning pipeline.
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
- **Backlog pruning**: 2× per iteration, maximize
  work not done (agile P10).

### Item lifecycle

Each backlog item follows this cycle:

Statuses: `À faire` → `Prêt` (grooming done) →
`En cours` → `Implémenté` (DoD met) → `Revue`.

**Development partnership**: an `Implémenté` item
can be consumed before its review — consumption
acts as a benevolent UAT with short feedback loop.

**Transverse DoD** (adds to item-specific DoD):
detailed documentation of design and
implementation — code guide and implementation
guide detailing code and technical artifacts,
block by block (high level → atomic).

1. **Grooming**: before implementation, define
   DoD, successive MVPs, dependencies, design
   approach. Write a persistent artifact in
   `docs/studies/grooming-E<id>.md` with the
   grooming result. **Grooming is interactive
   and one item at a time** — present the
   grooming to the user, discuss, iterate until
   aligned. Do not batch-groom multiple items
   without user interaction on each. **Wait for
   explicit user validation** before starting
   implementation. Do not interpret feedback or
   silence as validation — the user must say
   "go" or equivalent.
2. **Work (successive MVPs)**: priority to the
   next MVP. At each MVP reached, produce the
   corresponding communication increment (sync
   outgoing, README, docs).
3. **Closure**: review ensures the right thing
   done right. Documentation mandatory. If
   changes needed post-review → create a **new
   item** (do not reopen). Item is `[x]` only
   after user validation.

**Transverse rules:**
- **Complementary work**: if identified on an
  item not in `Revue`, create needed items and
  return the item to `À faire`
- **Needed changes**: if identified on an item
  not in `Revue`, continue on the branch and
  update status

### Platform posture

lore-mcp is a Platform component. Design
decisions should prioritize:
- Self-service for consumers (API, tools, docs)
- Developer experience (clear errors, sensible
  defaults, capability assessment)
- Interface stability (backward-compatible
  changes, documented contracts)
