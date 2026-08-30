"""MCP server exposing search_docs and list_sources. See docs/architecture.md."""

import logging
import os
import threading
from pathlib import Path

from mcp.server import MCPServer

from lore_mcp.collections import (
    discover_collections,
    search_across,
    search_collection,
)
from lore_mcp.embedder import Embedder
from lore_mcp.store import list_sources as store_list_sources
from lore_mcp.store import open_db, search, validate_model

logger = logging.getLogger(__name__)

mcp = MCPServer("lore-mcp")

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
        biblio_parts = []
        if r.get("title"):
            biblio_parts.append(f"Title: {r['title']}")
        if r.get("author"):
            biblio_parts.append(f"Author: {r['author']}")
        if r.get("license"):
            biblio_parts.append(f"License: {r['license']}")
        biblio = " | ".join(biblio_parts)
        header = f"{prefix} (score: {r['score']:.4f})"
        if biblio:
            header += f"\n  {biblio}"
        parts.append(f"{header}\n{r['content']}")
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
        chunk_info = ""
        if c.get("chunk_size"):
            chunk_info = f" (chunk: {c['chunk_size']}/{c.get('chunk_overlap', '?')})"
        lines.append(f"  {c['name']}{level}: {c['chunk_count']} chunks, {c['file_count']} files{chunk_info}")
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
    """Entry point for the lore-mcp CLI command."""
    import argparse

    parser = argparse.ArgumentParser(description="LORE — Local Offline Retrieval Engine for MCP")
    sub = parser.add_subparsers(dest="command")

    # Default: serve
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )

    # eval subcommand
    eval_parser = sub.add_parser("eval", help="Evaluate RAG retrieval quality")
    eval_parser.add_argument("--db", default=os.environ.get("LORE_DB_PATH", "./lore.db"),
                             help="Path to .db file")
    eval_parser.add_argument("--num-questions", type=int, default=50)
    eval_parser.add_argument("--top-k", type=int, default=5)
    eval_parser.add_argument("--output", default=None, help="Output report JSON path")

    # optimize subcommand
    optimize_parser = sub.add_parser("optimize", help="Optimize chunking parameters")
    optimize_parser.add_argument("--source-dir", required=True, help="Source documents directory")
    optimize_parser.add_argument("--db-dir", default="./optimize-dbs", help="Working directory for temp DBs")
    optimize_parser.add_argument("--num-questions", type=int, default=30)
    optimize_parser.add_argument("--output", default=None, help="Output report JSON path")

    args = parser.parse_args()

    if args.command == "eval":
        _run_eval(args)
    elif args.command == "optimize":
        _run_optimize(args)
    else:
        mcp.run(transport=args.transport)


def _run_eval(args):
    """Run RAG evaluation."""
    from lore_mcp.eval import EvalConfig, run_eval

    embedder = _get_embedder()
    config = EvalConfig.from_env()
    config.num_questions = args.num_questions
    config.top_k = args.top_k

    output = args.output or f"eval-report-{Path(args.db).stem}.json"
    results = run_eval(args.db, embedder, config, output_path=output)

    print(f"Evaluation complete: {results['num_questions']} questions, top_k={results['top_k']}")
    for metric, score in results["scores"].items():
        print(f"  {metric}: {score:.4f}")
    print(f"Report: {output}")


def _run_optimize(args):
    """Run chunking parameter optimization."""
    from lore_mcp.eval import EvalConfig, generate_questions_from_db, evaluate_retrieval
    from lore_mcp.ingest import ingest_directory

    embedder = _get_embedder()
    config = EvalConfig.from_env()
    config.num_questions = args.num_questions

    chunk_sizes = [512, 1024, 2048]
    chunk_overlaps = [64, 128]
    top_ks = [3, 5, 10]

    db_dir = Path(args.db_dir)
    db_dir.mkdir(parents=True, exist_ok=True)

    # Generate questions once from the first config
    first_db = str(db_dir / "optimize-first.db")
    ingest_directory(args.source_dir, first_db, embedder, chunk_size=1024, chunk_overlap=128)
    questions = generate_questions_from_db(first_db, config.num_questions)
    print(f"Generated {len(questions)} questions")

    best_score = -1
    best_config = {}
    all_results = []

    for cs in chunk_sizes:
        for co in chunk_overlaps:
            db_path = str(db_dir / f"opt-{cs}-{co}.db")
            ingest_directory(args.source_dir, db_path, embedder, chunk_size=cs, chunk_overlap=co)
            for tk in top_ks:
                result = evaluate_retrieval(db_path, embedder, questions, top_k=tk)
                avg = sum(result["scores"].values()) / max(len(result["scores"]), 1)
                entry = {"chunk_size": cs, "chunk_overlap": co, "top_k": tk,
                         "scores": result["scores"], "avg_score": round(avg, 4)}
                all_results.append(entry)
                print(f"  chunk={cs}/{co} top_k={tk}: avg={avg:.4f}")
                if avg > best_score:
                    best_score = avg
                    best_config = entry

    print(f"\nBest: chunk={best_config['chunk_size']}/{best_config['chunk_overlap']} "
          f"top_k={best_config['top_k']} avg={best_config['avg_score']:.4f}")

    if args.output:
        import json
        Path(args.output).write_text(json.dumps({
            "best": best_config, "all": all_results
        }, indent=2))
        print(f"Report: {args.output}")
