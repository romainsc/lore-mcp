"""MCP server exposing search_docs and list_sources. See docs/architecture.md."""

import logging
import os

from mcp.server.fastmcp import FastMCP

from lore_mcp.embedder import Embedder
from lore_mcp.store import list_sources as store_list_sources
from lore_mcp.store import open_db, search, validate_model

logger = logging.getLogger(__name__)

mcp = FastMCP("lore-mcp")

_db = None
_embedder = None


def _get_db():
    """Lazy-load the database on first query."""
    global _db
    if _db is None:
        db_path = os.environ.get("LORE_DB_PATH", "./lore.db")
        _db = open_db(db_path)
    return _db


def _get_embedder():
    """Lazy-load the embedder on first query."""
    global _embedder
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
        parts.append(f"[{r['source_file']}] (score: {r['score']:.4f})\n{r['content']}")
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


@mcp.tool()
def search_docs(query: str, top_k: int = 5) -> str:
    """Semantic search over indexed documents.

    Returns the most relevant passages for the given query,
    with similarity scores and source files.
    """
    db = _get_db()
    embedder = _get_embedder()
    validate_model(db, embedder.model_name, embedder.model_dim)
    query_embedding = embedder.embed(query)
    results = search(db, query_embedding, top_k=top_k)
    backend = embedder.mode if embedder.mode != "auto" else "auto"
    return format_search_results(results, backend)


@mcp.tool()
def list_indexed_sources() -> str:
    """List all indexed files with chunk counts."""
    db = _get_db()
    sources = store_list_sources(db)
    return format_sources(sources)


def main():
    """Entry point for the lore-mcp CLI command."""
    mcp.run()
