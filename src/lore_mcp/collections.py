"""Multi-collection management over a directory of .db files.

See docs/architecture.md for design context. Each .db file is an
independent collection with its own vec0 index and metadata.
"""

from pathlib import Path


def collection_db_path(db_dir: str, name: str) -> str:
    """Return the .db file path for a named collection."""
    return str(Path(db_dir) / f"{name}.db")
