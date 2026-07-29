"""Ingestion pipeline: preprocessing, chunking, indexing. See docs/architecture.md."""

import hashlib
import logging
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from lore_mcp.embedder import Embedder
from lore_mcp.store import create_tables, insert_chunks, open_db, validate_model

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 2048
DEFAULT_CHUNK_OVERLAP = 128
EMBED_BATCH_SIZE = 64
MIN_DOC_LENGTH = 100

MD_SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]


def preprocess(text: str) -> str:
    """Strip NUL characters and base64 image data lines."""
    text = text.replace("\x00", "")
    return "\n".join(
        line for line in text.split("\n") if "base64," not in line
    )


def chunk_document(
    text: str,
    source_file: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """Split text into chunks with deterministic IDs."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=MD_SEPARATORS,
    )
    parts = splitter.split_text(text)
    chunks = []
    for i, part in enumerate(parts):
        chunk_id = hashlib.sha256(
            f"{source_file}:{i}:{part[:64]}".encode()
        ).hexdigest()[:16]
        chunks.append({
            "id": chunk_id,
            "source_file": source_file,
            "chunk_index": i,
            "content": part,
        })
    return chunks


def ingest_directory(
    dir_path: str,
    db_path: str,
    embedder: Embedder,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> dict:
    """Index a directory of Markdown/text files into the store.

    Returns a summary dict with file_count, chunk_count, and errors.
    """
    db = open_db(db_path)
    create_tables(db, embedder.model_name, embedder.model_dim)
    validate_model(db, embedder.model_name, embedder.model_dim)

    docs_path = Path(dir_path)
    md_files = sorted(docs_path.rglob("*.md"))
    file_count = 0
    chunk_count = 0
    errors = []

    for md_file in md_files:
        try:
            rel = str(md_file.relative_to(docs_path))
            text = md_file.read_text(encoding="utf-8")
            text = preprocess(text)
            if len(text.strip()) < MIN_DOC_LENGTH:
                continue

            chunks = chunk_document(text, rel, chunk_size, chunk_overlap)
            for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
                batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
                texts = [c["content"] for c in batch]
                embeddings = embedder.embed_batch(texts)
                insert_chunks(db, batch, embeddings)

            file_count += 1
            chunk_count += len(chunks)
            logger.info("%s: %d chunks", rel, len(chunks))
        except Exception as e:
            errors.append({"file": str(md_file), "error": str(e)})
            logger.error("Failed to index %s: %s", md_file, e)

    db.close()
    return {"file_count": file_count, "chunk_count": chunk_count, "errors": errors}
