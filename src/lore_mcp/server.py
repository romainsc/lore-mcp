"""MCP server exposing search_docs and list_sources. See docs/architecture.md."""

import logging
import os
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from lore_mcp.collections import (
    discover_collections,
    search_across,
    search_collection,
)
from lore_mcp.embedder import Embedder
from lore_mcp.store import list_sources as store_list_sources
from lore_mcp.store import open_db, search, validate_model

logger = logging.getLogger(__name__)

mcp = FastMCP("lore-mcp")

_embedder = None
_single_db = None
_init_lock = threading.Lock()


def _get_db_dir() -> str | None:
    """Return LORE_DB_DIR if set, else None."""
    return os.environ.get("LORE_DB_DIR")


def _get_db_path() -> str:
    """Return LORE_DB_PATH for single-collection mode."""
    return os.environ.get("LORE_DB_PATH", "./lore.db")


def _is_multi_collection() -> bool:
    """True if LORE_DB_DIR is set (multi-collection mode)."""
    return _get_db_dir() is not None


def _get_single_db():
    """Lazy-load and cache the single-collection database connection."""
    global _single_db
    with _init_lock:
        if _single_db is None:
            _single_db = open_db(_get_db_path())
    return _single_db


def _get_embedder():
    """Lazy-load the embedder on first query."""
    global _embedder
    with _init_lock:
        if _embedder is None:
            _embedder = Embedder(
                model_name=os.environ.get("LORE_MODEL", "BAAI/bge-m3"),
                mode=os.environ.get("LORE_EMBED_MODE", "auto"),
                api_url=os.environ.get("LORE_API_URL"),
                api_model=os.environ.get("LORE_API_MODEL"),
            )
    return _embedder


def format_search_results(results: list[dict], backend: str) -> str:
    """Format search results for MCP tool output."""
    if not results:
        return "0 results."
    parts = []
    for r in results:
        collection = r.get("collection", "")
        prefix = f"[{collection}:{r['source_file']}]" if collection else f"[{r['source_file']}]"
        parts.append(f"{prefix} (score: {r['score']:.4f})\n{r['content']}")
    header = f"{len(results)} result(s) (embedding: {backend})"
    return header + "\n\n---\n\n".join([""] + parts)


def format_sources(sources: list[dict]) -> str:
    """Format source listing for MCP tool output."""
    if not sources:
        return "0 chunks, 0 files."
    total = sum(s["count"] for s in sources)
    lines = [f"{total} chunks, {len(sources)} file(s)\n"]
    for s in sources:
        lines.append(f"  {s['source_file']}: {s['count']}")
    return "\n".join(lines)


def format_collections(collections: list[dict]) -> str:
    """Format collection listing for MCP tool output."""
    if not collections:
        return "No collections found."
    total_chunks = sum(c["chunk_count"] for c in collections)
    total_files = sum(c["file_count"] for c in collections)
    lines = [f"{len(collections)} collection(s), {total_chunks} chunks, {total_files} files\n"]
    for c in collections:
        level = f" [{c['level']}]" if c["level"] else ""
        lines.append(f"  {c['name']}{level}: {c['chunk_count']} chunks, {c['file_count']} files")
    return "\n".join(lines)


@mcp.tool()
def search_docs(query: str, top_k: int = 5, collection: str = "") -> str:
    """Semantic search over indexed documents.

    Returns the most relevant passages for the given query,
    with similarity scores and source files. In multi-collection
    mode, specify a collection name or leave empty to search
    across all collections.
    """
    embedder = _get_embedder()
    query_embedding = embedder.embed(query)
    backend = embedder.mode if embedder.mode != "auto" else "auto"

    if _is_multi_collection():
        db_dir = _get_db_dir()
        if collection:
            results = search_collection(db_dir, collection, query_embedding, top_k=top_k)
        else:
            results = search_across(db_dir, query_embedding, top_k=top_k)
    else:
        db = _get_single_db()
        validate_model(db, embedder.model_name, embedder.model_dim)
        results = search(db, query_embedding, top_k=top_k)

    return format_search_results(results, backend)


@mcp.tool()
def list_indexed_sources(collection: str = "") -> str:
    """List all indexed files with chunk counts.

    In multi-collection mode, specify a collection name or
    leave empty to list sources across all collections.
    """
    if _is_multi_collection():
        db_dir = _get_db_dir()
        if collection:
            from lore_mcp.collections import collection_db_path
            db = open_db(collection_db_path(db_dir, collection))
            try:
                sources = store_list_sources(db)
            finally:
                db.close()
            return format_sources(sources)
        else:
            all_sources = []
            for f in Path(db_dir).glob("*.db"):
                db = open_db(str(f))
                try:
                    sources = store_list_sources(db)
                    for s in sources:
                        s["source_file"] = f"{f.stem}/{s['source_file']}"
                    all_sources.extend(sources)
                finally:
                    db.close()
            return format_sources(all_sources)
    else:
        db = _get_single_db()
        sources = store_list_sources(db)
        return format_sources(sources)


@mcp.tool()
def list_collections() -> str:
    """List available collections with chunk and file counts.

    Only available in multi-collection mode (LORE_DB_DIR set).
    """
    if not _is_multi_collection():
        return "Single-collection mode (LORE_DB_PATH). Set LORE_DB_DIR for multi-collection."
    collections = discover_collections(_get_db_dir())
    return format_collections(collections)


def main():
    """Entry point for the lore-mcp CLI command.

    Usage:
        lore-mcp                    # stdio (default, for MCP client subprocess)
        lore-mcp --transport sse    # HTTP/SSE (for manual/service launch)
    """
    import argparse

    parser = argparse.ArgumentParser(description="LORE — Local Offline Retrieval Engine for MCP")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)
