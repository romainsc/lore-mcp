"""Unified build configuration. See docs/architecture.md."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class BuildConfig:
    """Unified configuration for lore-mcp build."""
    embedding_models: list[dict] = field(default_factory=list)
    judge_model: str = ""
    judge_api_url: str = ""
    judge_verify_ssl: bool = True
    metrics: list[str] = field(default_factory=lambda: ["score_spread", "source_diversity", "result_diversity"])
    chunk_sizes: list[int] = field(default_factory=lambda: [512, 1024, 2048])
    chunk_overlaps: list[int] = field(default_factory=lambda: [64, 128])
    top_ks: list[int] = field(default_factory=lambda: [3, 5, 10])
    num_questions: int = 50
    default_model: str = ""
    default_chunk_size: int = 1024
    default_chunk_overlap: int = 128

    @classmethod
    def from_file(cls, path: str) -> "BuildConfig":
        """Load build config from a YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        judge = data.get("judge", {})
        optimize = data.get("optimize", {})
        defaults = data.get("defaults", {})

        return cls(
            embedding_models=data.get("embedding_models") or data.get("models", []),
            judge_model=judge.get("model", ""),
            judge_api_url=judge.get("api_url", ""),
            judge_verify_ssl=judge.get("verify_ssl", True),
            metrics=data.get("metrics", ["score_spread", "source_diversity", "result_diversity"]),
            chunk_sizes=optimize.get("chunk_sizes", [512, 1024, 2048]),
            chunk_overlaps=optimize.get("chunk_overlaps", [64, 128]),
            top_ks=optimize.get("top_ks", [3, 5, 10]),
            num_questions=optimize.get("num_questions", 50),
            default_model=defaults.get("model", ""),
            default_chunk_size=defaults.get("chunk_size", 1024),
            default_chunk_overlap=defaults.get("chunk_overlap", 128),
        )

    @classmethod
    def from_env(cls) -> "BuildConfig":
        """Fallback: build config from environment variables."""
        return cls(
            judge_model=os.environ.get("LORE_LLM_MODEL", ""),
            judge_api_url=os.environ.get("LORE_LLM_URL", ""),
            judge_verify_ssl=os.environ.get("LORE_API_VERIFY", "true").lower() != "false",
        )
