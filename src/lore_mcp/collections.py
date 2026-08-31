"""Multi-collection management over a directory of .db files.

See docs/architecture.md for design context. Each .db file is an
independent collection with its own vec0 index and metadata.
"""

import os
from pathlib import Path

from lore_mcp.store import list_sources, open_db, search


def build_collection_name(theme: str, level: str) -> str:
    """Build a collection name from theme and level."""
    return f"{theme}-{level}"


def collection_db_path(db_dir: str, name: str) -> str:
    """Return the .db file path for a named collection."""
    return str(Path(db_dir) / f"{name}.db")


def _parse_name(filename: str) -> dict:
    """Extract theme and level from a collection filename."""
    name = filename.removesuffix(".db")
    known_levels = {"nda", "libre", "restreint", "gris"}
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1] in known_levels:
        return {"theme": parts[0], "level": parts[1]}
    return {"theme": name, "level": ""}


def discover_collections(db_dir: str) -> list[dict]:
    """List all .db collections in a directory with metadata."""
    db_path = Path(db_dir)
    if not db_path.is_dir():
        return []
    results = []
    for f in sorted(db_path.glob("*.db")):
        try:
            db = open_db(str(f))
            sources = list_sources(db)
            chunk_count = sum(s["count"] for s in sources)
            file_count = len(sources)
            meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
            db.close()
            parsed = _parse_name(f.name)
            results.append({
                "name": f.stem,
                "theme": parsed["theme"],
                "level": parsed["level"],
                "chunk_count": chunk_count,
                "file_count": file_count,
                "chunk_size": int(meta["chunk_size"]) if "chunk_size" in meta else None,
                "chunk_overlap": int(meta["chunk_overlap"]) if "chunk_overlap" in meta else None,
                "model_name": meta.get("model_name"),
                "model_dim": int(meta["model_dim"]) if "model_dim" in meta else None,
                "path": str(f),
            })
        except Exception:
            continue
    return results


def search_collection(
    db_dir: str,
    collection: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """Search within a single named collection."""
    path = collection_db_path(db_dir, collection)
    if not Path(path).exists():
        raise FileNotFoundError(f"Collection not found: {collection} ({path})")
    db = open_db(path)
    results = search(db, query_embedding, top_k=top_k)
    db.close()
    for r in results:
        r["collection"] = collection
    return results


def search_across(
    db_dir: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """Search across all collections, merge results by score."""
    all_results = []
    for f in Path(db_dir).glob("*.db"):
        try:
            db = open_db(str(f))
            results = search(db, query_embedding, top_k=top_k)
            db.close()
            name = f.stem
            for r in results:
                r["collection"] = name
            all_results.extend(results)
        except Exception:
            continue
    all_results.sort(key=lambda r: r["score"], reverse=True)
    return all_results[:top_k]
