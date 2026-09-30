#!/usr/bin/env python3
"""E12.96: MCP SDK validation — programmatic tool calls.

Tests all MCP tools directly via Python imports (no MCP transport).
Requires a built .db (run validate_cli.py first or point to an existing build).

Usage:
    python tests/validation/validate_mcp_sdk.py [db_path]

Prerequisites:
    - Built .db file
    - TEI running for search_docs
    - pip install -e .
"""

import sys
from pathlib import Path

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "workspace-validation/build/test-redist.db"
errors = []


def check(name, condition, msg=""):
    if condition:
        print(f"  ✓ {name}")
    else:
        errors.append(f"{name}: {msg}")
        print(f"  ✗ {name}: {msg}")


def main():
    print("=== E12.96: MCP SDK Validation ===\n")

    # Patch config to use the right .db
    import os
    os.environ.setdefault("LORE_DB_PATH", DB_PATH)

    # 1. list_indexed_sources
    print("[1/6] list_indexed_sources")
    from lore_mcp.server import list_indexed_sources
    result = list_indexed_sources()
    check("returns string", isinstance(result, str))
    check("has files", "file(s)" in result)

    # 2. get_service_status
    print("[2/6] get_service_status")
    from lore_mcp.server import get_service_status
    result = get_service_status()
    check("returns string", isinstance(result, str))
    check("mentions embedder", "Embedder" in result or "embedder" in result.lower())

    # 3. lint_source
    print("[3/6] lint_source")
    from lore_mcp.server import lint_source
    result = lint_source("tests/fixtures/orig/test-markdown-sample.md")
    check("returns string", isinstance(result, str))
    check("has verdict", "verdict" in result.lower() or "density" in result.lower())

    # 4. list_pipeline_state
    print("[4/6] list_pipeline_state")
    from lore_mcp.server import list_pipeline_state
    result = list_pipeline_state()
    check("returns string", isinstance(result, str))

    # 5. list_tasks
    print("[5/6] list_tasks")
    from lore_mcp.server import list_tasks
    result = list_tasks()
    check("returns string", isinstance(result, str))

    # 6. search_docs (requires TEI running)
    print("[6/6] search_docs")
    try:
        from lore_mcp.server import search_docs
        result = search_docs("open source AI definition")
        check("returns string", isinstance(result, str))
        check("has results", "result(s)" in result)
        check("relevant content", "Open Source" in result or "open source" in result.lower(),
              f"Expected 'Open Source' in result, got: {result[:100]}")
    except Exception as e:
        check("search_docs callable", False, str(e))

    # Report
    print(f"\n{'='*40}")
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("MCP SDK validation PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
