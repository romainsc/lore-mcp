"""RAG evaluation: testset generation, retrieval scoring. See docs/architecture.md."""

import json
import logging
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import sys
import time
import types

import yaml

from lore_mcp.progress import ProgressReporter


def _apply_ragas_stub() -> None:
    """Stub missing langchain_community.chat_models.vertexai module.

    ragas 0.4.3 unconditionally imports ChatVertexAI at import time.
    langchain-community was sunset May 2026 and the module was removed.
    This stub provides a dummy class so ragas can import without crash.
    See docs/studies/grooming-E10.23.md.
    """
    key = "langchain_community.chat_models.vertexai"
    if key not in sys.modules:
        mod = types.ModuleType(key)
        mod.ChatVertexAI = type("ChatVertexAI", (), {})
        sys.modules[key] = mod

from lore_mcp.store import open_db, search, list_sources, get_all_sources

logger = logging.getLogger(__name__)

METRIC_LEVELS = {
    "embedding": ["score_spread", "source_diversity", "result_diversity"],
    "retrieval": ["hit", "word_overlap", "mrr"],
    "ragas": ["faithfulness", "context_recall", "answer_correctness"],
}

RAGAS_METRIC_NAMES = set(METRIC_LEVELS["ragas"])


def check_ragas_guard(
    metrics: list[str],
    judge_url: str,
    judge_model: str,
    verify_ssl: bool = True,
) -> None:
    """Bidirectional RAGAS guard. Call before eval/optimize/build."""
    requested_ragas = [m for m in metrics if m in RAGAS_METRIC_NAMES]
    has_judge = bool(judge_url and judge_model)

    if has_judge and not requested_ragas:
        logger.warning(
            "Judge LLM configured (%s) but no RAGAS metrics requested. "
            "The judge will not be used. Add RAGAS metrics "
            "(faithfulness, context_recall, answer_correctness) to use it.",
            judge_model,
        )

    if requested_ragas:
        validate_metrics_prerequisites(
            metrics, judge_url, judge_model, verify_ssl=verify_ssl,
        )


def validate_metrics_prerequisites(
    metrics: list[str],
    judge_url: str,
    judge_model: str,
    verify_ssl: bool = True,
) -> None:
    """Fail fast if RAGAS metrics requested but prerequisites missing."""
    requested_ragas = [m for m in metrics if m in RAGAS_METRIC_NAMES]
    if not requested_ragas:
        return

    if not judge_url or not judge_model:
        raise ValueError(
            f"RAGAS metrics {requested_ragas} require a judge LLM. "
            f"Set judge in build-config.yaml or LORE_LLM_URL/LORE_LLM_MODEL."
        )

    try:
        _apply_ragas_stub()
        import ragas  # noqa: F401
    except ImportError:
        raise ImportError(
            f"RAGAS metrics {requested_ragas} require the ragas package. "
            f"Install with: pip install lore-mcp[eval]"
        )

    _probe_judge(judge_url, verify=verify_ssl)


def _probe_judge(url: str, timeout: float = 5.0, verify: bool = True) -> None:
    """Fail fast if the judge LLM endpoint is unreachable."""
    import httpx
    try:
        resp = httpx.get(
            url.rstrip("/").rsplit("/v1", 1)[0] + "/v1/models",
            timeout=httpx.Timeout(timeout, connect=3.0),
            verify=verify,
        )
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise ConnectionError(
            f"Judge LLM unreachable at {url} — start the server or "
            f"remove RAGAS metrics from config. ({e})"
        )


def compute_embedding_metrics(results: list[dict]) -> dict:
    """Level 1 metrics: no LLM, no ground truth needed."""
    if not results:
        return {"score_spread": 0.0, "source_diversity": 0.0, "result_diversity": 0.0}
    scores = [r["score"] for r in results]
    sources = [r["source_file"] for r in results]
    return {
        "score_spread": round(max(scores) - min(scores), 4),
        "source_diversity": round(len(set(sources)) / len(results), 4),
        "result_diversity": 0.0,
    }


RELEVANCE_THRESHOLD = 0.3


def _word_overlap(text_a: str, text_b: str) -> float:
    """Word-level overlap ratio: |A ∩ B| / |A|."""
    words_a = set(text_a.lower().split())
    if not words_a:
        return 0.0
    words_b = set(text_b.lower().split())
    return len(words_a & words_b) / len(words_a)


def compute_retrieval_metrics(contexts: list[str], ground_truth: str) -> dict:
    """Level 2 metrics: with ground truth, no LLM."""
    if not ground_truth or not contexts:
        return {"hit": 0.0, "word_overlap": 0.0, "mrr": 0.0,
                "ndcg@5": 0.0, "recall@5": 0.0}

    overlaps = [_word_overlap(ground_truth, ctx) for ctx in contexts]
    relevances = [1.0 if ov >= RELEVANCE_THRESHOLD else 0.0 for ov in overlaps]
    best_overlap = max(overlaps)

    hit = 1.0 if any(r > 0 for r in relevances) else 0.0
    mrr = 0.0
    for i, rel in enumerate(relevances):
        if rel > 0:
            mrr = 1.0 / (i + 1)
            break

    return {
        "hit": hit,
        "word_overlap": round(best_overlap, 4),
        "mrr": round(mrr, 4),
        "ndcg@5": ndcg_at_k(relevances, k=5),
        "recall@5": recall_at_k(relevances, total_relevant=max(1, sum(1 for r in relevances if r > 0)), k=5),
    }


def parse_model_configs(config_path: str) -> list[dict]:
    """Parse a YAML file with model configurations."""
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "models" in data or "embedding_models" in data:
        raise ValueError(
            f"Use 'embedding:' key (not 'models:' or 'embedding_models:') "
            f"in {config_path}"
        )
    return data.get("embedding", [])


def parse_model_configs_from_cli(models_str: str) -> list[dict]:
    """Parse comma-separated model names from CLI."""
    return [{"name": m.strip(), "mode": "builtin"} for m in models_str.split(",") if m.strip()]


@dataclass
class EvalConfig:
    """Configuration for RAG evaluation."""
    llm_url: str
    llm_model: str
    num_questions: int = 50
    top_k: int = 5
    verify_ssl: bool = True

    @classmethod
    def from_env(cls) -> "EvalConfig":
        """Read eval configuration from environment variables."""
        llm_url = os.environ.get("LORE_LLM_URL")
        if not llm_url:
            raise ValueError("LORE_LLM_URL is required for evaluation")
        return cls(
            llm_url=llm_url,
            llm_model=os.environ.get("LORE_LLM_MODEL", "granite-8b-instruct"),
            verify_ssl=os.environ.get("LORE_API_VERIFY", "true").lower() != "false",
        )


def generate_questions_from_db(
    db_path: str,
    num_questions: int = 50,
    llm=None,
) -> list[dict]:
    """Generate evaluation questions from indexed chunks.

    If an LLM is provided and RAGAS is available, uses TestsetGenerator.
    Otherwise, generates simple extractive questions from chunk content.
    """
    db = open_db(db_path)
    chunks = db.execute(
        "SELECT content, source_file FROM chunks ORDER BY RANDOM() LIMIT ?",
        (num_questions * 3,),
    ).fetchall()
    db.close()

    if not chunks:
        return []

    try:
        if llm is not None:
            return _generate_with_ragas(chunks, num_questions, llm)
    except ImportError:
        logger.info("RAGAS not installed, using extractive question generation")

    return _generate_extractive(chunks, num_questions)


def generate_questions_from_sources(
    docs_dir: str,
    num_questions: int = 50,
) -> list[dict]:
    """Generate QA pairs from document headings before chunking."""
    import re
    questions = []
    docs_path = Path(docs_dir)
    for md_file in sorted(docs_path.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r"^(#{2,3})\s+(.+)$", text, flags=re.MULTILINE)
        i = 1
        while i < len(sections) - 2:
            level = sections[i]
            heading = sections[i + 1].strip()
            body = sections[i + 2].strip()
            next_heading = re.split(r"^#{1,3}\s+", body, flags=re.MULTILINE)[0].strip()
            if len(next_heading) >= 30:
                rel_path = str(md_file.relative_to(docs_path))
                questions.append({
                    "question": heading,
                    "ground_truth": next_heading,
                    "source_file": rel_path,
                })
            i += 3
    random.shuffle(questions)
    return questions[:num_questions]


def ndcg_at_k(relevances: list[float], k: int) -> float:
    """Normalized Discounted Cumulative Gain at k."""
    import math
    relevances = relevances[:k]
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))
    ideal = sorted(relevances, reverse=True)
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    if idcg == 0:
        return 0.0
    return round(dcg / idcg, 4)


def recall_at_k(relevances: list[float], total_relevant: int, k: int) -> float:
    """Recall at k: fraction of relevant items found in top-k."""
    if total_relevant == 0:
        return 0.0
    found = sum(1 for r in relevances[:k] if r > 0)
    return round(found / total_relevant, 4)


def _generate_extractive(chunks: list, num_questions: int) -> list[dict]:
    """Generate simple questions by extracting key sentences from chunks."""
    questions = []
    selected = random.sample(chunks, min(num_questions, len(chunks)))
    for content, source_file in selected:
        sentences = [s.strip() for s in content.split(".") if len(s.strip()) > 20]
        if sentences:
            key_sentence = max(sentences, key=len)
            questions.append({
                "question": f"What does the documentation say about: {key_sentence[:80]}?",
                "ground_truth": key_sentence,
                "contexts": [content],
                "source_file": source_file,
            })
    return questions[:num_questions]


def _generate_with_ragas(chunks: list, num_questions: int, llm) -> list[dict]:
    """Generate questions using RAGAS TestsetGenerator."""
    from ragas.testset import TestsetGenerator

    docs = [{"page_content": c[0], "metadata": {"source": c[1]}} for c in chunks]
    generator = TestsetGenerator(llm=llm)
    testset = generator.generate(docs, testset_size=num_questions)
    return [
        {
            "question": row["question"],
            "ground_truth": row.get("ground_truth", ""),
            "contexts": row.get("contexts", []),
        }
        for row in testset.to_list()
    ]


def evaluate_retrieval(
    db_path: str,
    embedder,
    questions: list[dict],
    top_k: int = 5,
    metrics: list[str] | None = None,
    judge_url: str = "",
    judge_model: str = "",
    judge_verify_ssl: bool = True,
) -> dict:
    """Evaluate retrieval quality on a set of questions.

    For each question, embeds the query, searches the index,
    and scores the retrieved contexts against ground truth.
    When RAGAS metrics are requested, calls the judge LLM.
    """
    if metrics is None:
        metrics = ["hit", "word_overlap"]

    requested_ragas = [m for m in metrics if m in RAGAS_METRIC_NAMES]

    db = open_db(db_path)
    details = []

    for q in questions:
        query_emb = embedder.embed(q["question"])
        results = search(db, query_emb, top_k=top_k)
        retrieved_contexts = [r["content"] for r in results]

        scores = compute_retrieval_metrics(
            retrieved_contexts,
            q.get("ground_truth", ""),
        )

        if requested_ragas and judge_url and judge_model:
            ragas_scores = _score_with_ragas(
                question=q["question"],
                contexts=retrieved_contexts,
                ground_truth=q.get("ground_truth", ""),
                metrics=requested_ragas,
                judge_url=judge_url,
                judge_model=judge_model,
                embedder=embedder,
                verify_ssl=judge_verify_ssl,
            )
            scores.update(ragas_scores)

        details.append({
            "question": q["question"],
            "ground_truth": q.get("ground_truth", ""),
            "contexts": retrieved_contexts,
            "sources": [r["source_file"] for r in results],
            "scores": scores,
        })

    db.close()

    avg_scores = _average_scores(details)
    return {
        "db_path": db_path,
        "model_name": embedder.model_name,
        "num_questions": len(questions),
        "top_k": top_k,
        "scores": avg_scores,
        "details": details,
    }


class _RagasEmbeddingsWrapper:
    """Adapt lore-mcp Embedder to the RAGAS/langchain embeddings interface.

    Inherits from langchain Embeddings so that RAGAS async methods
    (aembed_text → aembed_documents → embed_documents) work via
    the built-in run_in_executor fallback.
    """

    def __init__(self, embedder):
        self._embedder = embedder

    def embed_query(self, text: str) -> list[float]:
        return self._embedder.embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed_batch(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_text(self, text: str) -> list[float]:
        return self.embed_query(text)

    async def embed_text(self, text: str, is_async=True) -> list[float]:
        return self.embed_query(text)


def _score_with_ragas(
    question: str,
    contexts: list[str],
    ground_truth: str,
    metrics: list[str],
    judge_url: str,
    judge_model: str,
    embedder=None,
    verify_ssl: bool = True,
) -> dict:
    """Score with RAGAS metrics via the judge LLM."""
    _apply_ragas_stub()
    from ragas.metrics.collections import (
        Faithfulness, ContextRecall, AnswerCorrectness,
    )
    from ragas.llms import llm_factory
    from openai import AsyncOpenAI
    import httpx

    http_client = httpx.AsyncClient(verify=verify_ssl) if not verify_ssl else None
    client = AsyncOpenAI(
        api_key="dummy", base_url=judge_url, http_client=http_client,
    )
    llm = llm_factory(judge_model, provider="openai", client=client)

    ragas_emb = _RagasEmbeddingsWrapper(embedder) if embedder else None

    response = contexts[0] if contexts else ""

    metric_configs = {
        "faithfulness": (
            Faithfulness(llm=llm),
            dict(user_input=question, response=response,
                 retrieved_contexts=contexts),
        ),
        "context_recall": (
            ContextRecall(llm=llm),
            dict(user_input=question, retrieved_contexts=contexts,
                 reference=ground_truth),
        ),
        "answer_correctness": (
            AnswerCorrectness(llm=llm, embeddings=ragas_emb),
            dict(user_input=question, response=response,
                 reference=ground_truth),
        ),
    }

    scores = {}
    for name in metrics:
        if name in metric_configs:
            metric, kwargs = metric_configs[name]
            try:
                result = metric.score(**kwargs)
                scores[name] = round(float(result), 4)
            except Exception as e:
                logger.warning("RAGAS metric %s failed: %s", name, e)
                scores[name] = 0.0
    return scores


def _score_retrieval(
    question: str,
    retrieved: list[str],
    ground_truth: str,
) -> dict:
    """Score retrieval quality for a single question.

    Uses simple text overlap when RAGAS is not available.
    """
    if not ground_truth or not retrieved:
        return {"hit": 0.0}

    gt_lower = ground_truth.lower()
    hit = 1.0 if any(gt_lower in ctx.lower() for ctx in retrieved) else 0.0

    gt_words = set(gt_lower.split())
    if gt_words:
        best_overlap = max(
            len(gt_words & set(ctx.lower().split())) / len(gt_words)
            for ctx in retrieved
        ) if retrieved else 0.0
    else:
        best_overlap = 0.0

    return {
        "hit": hit,
        "word_overlap": round(best_overlap, 4),
    }


def _average_scores(details: list[dict]) -> dict:
    """Compute average scores across all questions."""
    if not details:
        return {}
    all_keys = set()
    for d in details:
        all_keys.update(d["scores"].keys())
    avg = {}
    for key in sorted(all_keys):
        values = [d["scores"].get(key, 0.0) for d in details]
        avg[key] = round(sum(values) / len(values), 4)
    return avg


def generate_eval_report(results: dict, output_path: str) -> str:
    """Write evaluation results to a JSON report file."""
    results["generated_at"] = datetime.now(timezone.utc).isoformat()
    Path(output_path).write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def run_eval(
    db_path: str,
    embedder,
    config: EvalConfig,
    output_path: str | None = None,
) -> dict:
    """Full eval pipeline: generate questions, retrieve, score, report."""
    check_ragas_guard(
        metrics=["hit", "word_overlap"],
        judge_url=config.llm_url,
        judge_model=config.llm_model,
        verify_ssl=config.verify_ssl,
    )
    logger.info("Generating %d questions from %s", config.num_questions, db_path)
    questions = generate_questions_from_db(db_path, config.num_questions)

    logger.info("Evaluating retrieval (top_k=%d)", config.top_k)
    results = evaluate_retrieval(db_path, embedder, questions, top_k=config.top_k)

    if output_path:
        generate_eval_report(results, output_path)
        logger.info("Report written to %s", output_path)

    return results


def _optimize_ingest(
    db_dir_path,
    manifest_path: str | None,
    docs_dir: str | None,
    embedder,
    chunk_size: int,
    chunk_overlap: int,
) -> str:
    """Ingest for one optimization config. Returns the .db path."""
    from lore_mcp.ingest import ingest_directory, ingest_with_manifest

    db_name = f"opt-{chunk_size}-{chunk_overlap}"
    db_path = str(db_dir_path / f"{db_name}.db")

    if Path(db_path).exists():
        Path(db_path).unlink()

    if manifest_path and docs_dir:
        ingest_with_manifest(
            manifest_path, docs_dir, str(db_dir_path), embedder,
            chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        )
        from lore_mcp.manifest import parse_manifest
        collection = parse_manifest(manifest_path)["collection"]
        manifest_db = str(db_dir_path / f"{collection}.db")
        if Path(manifest_db).exists() and manifest_db != db_path:
            Path(manifest_db).rename(db_path)
    elif docs_dir:
        ingest_directory(docs_dir, db_path, embedder,
                         chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    return db_path


def run_optimize(
    embedder=None,
    embedders: dict | None = None,
    db_dir: str = "./optimize-dbs",
    source_dir: str | None = None,
    manifest_path: str | None = None,
    docs_dir: str | None = None,
    chunk_sizes: list[int] | None = None,
    chunk_overlaps: list[int] | None = None,
    top_ks: list[int] | None = None,
    num_questions: int = 30,
    metrics: list[str] | None = None,
    judge_url: str = "",
    judge_model: str = "",
    judge_verify_ssl: bool = True,
    output_level: str = "default",
) -> dict:
    """Optimize chunking parameters and optionally embedding models.

    When embedders dict is provided (name→Embedder), iterates over
    all models. Otherwise uses the single embedder. Supports manifest
    for bibliographic metadata preservation.
    """
    if chunk_sizes is None:
        chunk_sizes = [512, 1024, 2048]
    if chunk_overlaps is None:
        chunk_overlaps = [64, 128]
    if top_ks is None:
        top_ks = [3, 5, 10]

    if metrics is None:
        metrics = ["score_spread", "source_diversity", "result_diversity"]

    check_ragas_guard(
        metrics=metrics, judge_url=judge_url, judge_model=judge_model,
        verify_ssl=judge_verify_ssl,
    )

    if embedders is None and embedder is not None:
        embedders = {embedder.model_name: embedder}
    if not embedders:
        raise ValueError("Provide embedder or embedders")

    total_configs = len(embedders) * len(chunk_sizes) * len(chunk_overlaps) * len(top_ks)
    reporter = ProgressReporter(
        collection="optimize",
        models=list(embedders.keys()),
        total_configs=total_configs,
        level=output_level,
    )
    reporter.print_header()

    effective_docs_dir = docs_dir or source_dir
    db_dir_path = Path(db_dir)
    db_dir_path.mkdir(parents=True, exist_ok=True)

    first_emb_name = next(iter(embedders))
    first_emb = embedders[first_emb_name]

    reporter.print_section("Question generation")
    t0 = time.time()
    first_db = _optimize_ingest(
        db_dir_path, manifest_path, effective_docs_dir, first_emb,
        chunk_sizes[0], chunk_overlaps[0],
    )
    reporter.print_step("Initial indexing", elapsed=time.time() - t0)

    t0 = time.time()
    if effective_docs_dir:
        questions = generate_questions_from_sources(effective_docs_dir, num_questions)
    if not effective_docs_dir or not questions:
        questions = generate_questions_from_db(first_db, num_questions)
    reporter.print_step(f"Generated {len(questions)} questions", elapsed=time.time() - t0)

    best_score = -1.0
    best_config = {}
    all_results = []
    config_num = 0

    reporter.print_section("Optimization")

    prev_emb = None
    for model_name, emb in embedders.items():
        if prev_emb is not None and prev_emb is not emb:
            prev_emb.unload()
        prev_emb = emb
        reporter.print_step(f"Model: {model_name}")
        for cs in chunk_sizes:
            for co in chunk_overlaps:
                t0 = time.time()
                db_path = _optimize_ingest(
                    db_dir_path, manifest_path, effective_docs_dir, emb, cs, co,
                )
                reporter.print_file(f"Indexed chunk={cs}/{co}", int(time.time() - t0))

                for tk in top_ks:
                    config_num += 1
                    result = evaluate_retrieval(
                        db_path, emb, questions, top_k=tk,
                        metrics=metrics,
                        judge_url=judge_url,
                        judge_model=judge_model,
                        judge_verify_ssl=judge_verify_ssl,
                    )

                    scores = {**result["scores"]}

                    if result["details"]:
                        search_results = [
                            {"score": s.get("score", 0), "source_file": s.get("source_file", ""),
                             "content": s.get("content", "")}
                            for d in result["details"]
                            for s in [{"score": 0, "source_file": "", "content": c}
                                      for c in d.get("contexts", [])]
                        ]
                        emb_scores = compute_embedding_metrics(search_results) if search_results else {}
                        scores.update(emb_scores)

                    avg = sum(scores.values()) / max(len(scores), 1)
                    entry = {
                        "model_name": model_name,
                        "chunk_size": cs, "chunk_overlap": co, "top_k": tk,
                        "scores": scores, "avg_score": round(avg, 4),
                    }
                    all_results.append(entry)

                    is_best = avg > best_score
                    if is_best:
                        best_score = avg
                        best_config = entry

                    reporter.print_milestone(
                        f"[{config_num}/{total_configs}] {model_name} "
                        f"chunk={cs}/{co} top_k={tk}: avg={round(avg, 4)}"
                    )

    for emb in embedders.values():
        emb.unload()

    reporter.print_results_table(all_results)
    elapsed = time.time() - reporter._start
    reporter.print_summary(configs_tested=total_configs, elapsed=elapsed)

    return {"best": best_config, "all": all_results}
