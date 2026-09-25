# Why lore-mcp?

## The problem

Documentation exists. It is scattered across PDFs,
HTML pages, DOCX files, slide decks, spreadsheets,
conference recordings, and internal wikis. Finding
the right piece of information means opening the
right tool, remembering the right file, and
scanning through pages of content.

Developers spend 30-60 minutes per day searching
for information they know exists somewhere. This
is worse for new team members, cross-functional
teams, and anyone working with regulatory or
compliance documentation.

Existing solutions either require cloud services
(vendor lock-in, data privacy concerns), demand
coding expertise (LangChain, LlamaIndex), or only
handle one format (Obsidian, grep).

## What lore-mcp does

lore-mcp turns a folder of documents into a
searchable knowledge base that any AI assistant
can query. One command, one `.db` file, no server.

```bash
lore-mcp build --docs-dir /path/to/docs/ --output-dir .
```

The AI assistant (Claude Code, Claude Desktop, or
any MCP client) queries your documentation with
natural language:

> "What are the GPU requirements for TEI?"
> "How does the reranking configuration work?"
> "What did the OECD say about AI definition?"

## What makes it different

### Local-first

No data leaves your machine. The `.db` file lives
on your disk. No cloud API, no external database,
no network dependency. Works in air-gapped
environments, meets compliance requirements
(GDPR, HIPAA, classified), and runs on a laptop.

### Multi-format, single pipeline

PDF, HTML, DOCX, PPTX, XLSX, EPUB, images (OCR),
CSV, JSON, XML, markdown, audio, and video — all
processed by one pipeline. No format-specific
tooling. Add a conference recording and it
transcribes, extracts frames, and indexes
alongside your PDFs.

### MCP native

lore-mcp exposes three MCP tools (`search_docs`,
`list_indexed_sources`, `list_collections`). Any
MCP client — Claude Code, Claude Desktop, Cursor,
or custom — can use them. The AI chooses which
tool to call based on the query. No prompt
engineering, no retrieval code to write.

### Libre stack

AGPL-3.0 code. All dependencies have free/libre
licenses (MIT, Apache 2.0). The default embedding
model (nomic-embed-text-v2-moe) is Apache 2.0
with Level 2 libre weights. No proprietary models
required. No license audit surprises.

### Portable

The entire index is a single SQLite `.db` file.
Copy it to another machine, share it with a
colleague, distribute it with your project. No
database server, no migrations, no infrastructure.

### Complementary to code intelligence

lore-mcp handles documents. For source code,
pair it with [Codebase-Memory](https://github.com/DeusData/codebase-memory-mcp)
(MIT, 158 languages). Both are MCP servers — mount
them together and the AI routes queries to the
right one. See [multi-mcp.md](multi-mcp.md).

## Use cases

### 1. Platform engineer onboarding

*New team member joining a platform team.*
They index the team's internal docs (architecture
decisions, runbooks, onboarding guides, API specs)
with one command. From their IDE, they query
"how do we deploy to staging?" and get the answer
with source attribution. Ramp-up time drops from
weeks to days.

### 2. Compliance and regulatory search

*Compliance officer preparing for an audit.*
They index regulatory documents (AI Act, GDPR,
OECD AI principles, internal policies) into a
single `.db`. During the audit, they query
"what are the transparency requirements for
high-risk AI systems?" and get the exact clause
with source reference. No cloud — sensitive
regulatory interpretations stay local.

### 3. Open source project documentation

*Maintainer of an open source project.*
They index the project's docs, RFCs, mailing list
archives, and ADRs. Contributors query "has this
been discussed before?" or "what's the rationale
for this design decision?" instead of searching
through years of GitHub issues.

### 4. Academic research

*Researcher working across multiple papers.*
They index a corpus of papers, books, and datasets
documentation. They query across the entire corpus:
"which papers discuss reproducibility in the
context of copyleft?" and find cross-references
that manual reading would miss.

### 5. SRE incident response

*On-call engineer during a production incident.*
Runbooks, past incident reports, and architecture
docs are indexed. During the incident, they query
"what's the procedure for database failover on
cluster-3?" and get the exact steps — no time
spent navigating Confluence.

### 6. Technical writing and documentation audit

*Technical writer maintaining product docs.*
They index all existing docs, then query "what
does the documentation say about authentication?"
to find gaps, inconsistencies, or outdated
sections across multiple documents.

### 7. Training and education

*Instructor or course designer.*
They index course material — slides (PPTX),
lecture recordings (video/audio), reading lists
(PDF). Students query the indexed material from
Claude Desktop: "explain the difference between
supervised and unsupervised learning, based on
the lecture." The AI cites the specific lecture
and slide.

### 8. Legal document search

*Legal team reviewing contracts.*
They index contracts, terms of service, and
company policies. They query "which contracts
have a non-compete clause longer than 12 months?"
and get the relevant clauses with document
attribution. No cloud — contract content stays
on their machine.

### 9. Air-gapped environments

*Defense, government, or healthcare IT.*
Cloud RAG is forbidden. lore-mcp runs entirely
offline with local embedding (CPU or GPU). The
`.db` file is the only artifact. No network
calls, no telemetry, no external dependencies
at runtime. Embed once, query forever.

### 10. Personal knowledge base

*Developer who reads widely.*
They index everything they read — blog posts,
papers, books, conference talks. From any MCP
client, they query their accumulated knowledge:
"what was that article about AST-based code
chunking?" and the specific source comes back.

## Comparison

| Feature | lore-mcp | Notion AI / Confluence AI | LangChain / LlamaIndex | Obsidian plugins |
|---------|----------|--------------------------|----------------------|-----------------|
| **Runs locally** | Yes (offline) | No (cloud only) | Yes (requires coding) | Yes |
| **Multi-format** | PDF, HTML, DOCX, PPTX, audio, video, images | Platform-native only | Any (you build it) | Markdown only |
| **MCP native** | Yes (3 tools) | No | No (framework) | No |
| **Setup effort** | One command | SaaS subscription | Write Python code | Install plugins |
| **Data privacy** | Local only | Cloud (vendor access) | Depends on setup | Local only |
| **License** | AGPL-3.0 (libre) | Proprietary | MIT/Apache | Various |
| **Code intelligence** | Via Codebase-Memory | Limited | Build it yourself | Via plugins |
| **Portable index** | Single .db file | Vendor-locked | Depends on backend | Local vault |

### vs Codebase-Memory

Not a competitor — a complement. lore-mcp indexes
**documents** (prose, PDFs, recordings).
Codebase-Memory indexes **code** (AST, call
graphs, dependencies). Mount both as MCP servers
and the AI uses the right one for each query.
See [multi-mcp.md](multi-mcp.md).
