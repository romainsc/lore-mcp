# Grooming E3.33: Version command

## Context

No way to verify which version/commit of lore-mcp
is running, neither CLI nor MCP. Version duplicated
in pyproject.toml and __init__.py.

## Design

### Single source of truth: setuptools-scm

Version derived from git tags. No manual file editing.

- Release: `git tag v0.1.0` → `0.1.0`
- Dev: commits after tag → `0.1.1.dev2+gabc123`
- Dirty: uncommitted changes → `0.1.1.dev2+gabc123.dirty`

### CLI

```
$ lore-mcp version
0.1.0.dev1+g55c7194

$ lore-mcp version --deps
lore-mcp 0.1.0.dev1+g55c7194
Python 3.14.7
sqlite-vec 0.1.6
puremagic 2.2.0
sentence-transformers 3.4.1
docling 2.100.0 (optional)
trafilatura: not installed
markitdown: not installed
```

### MCP

```python
def get_version(deps: bool = False) -> str:
    """Return lore-mcp version.

    deps: include dependency versions
    """
```

### Implementation

1. Add setuptools-scm to pyproject.toml
2. Remove hardcoded version from pyproject.toml
   and __init__.py
3. __init__.__version__ reads from metadata
4. Add `version` subcommand to CLI
5. Add `get_version` MCP tool

## DoD

- setuptools-scm configured in pyproject.toml
- Single version source (git tags)
- lore-mcp version CLI
- lore-mcp version --deps CLI
- get_version(deps) MCP tool
- __version__ derived, not duplicated
- Test: version string matches git describe
