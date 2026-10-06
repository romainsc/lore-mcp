# Grooming E3.43 — Preprocess-only MCP tools

## Problem

E3.18 removed `start_preprocess` MCP tool
(unified add pipeline). Users who want the
preprocessed markdown without indexation have
no MCP option — only the CLI `lore-mcp preprocess`.

Use cases:
- STT of a video → get the transcription markdown
- Parse a PDF → get the structured markdown
- Enrich a document → get context/QA/meta without indexing

## Design

3 symmetric tools matching the add_* family:

```python
@mcp.tool()
def preprocess_source(
    file: str,
    collection: str = "",
    enrich: str = "",
    force: bool = False,
) -> str:
    """Preprocess a single file without indexing.

    Full pipeline: parse, clean, caption (VLM),
    enrich (LLM), judge selection.
    Returns path to the preprocessed markdown.

    file: path to source file
    collection: working directory (default)

    Advanced:
    enrich: techniques (comma-separated, "none")
    force: ignore checkpoint, re-run all phases
    """

@mcp.tool()
def preprocess_sources(
    sources: str,
    collection: str = "",
    orig_dir: str = "",
    enrich: str = "",
    force: bool = False,
) -> str:
    """Preprocess multiple files (JSON array).
    Returns task ID — poll with get_task_status().
    """

@mcp.tool()
def preprocess_directory(
    directory: str,
    collection: str = "",
    enrich: str = "",
    force: bool = False,
    include_pattern: str = "*",
    include_hidden: bool = False,
) -> str:
    """Preprocess all supported files in a directory.
    Returns task ID.
    """
```

## Architecture

Same pipeline as add_* but stop after phase 3:
- Phase 1: parse (Docling, trafilatura, code narration)
- Phase 1.5: STT (if audio/video)
- Phase 1.7: inline frame captioning
- Phase 2: VLM captioning + judge
- Phase 3: clean + enrich (LLM)
- ~~Phase 4: ingest~~ (skipped)

All config-driven features active:
captioning, judge, enrich, STT, OCR, params.

## Implementation

Extract preprocess logic from `_do_add` into
a shared helper. Both `add_source._do_add` and
`preprocess_source._do_preprocess` call it.
`_do_add` continues to phase 4, `_do_preprocess`
returns the prep path.

`preprocess_directory` calls `preprocess_sources`
(same pattern as add_directory → add_sources).

## Interaction with E12.126

prep/ is the deliverable for preprocess_* tools.
E12.126 does NOT clean prep/ for preprocess_*.

## DoD

- 3 MCP tools: preprocess_source, preprocess_sources,
  preprocess_directory
- Background tasks via TaskManager
- Full pipeline (parse, caption, judge, enrich)
- Return prep/ path or .md file path
- prep/ preserved (deliverable)
- 22 MCP tools total (19 + 3)
- Tests
- CI green

## Effort

Petit-moyen — extract shared preprocess logic
+ 3 thin tool wrappers.
