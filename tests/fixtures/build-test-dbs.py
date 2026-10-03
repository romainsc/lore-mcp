#!/usr/bin/env python3
"""Build test .db fixtures from existing test sources.

Usage: python tests/fixtures/build-test-dbs.py

Requires: pip install -e . (builtin:cpu mode, no TEI needed)
"""

from pathlib import Path

FIXTURES = Path(__file__).parent
ORIG = FIXTURES / "orig"


def build_minimal():
    """2 markdown sources — fastest fixture."""
    from lore_mcp.embedder import Embedder
    from lore_mcp.store import open_db, create_tables
    from lore_mcp.ingest import ingest_source

    db_path = FIXTURES / "test-minimal.db"
    if db_path.exists():
        db_path.unlink()

    embedder = Embedder(model_name="nomic-ai/nomic-embed-text-v2-moe", mode="builtin:cpu")

    db = open_db(str(db_path))
    create_tables(db, embedder.model_name, embedder.model_dim)
    db.close()

    for md in [ORIG / "test-markdown-sample.md"]:
        if md.exists():
            ingest_source(str(db_path), md, embedder,
                          {"title": md.stem, "lang": "eng"})

    db = open_db(str(db_path))
    count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    db.close()
    print(f"test-minimal.db: {count} chunks")


def build_mixed():
    """Markdown + HTML + CSV — tests multi-format without heavy deps."""
    from lore_mcp.embedder import Embedder
    from lore_mcp.store import open_db, create_tables
    from lore_mcp.ingest import ingest_source
    from lore_mcp.preprocess.parse import parse_to_markdown
    from lore_mcp.preprocess import clean_text
    import tempfile

    db_path = FIXTURES / "test-mixed.db"
    if db_path.exists():
        db_path.unlink()

    embedder = Embedder(model_name="nomic-ai/nomic-embed-text-v2-moe", mode="builtin:cpu")

    db = open_db(str(db_path))
    create_tables(db, embedder.model_name, embedder.model_dim)
    db.close()

    sources = [
        (ORIG / "test-markdown-sample.md", {"title": "Markdown Sample", "lang": "eng"}),
        (ORIG / "free-sw.en.html", {"title": "Free Software", "lang": "eng", "author": "FSF"}),
        (ORIG / "test-data-sample.csv", {"title": "Embedding Models", "lang": "eng"}),
    ]

    for src, meta in sources:
        if not src.exists():
            continue
        if src.suffix.lower() != ".md":
            text = parse_to_markdown(str(src))
            text = clean_text(text)
            tmp = Path(tempfile.mkdtemp()) / (src.stem + ".md")
            tmp.write_text(text, encoding="utf-8")
            ingest_source(str(db_path), tmp, embedder, meta)
        else:
            ingest_source(str(db_path), src, embedder, meta)

    db = open_db(str(db_path))
    count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    sources_count = db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    db.close()
    print(f"test-mixed.db: {sources_count} sources, {count} chunks")


if __name__ == "__main__":
    print("Building test fixtures...")
    build_minimal()
    build_mixed()
    print("Done.")
