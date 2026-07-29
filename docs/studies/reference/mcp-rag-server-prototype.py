#!/usr/bin/env python3
"""Serveur MCP RAG pour Claude Code.

Interroge pgvector (corpus Red Hat indexé) et
retourne les chunks pertinents. Embedding avec
fallback : GPU vLLM (SNO) → CPU local (bge-m3).

Usage (lancé automatiquement par Claude Code) :
  python3 claude/scripts/mcp-rag-server.py

Configuration dans .claude/settings.json :
  {"mcpServers": {"redhat-rag": {
    "command": "python3",
    "args": ["claude/scripts/mcp-rag-server.py"]
  }}}
"""
import json
import os
import sys
import time
import urllib3

try:
    import setproctitle
    setproctitle.setproctitle("mcp-rag-server")
except ImportError:
    pass

import psycopg2
import requests
from mcp.server.fastmcp import FastMCP

urllib3.disable_warnings()

PG_CONFIG = {
    "host": os.environ.get(
        "RAG_PG_HOST", "CHANGE_ME_HOST"
    ),
    "port": int(
        os.environ.get("RAG_PG_PORT", "30432")
    ),
    "user": "llamastack",
    "dbname": "llamastack",
    "password": "CHANGE_ME_PASSWORD",
}

VLLM_URL = (
    "https://bge-m3-autorag-ai-serving"
    ".CHANGE_ME_DOMAIN/v1/embeddings"
)
VLLM_MODEL = "BAAI/bge-m3-embedding"
GPU_CHECK_INTERVAL = 300

# RAG_EMBED_MODE: auto, gpu, gpu-local, cpu
EMBED_MODE = os.environ.get(
    "RAG_EMBED_MODE", "auto"
)

mcp = FastMCP("redhat-rag")

_vllm_available = None
_vllm_last_check = 0
_local_model = None
_local_device = None


def _check_vllm():
    global _vllm_available, _vllm_last_check
    now = time.time()
    if now - _vllm_last_check < GPU_CHECK_INTERVAL:
        return _vllm_available
    _vllm_last_check = now
    try:
        r = requests.post(
            VLLM_URL,
            json={
                "model": VLLM_MODEL,
                "input": ["test"],
            },
            verify=False,
            timeout=5,
        )
        _vllm_available = r.status_code == 200
    except Exception:
        _vllm_available = False
    return _vllm_available


def _get_local_model(device=None):
    global _local_model, _local_device
    if _local_model is None or device != _local_device:
        from sentence_transformers import (
            SentenceTransformer,
        )
        _local_device = device or "cpu"
        _local_model = SentenceTransformer(
            "BAAI/bge-m3", device=_local_device
        )
    return _local_model


def _embed_vllm(text):
    r = requests.post(
        VLLM_URL,
        json={
            "model": VLLM_MODEL,
            "input": [text],
        },
        verify=False,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def _embed_local(text, device=None):
    model = _get_local_model(device)
    return model.encode(
        text, normalize_embeddings=True
    ).tolist()


def _embed(text):
    if EMBED_MODE == "gpu":
        return _embed_vllm(text)
    if EMBED_MODE == "gpu-local":
        return _embed_local(text, "cuda")
    if EMBED_MODE == "cpu":
        return _embed_local(text, "cpu")
    # auto: GPU local → vLLM SNO → CPU
    try:
        import torch
        if torch.cuda.is_available():
            return _embed_local(text, "cuda")
    except ImportError:
        pass
    if _check_vllm():
        return _embed_vllm(text)
    return _embed_local(text, "cpu")


def _get_conn():
    return psycopg2.connect(**PG_CONFIG)


@mcp.tool()
def search_docs(query: str, top_k: int = 3) -> str:
    """Recherche dans le corpus Red Hat indexé.

    Retourne les passages les plus pertinents
    pour la requête donnée, avec le score de
    similarité et le fichier source.
    """
    embedding = _embed(query)
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT content, source_file, "
        "1 - (embedding <=> %s::vector) AS score "
        "FROM rag_chunks "
        "ORDER BY embedding <=> %s::vector "
        "LIMIT %s",
        (json.dumps(embedding),
         json.dumps(embedding), top_k),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return "Aucun résultat trouvé."

    if _vllm_available and EMBED_MODE in ("auto", "gpu"):
        backend = "vLLM-GPU"
    elif _local_device == "cuda":
        backend = "local-GPU"
    else:
        backend = "CPU"
    results = []
    for content, source, score in rows:
        results.append(
            f"[{source}] (score: {score:.4f})\n"
            f"{content}"
        )
    header = (
        f"{len(rows)} résultat(s) "
        f"(embedding: {backend})"
    )
    return header + "\n\n---\n\n".join(
        [""] + results
    )


@mcp.tool()
def list_sources() -> str:
    """Liste les fichiers indexés dans le corpus
    RAG avec le nombre de chunks par fichier."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT source_file, count(*) "
        "FROM rag_chunks "
        "GROUP BY source_file "
        "ORDER BY source_file"
    )
    rows = cur.fetchall()
    cur.execute("SELECT count(*) FROM rag_chunks")
    total = cur.fetchone()[0]
    conn.close()

    lines = [
        f"{total} chunks, {len(rows)} fichiers\n"
    ]
    for source, count in rows:
        lines.append(f"  {source}: {count}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
