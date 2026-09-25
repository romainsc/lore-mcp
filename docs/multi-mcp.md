# Multi-MCP Setup: lore-mcp + Codebase-Memory

Use two complementary MCP servers to cover both
documentation and source code in a single project.

- **lore-mcp**: semantic search over documents
  (PDF, HTML, DOCX, audio, video). Embedding-based
  retrieval with hybrid BM25+vector search.
- **Codebase-Memory**: structural code intelligence
  (functions, classes, call chains, imports).
  Tree-sitter AST knowledge graph, 158 languages.

Neither replaces the other. An MCP client (Claude
Code, Claude Desktop) can mount both servers and
route queries to the right one.

## Installation

### lore-mcp

```bash
pip install lore-mcp
```

Or via container — see `docs/docker.md`.

### Codebase-Memory

Download the static binary from GitHub releases:

```bash
# https://github.com/DeusData/codebase-memory-mcp/releases
codebase-memory-mcp install
```

Single binary, zero dependencies. MIT license.

## MCP client configuration

### Claude Code

Add both servers to your MCP settings
(`~/.claude/settings.json` or project
`.claude/settings.json`):

```json
{
  "mcpServers": {
    "lore-mcp": {
      "command": "lore-mcp",
      "args": ["serve", "--config", "/path/to/config.yaml"]
    },
    "codebase-memory": {
      "command": "codebase-memory-mcp"
    }
  }
}
```

### Claude Desktop

Same structure in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lore-mcp": {
      "command": "lore-mcp",
      "args": ["serve", "--config", "/path/to/config.yaml"]
    },
    "codebase-memory": {
      "command": "codebase-memory-mcp"
    }
  }
}
```

## When to use which

| Question type | Server | Tool | Example query |
|--------------|--------|------|---------------|
| Documentation content | lore-mcp | `search_docs` | "What does the doc say about reranking?" |
| Configuration reference | lore-mcp | `search_docs` | "How to configure the embedding model?" |
| API documentation | lore-mcp | `search_docs` | "What MCP tools are exposed?" |
| Indexed sources list | lore-mcp | `list_indexed_sources` | "What documents are indexed?" |
| Code structure | Codebase-Memory | `search_graph` | "Where is reranking implemented?" |
| Call chains | Codebase-Memory | `trace_path` | "Who calls `_start_embedders`?" |
| Architecture overview | Codebase-Memory | `get_architecture` | "Show project structure and hotspots" |
| Dependencies | Codebase-Memory | `query_graph` | "What does `store.py` import?" |

**Rule of thumb**: if the answer is in prose
(documentation, guides, specs), use lore-mcp. If
the answer is in code structure (where something
is defined, who calls it, what it depends on),
use Codebase-Memory.

## Workflow

### 1. Index documentation

```bash
lore-mcp build \
  --docs-dir docs/ \
  --output-dir . \
  --config config.yaml
```

This creates a `.db` file with embedded vectors
for semantic search over your documentation.

### 2. Index code

Codebase-Memory auto-indexes on first query.
To index explicitly:

```
# Via MCP tool
index_repository(repo_path="/path/to/repo")
```

This creates a knowledge graph of all functions,
classes, imports, and call relationships.

### 3. Query

The LLM automatically routes to the right server
based on the question. No manual routing needed —
the tool descriptions guide the model.

## Exclude non-code from code graph

Create `.cbmignore` in the repository root to
keep the Codebase-Memory graph focused on code:

```
tests/fixtures/
docs/studies/
sync/
workspace-validation/
```

This excludes test fixtures, research documents,
and other non-code content that adds noise to the
structural graph. Technical docs (`docs/*.md`)
are kept — they provide semantic links between
code and documentation.

## Benchmarks (E10.34)

Measured on the lore-mcp repository itself:

| Corpus type | lore-mcp Recall@5 | Codebase-Memory |
|-------------|-------------------|-----------------|
| Technical docs | 90% | N/A (not designed for docs) |
| Philosophy (Kant) | 100% | N/A |
| Source code | 0% | Structural queries (83% quality, 10x fewer tokens) |

lore-mcp with generalist embeddings cannot
retrieve source code effectively — natural
language documentation always wins in vector
similarity. Codebase-Memory uses AST parsing
instead of embeddings, making it the right tool
for code queries.

## Licenses

| Server | License | Compatibility |
|--------|---------|---------------|
| lore-mcp | AGPL-3.0 | Copyleft, network clause |
| Codebase-Memory | MIT | Permissive |

Both communicate via MCP (stdio), so there is no
code linking — license compatibility is not a
concern.
