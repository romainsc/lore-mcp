"""Unified configuration for lore-mcp. See docs/configuration.md.

Single config.yaml replaces all LORE_* env vars and build-config.yaml.
No env var fallback — everything comes from the config file.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class LoreConfig:
    """Complete configuration for all lore-mcp commands."""

    # Database
    db_path: str = "./lore.db"
    db_dir: str = ""

    # Embedding
    embedding_model: str = "nomic-ai/nomic-embed-text-v2-moe"
    embedding_mode: str = "builtin"
    embedding_api_url: str = ""
    embedding_api_model: str = ""
    embedding_api_verify: bool = True
    embedding_api_ca_bundle: str = ""
    embedding_batch_size: int = 64
    embedding_models: list[dict] = field(default_factory=list)

    # Reranking
    reranking_model: str = ""
    reranking_api_key: str = ""

    # Chunking
    chunk_size: int = 1024
    chunk_overlap: int = 128

    # LLM (enrich + judge)
    llm_model: str = "granite-3-2-8b-instruct"
    llm_api_url: str = ""
    llm_api_key: str = ""
    llm_verify_ssl: bool = True

    # Optimize
    optimize_chunk_sizes: list[int] = field(default_factory=lambda: [512, 1024, 2048])
    optimize_chunk_overlaps: list[int] = field(default_factory=lambda: [64, 128])
    optimize_top_ks: list[int] = field(default_factory=lambda: [3, 5, 10])
    optimize_num_questions: int = 50
    optimize_metrics: list[str] = field(
        default_factory=lambda: ["score_spread", "source_diversity", "result_diversity"]
    )

    @classmethod
    def from_file(cls, path: str) -> "LoreConfig":
        """Load config from a YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        db = data.get("database", {})
        emb = data.get("embedding", {})
        rerank = data.get("reranking", {})
        chunk = data.get("chunking", {})
        llm = data.get("llm", {})
        opt = data.get("optimize", {})

        # Embedding models list (for multi-model optimize)
        emb_models = []
        if isinstance(emb, list):
            emb_models = emb
            emb = emb[0] if emb else {}
        elif "models" in data:
            raise ValueError(
                f"Use 'embedding:' key (not 'models:') in {path}"
            )

        return cls(
            db_path=db.get("path", "./lore.db"),
            db_dir=db.get("dir", ""),
            embedding_model=emb.get("model", "nomic-ai/nomic-embed-text-v2-moe"),
            embedding_mode=emb.get("mode", "builtin"),
            embedding_api_url=emb.get("api_url", ""),
            embedding_api_model=emb.get("api_model", ""),
            embedding_api_verify=emb.get("api_verify", True),
            embedding_api_ca_bundle=emb.get("api_ca_bundle", ""),
            embedding_batch_size=emb.get("batch_size", 64),
            embedding_models=emb_models,
            reranking_model=rerank.get("model", ""),
            reranking_api_key=rerank.get("api_key", ""),
            chunk_size=chunk.get("chunk_size", 1024),
            chunk_overlap=chunk.get("chunk_overlap", 128),
            llm_model=llm.get("model", "granite-3-2-8b-instruct"),
            llm_api_url=llm.get("api_url", ""),
            llm_api_key=llm.get("api_key", ""),
            llm_verify_ssl=llm.get("verify_ssl", True),
            optimize_chunk_sizes=opt.get("chunk_sizes", [512, 1024, 2048]),
            optimize_chunk_overlaps=opt.get("chunk_overlaps", [64, 128]),
            optimize_top_ks=opt.get("top_ks", [3, 5, 10]),
            optimize_num_questions=opt.get("num_questions", 50),
            optimize_metrics=opt.get("metrics", ["score_spread", "source_diversity", "result_diversity"]),
        )

    @classmethod
    def defaults(cls) -> "LoreConfig":
        """Return config with all defaults."""
        return cls()

    @property
    def is_multi_collection(self) -> bool:
        return bool(self.db_dir)
