# ADR-002: Project name — lore-mcp

- **Status:** Accepted
- **Date:** 2026-07-29
- **Decision:** Name the project **lore-mcp**, where LORE stands for **Local Offline Retrieval Engine**

## Context

The project was initially conceived under the working title `mcp-rag-local`. While descriptive, this name is generic (many MCP RAG projects exist), not memorable, and reads as a technical label rather than a project identity. A better name should be:

1. **Memorable and distinctive** — stands out in the MCP ecosystem
2. **Technically meaningful** — conveys what the tool does
3. **Short and typeable** — works as a CLI command, PyPI package, and GitHub repo name
4. **Pronounceable** — in both English and French

## Creative exploration

### Phase 1: Symbolic and mythological names

Five candidates were generated, each with a different naming strategy:

| Name | Strategy | Meaning |
|---|---|---|
| **CAIRN** | Symbolic | A cairn is a stack of stones used as a landmark for travelers — fragments of knowledge stacked to guide exploration |
| **RUNE** | Acronym + symbolic | Retrieval Using Neural Embeddings; runes are ancient symbols of knowledge carved in stone |
| **MNEMOS** | Mythological | From Mnemosyne, the Greek goddess of memory, mother of the Muses — direct link to retrieval and memory |
| **ARCA** | Recursive acronym | ARCA Retrieves Chunks Autonomously; "arca" means chest or ark in Latin — a container of knowledge |
| **LORE** | Symbolic | Accumulated knowledge, oral tradition, transmitted wisdom — semantically perfect for a RAG system |

### Phase 2: LORE as the base

LORE emerged as the strongest candidate: short (4 letters), evocative, and naturally expandable into a technically descriptive acronym:

**LORE = Local Offline Retrieval Engine**

Every word carries meaning:
- **Local** — runs on the workstation, no cloud dependency
- **Offline** — no mandatory network connection
- **Retrieval** — semantic search over documents
- **Engine** — it's a tool, not a service

### Phase 3: Making it technically explicit

LORE alone doesn't indicate the MCP connection. Variants explored:

| Form | Analysis |
|---|---|
| **lore-mcp** | LORE identity + MCP suffix. Follows ecosystem convention. Clear: "this is LORE, an MCP server." PyPI: `lore-mcp`, import: `lore_mcp` |
| **mcp-lore** | MCP prefix convention (`mcp-server-*`). But puts the protocol before the identity — the project becomes "just another mcp-something" |
| **LORME** | Word blend of LORE + MCP. Could expand to "Local Offline Retrieval for MCP Environments." Elegant fusion, but less immediately readable than the hyphenated form |
| **mcplore** | Portmanteau of MCP + explore + lore. Clever wordplay but hard to pronounce and parse |
| **lorevec** | LORE + vec (nod to sqlite-vec). Highlights vector search but loses the MCP connection |
| **lore-rag** | LORE + RAG. Explicit about function but RAG is an implementation detail, not the user-facing purpose |

## Decision

**lore-mcp** — the hyphenated form `{identity}-{protocol}`.

Rationale:
1. **Identity first:** "lore" is the name people remember; "-mcp" is the technical qualifier
2. **Ecosystem convention:** follows the `{name}-mcp` pattern used by community MCP servers
3. **Technically unambiguous:** the suffix immediately signals this is an MCP server
4. **PyPI-friendly:** `lore-mcp` is a valid, available-style package name; Python import becomes `lore_mcp`
5. **CLI-friendly:** `lore-mcp` works as a command name
6. **LORME was a close second:** elegant fusion, but `lore-mcp` wins on immediate readability for someone discovering the project on GitHub or PyPI

## Consequences

- GitHub repository: `lore-mcp`
- PyPI package: `lore-mcp`
- Python package: `lore_mcp` (under `src/lore_mcp/`)
- CLI entry point: `lore-mcp`
- Environment variable prefix: `LORE_`
- The acronym LORE (Local Offline Retrieval Engine) should appear in the README and project description
