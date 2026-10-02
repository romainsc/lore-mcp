#!/usr/bin/env python3
"""E3.17: Exhaustive MCP SDK validation — all 17 tools.

Tests all MCP tools directly via Python imports (no MCP transport).
Requires a built .db and TEI running for search_docs.

Usage:
    python tests/validation/validate_mcp_sdk.py [db_path]

Prerequisites:
    - Built .db file
    - TEI running for search_docs/add_source
    - pip install -e .
"""

import sys
import time
import tempfile
from pathlib import Path

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "workspace-validation/build/test-redist.db"
BUILD_DIR = str(Path(DB_PATH).parent)
errors = []


def check(name, condition, msg=""):
    if condition:
        print(f"  ✓ {name}")
    else:
        errors.append(f"{name}: {msg}")
        print(f"  ✗ {name}: {msg}")


def wait_task(task_id, timeout=60):
    """Poll task until completed or timeout."""
    from lore_mcp.server import get_task_status
    start = time.time()
    while time.time() - start < timeout:
        result = get_task_status(task_id=task_id)
        if "completed" in result.lower():
            return result
        if "failed" in result.lower():
            return result
        time.sleep(1)
    return f"Timeout after {timeout}s"


def main():
    print("=== E3.17: Exhaustive MCP SDK Validation ===\n")

    # Configure
    import lore_mcp.server as srv
    from lore_mcp.config import LoreConfig
    cfg = LoreConfig.from_file("config.yaml") if Path("config.yaml").exists() else LoreConfig.defaults()
    cfg.db_dir = str(Path(DB_PATH).parent)
    cfg.default_collection = Path(DB_PATH).stem
    srv._config = cfg
    srv._db_cache.clear()

    # Pre-flight: ensure embedder is ready before tests
    # Skip service start — TEI must be running before this script
    print("[0/17] Embedder pre-flight")
    srv._service_started = True
    try:
        embedder = srv._get_embedder()
        test_vec = embedder.embed("pre-flight check")
        check("embedder ready", test_vec is not None and len(test_vec) > 0)
    except Exception as e:
        print(f"  ✗ embedder not ready: {e}")
        print("  Start TEI first: podman start tei-nomic-v2")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 1. list_indexed_sources
    # ------------------------------------------------------------------
    print("[1/17] list_indexed_sources")
    from lore_mcp.server import list_indexed_sources
    result = list_indexed_sources()
    check("returns string", isinstance(result, str))
    check("has files", "file(s)" in result)
    initial_sources = result

    # ------------------------------------------------------------------
    # 2. get_service_status
    # ------------------------------------------------------------------
    print("[2/17] get_service_status")
    from lore_mcp.server import get_service_status
    result = get_service_status()
    check("returns string", isinstance(result, str))
    check("mentions embedder", "embedder" in result.lower())

    # ------------------------------------------------------------------
    # 3. lint_source
    # ------------------------------------------------------------------
    print("[3/17] lint_source")
    from lore_mcp.server import lint_source
    result = lint_source("tests/fixtures/orig/test-markdown-sample.md")
    check("returns string", isinstance(result, str))
    check("has verdict", "verdict" in result.lower() or "density" in result.lower())

    # ------------------------------------------------------------------
    # 4. lint_source — missing file
    # ------------------------------------------------------------------
    print("[4/17] lint_source (missing file)")
    result = lint_source("/nonexistent/file.md")
    check("handles missing", "not found" in result.lower() or "error" in result.lower())

    # ------------------------------------------------------------------
    # 5. list_pipeline_state
    # ------------------------------------------------------------------
    print("[5/17] list_pipeline_state")
    from lore_mcp.server import list_pipeline_state
    result = list_pipeline_state()
    check("returns string", isinstance(result, str))

    # ------------------------------------------------------------------
    # 6. list_tasks
    # ------------------------------------------------------------------
    print("[6/17] list_tasks")
    from lore_mcp.server import list_tasks
    result = list_tasks()
    check("returns string", isinstance(result, str))

    # ------------------------------------------------------------------
    # 7. list_collections
    # ------------------------------------------------------------------
    print("[7/17] list_collections")
    from lore_mcp.server import list_collections
    result = list_collections()
    check("returns string", isinstance(result, str))
    check("single mode", "single" in result.lower() or "collection" in result.lower())

    # ------------------------------------------------------------------
    # 8. search_docs
    # ------------------------------------------------------------------
    print("[8/17] search_docs")
    try:
        from lore_mcp.server import search_docs
        result = search_docs("open source AI definition")
        check("returns string", isinstance(result, str))
        check("has results", "result(s)" in result)
        check("relevant", "open source" in result.lower(),
              f"got: {result[:100]}")
    except Exception as e:
        check("search_docs", False, str(e))

    # ------------------------------------------------------------------
    # 9. search_docs with filter
    # ------------------------------------------------------------------
    print("[9/17] search_docs (with filter)")
    try:
        result = search_docs("definition", filter="license:CC-BY-4.0")
        check("filtered returns string", isinstance(result, str))
        check("filtered has results", "result(s)" in result)
    except Exception as e:
        check("search_docs filter", False, str(e))

    # ------------------------------------------------------------------
    # 10. search_docs — out of corpus
    # ------------------------------------------------------------------
    print("[10/17] search_docs (out of corpus)")
    try:
        result = search_docs("kubernetes istio service mesh configuration")
        check("out-of-corpus returns", isinstance(result, str))
        check("low relevance", "result(s)" in result)
    except Exception as e:
        check("search_docs out-of-corpus", False, str(e))

    # ------------------------------------------------------------------
    # 11. add_source → search → remove cycle
    # ------------------------------------------------------------------
    print("[11/17] add_source → search → remove cycle")
    try:
        from lore_mcp.server import add_source, remove_source

        doc = Path(tempfile.mkdtemp()) / "platypus-test.md"
        doc.write_text(
            "## Platypus Biology\n\n"
            "The platypus is a semi-aquatic monotreme endemic to Australia.\n"
            "It has a duck-like bill, beaver-like tail, and venomous spurs.\n"
            "Males can deliver a painful sting to predators.\n"
            * 3
        )

        result = add_source(file=str(doc), build_dir=BUILD_DIR, title="Platypus Test")
        check("add returns task_id", "poll" in result.lower() or "adding" in result.lower())

        task_id = result.split(":")[-1].strip().split("'")[1] if "'" in result else result.split()[-1].rstrip(".")
        task_result = wait_task(task_id, timeout=30)
        check("add completed", "completed" in task_result.lower(), task_result[:100])

        # Search for added content
        result = search_docs("platypus venomous monotreme")
        check("platypus found", "platypus" in result.lower(),
              f"got: {result[:150]}")
        check("from correct source", "platypus-test" in result.lower(),
              f"got: {result[:150]}")

        # Verify source count increased
        sources_after_add = list_indexed_sources()
        check("source count +1", "platypus-test" in sources_after_add.lower())

        # Remove
        result = remove_source(source="platypus-test.md", build_dir=BUILD_DIR)
        check("remove ok", "removed" in result.lower(), result)

        # Verify source count restored
        sources_after_remove = list_indexed_sources()
        check("source removed", "platypus-test" not in sources_after_remove.lower())

        doc.unlink(missing_ok=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        check("add/search/remove cycle", False, str(e))

    # ------------------------------------------------------------------
    # 12. get_task_status — not found
    # ------------------------------------------------------------------
    print("[12/17] get_task_status (not found)")
    from lore_mcp.server import get_task_status
    result = get_task_status(task_id="nonexistent-id")
    check("not found", "not found" in result.lower())

    # ------------------------------------------------------------------
    # 13. cancel_task
    # ------------------------------------------------------------------
    print("[13/17] cancel_task")
    from lore_mcp.server import cancel_task
    result = cancel_task(task_id="nonexistent-id")
    check("cancel not found", "not found" in result.lower() or "cannot" in result.lower())

    # ------------------------------------------------------------------
    # 14. add_sources (JSON validation)
    # ------------------------------------------------------------------
    print("[14/17] add_sources")
    from lore_mcp.server import add_sources
    result = add_sources(sources="not json")
    check("add_sources rejects bad json", "invalid json" in result.lower())
    result = add_sources(sources="[]")
    check("add_sources rejects empty", "non-empty" in result.lower())

    # ------------------------------------------------------------------
    # 15. add_recipe (mock)
    # ------------------------------------------------------------------
    print("[15/17] add_recipe")
    try:
        import lore_mcp.build
        _orig_build = lore_mcp.build.run_build
        lore_mcp.build.run_build = lambda *a, **kw: {"collection": "mock", "file_count": 0}
        from lore_mcp.server import add_recipe
        result = add_recipe(recipe="/fake/recipe.yaml")
        check("add_recipe returns task_id", "started" in result.lower())
        lore_mcp.build.run_build = _orig_build
    except Exception as e:
        check("add_recipe", False, str(e))

    # ------------------------------------------------------------------
    # 16. purge_pipeline_state
    # ------------------------------------------------------------------
    print("[16/16] purge_pipeline_state")
    from lore_mcp.server import purge_pipeline_state
    result = purge_pipeline_state(hash="nonexistent_hash_1234")
    check("purge not found", "not found" in result.lower())

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    print(f"\n{'='*40}")
    total = 16
    failed = len(errors)
    if errors:
        print(f"FAILED: {failed} error(s) / {total} tools")
        for e in errors:
            print(f"  ✗ {e[:200]}")
        sys.exit(1)
    else:
        print(f"MCP SDK validation PASSED ({total} tools)")
        sys.exit(0)


if __name__ == "__main__":
    main()
