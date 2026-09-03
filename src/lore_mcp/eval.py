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
    probe_url = url.rstrip("/").rsplit("/v1", 1)[0] + "/v1/models"
    logger.debug("Probing judge at %s (verify=%s)", probe_url, verify)
    try:
        resp = httpx.get(
            probe_url,
            timeout=httpx.Timeout(timeout, connect=3.0),
            verify=verify,
        )
        logger.debug("Judge probe: %d", resp.status_code)
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
        text = re.sub(r"!\[((?:[^\[\]]|\[[^\]]*\])*)\]\([^)]+\)", lambda m: m.group(1), text)
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


def _is_good_sentence(s: str) -> bool:
    """Filter garbage sentences for extractive question generation."""
    s = s.strip()
    if len(s) < 30:
        return False
    words = s.split()
    if len(words) < 5:
        return False
    alpha_chars = sum(1 for c in s if c.isalpha())
    if alpha_chars / max(len(s), 1) < 0.5:
        return False
    if s.startswith("#"):
        return False
    if s.startswith("---"):
        return False
    return True


def _generate_extractive(chunks: list, num_questions: int) -> list[dict]:
    """Generate simple questions by extracting key sentences from chunks."""
    questions = []
    selected = random.sample(chunks, min(num_questions * 3, len(chunks)))
    for content, source_file in selected:
        sentences = [s.strip() for s in content.split(".") if _is_good_sentence(s)]
        if sentences:
            key_sentence = max(sentences, key=len)
            question = key_sentence[:100]
            questions.append({
                "question": question,
                "ground_truth": key_sentence,
                "contexts": [content],
                "source_file": source_file,
            })
        if len(questions) >= num_questions:
            break
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

    for q_idx, q in enumerate(questions, 1):
        logger.debug("─── Query %d/%d: %s ───", q_idx, len(questions), q["question"])
        query_emb = embedder.embed(q["question"])
        results = search(db, query_emb, top_k=top_k)
        retrieved_contexts = [r["content"] for r in results]

        for i, r in enumerate(results):
            logger.debug(
                "  result[%d]: score=%.4f source=%s content=%s",
                i, r["score"], r["source_file"],
                r["content"][:120].replace("\n", "\\n"),
            )

        scores = compute_retrieval_metrics(
            retrieved_contexts,
            q.get("ground_truth", ""),
        )
        logger.debug("  ★ scores: %s", " ".join(f"{k}={v}" for k, v in sorted(scores.items())))

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

        sources_list = [r["source_file"] for r in results]

        details.append({
            "question": q["question"],
            "ground_truth": q.get("ground_truth", ""),
            "contexts": retrieved_contexts,
            "sources": sources_list,
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
                logger.debug("RAGAS %s: question=%s...", name, kwargs.get("user_input", "")[:60])
                result = metric.score(**kwargs)
                scores[name] = round(float(result), 4)
                logger.debug("RAGAS %s: score=%s", name, scores[name])
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


def _strip_images(text: str) -> str:
    """Replace markdown images with alt text for readable reports."""
    import re
    return re.sub(
        r"!\[((?:[^\[\]]|\[[^\]]*\])*)\]\([^)]+\)",
        lambda m: m.group(1),
        text,
    )


def generate_eval_report_md(
    questions: list[dict],
    all_results: list[dict],
    best_config: dict,
    elapsed: float,
    output_path: str,
) -> str:
    """Write detailed evaluation report in markdown."""
    lines = []
    now = datetime.now(timezone.utc).isoformat()
    best_model = best_config.get("model_name", "")
    best_cs = best_config.get("chunk_size", 0)
    best_co = best_config.get("chunk_overlap", 0)
    best_tk = best_config.get("top_k", 0)
    best_avg = best_config.get("avg_score", 0)

    lines.append("# Evaluation Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append(f"Best config: ★ {best_model} chunk={best_cs}/{best_co} top_k={best_tk} avg={best_avg:.4f}")
    lines.append("")

    lines.append(f"## 1. Reference questions ({len(questions)})")
    lines.append("")
    lines.append("Questions are generated from document headings before chunking")
    lines.append("(heading-based strategy). Each markdown heading becomes a query,")
    lines.append("the section content below becomes the ground truth. This ensures")
    lines.append("evaluation is independent of chunking parameters.")
    lines.append("")

    for i, q in enumerate(questions, 1):
        lines.append(f"### Q{i} — {q['question']}")
        lines.append("")
        lines.append(f"- **Source:** {q.get('source_file', 'unknown')}")
        lines.append("- **Ground truth:**")
        lines.append("")
        lines.append(_strip_images(q.get("ground_truth", "")))
        lines.append("")

    lines.append("---")
    lines.append("")

    models_seen = []
    for r in all_results:
        if r["model_name"] not in models_seen:
            models_seen.append(r["model_name"])

    for m_idx, model_name in enumerate(models_seen, 2):
        lines.append(f"## {m_idx}. {model_name}")
        lines.append("")

        model_results = [r for r in all_results if r["model_name"] == model_name]
        for r in model_results:
            is_best = (r.get("model_name") == best_model
                       and r.get("chunk_size") == best_cs
                       and r.get("chunk_overlap") == best_co
                       and r.get("top_k") == best_tk)
            star = " ★" if is_best else ""
            lines.append(f"### chunk={r['chunk_size']}/{r['chunk_overlap']} top_k={r['top_k']}{star}")
            lines.append("")

            details = r.get("details", [])
            if details:
                score_keys = sorted(details[0].get("scores", {}).keys())
                lines.append(f"| # | Question | {' | '.join(score_keys)} |")
                lines.append(f"|--:|----------|{'|'.join('-----:' for _ in score_keys)}|")

                for d_idx, d in enumerate(details, 1):
                    scores_vals = " | ".join(f"{d['scores'].get(k, 0):.2f}" for k in score_keys)
                    lines.append(f"| {d_idx} | {d['question']} | {scores_vals} |")

                lines.append("")

                for d_idx, d in enumerate(details, 1):
                    src_files = [Path(s).stem for s in dict.fromkeys(d.get("sources", []))]
                    src_short = ", ".join(src_files)
                    raw_answer = d["contexts"][0] if d.get("contexts") else "(no result)"
                    answer = _strip_images(raw_answer)
                    answer_preview = answer.replace("\n", " ")[:200]

                    lines.append(f"**Q{d_idx}. {d['question']}**")
                    lines.append(f"Sources: {src_short}")
                    lines.append("")
                    lines.append(f"> {answer_preview}")
                    lines.append("")

            agg_scores = r.get("scores", {})
            if agg_scores and details:
                agg_label = "**Aggregate scores:**"
                if is_best:
                    agg_label = "**Aggregate scores:** ★ Best config"
                lines.append(agg_label)
                lines.append("")
                lines.append("| Metric | Avg | Min | Max |")
                lines.append("|--------|-----|-----|-----|")
                for key in sorted(agg_scores.keys()):
                    vals = [d["scores"].get(key, 0) for d in details]
                    avg_v = sum(vals) / max(len(vals), 1)
                    min_v = min(vals)
                    max_v = max(vals)
                    lines.append(f"| {key} | {avg_v:.2f} | {min_v:.2f} | {max_v:.2f} |")
                lines.append(f"| **avg** | **{r['avg_score']:.4f}** | | |")
                lines.append("")

        lines.append("---")
        lines.append("")

    lines.append("## Appendix: Scoring methodology")
    lines.append("")
    lines.append("### Question generation")
    lines.append("")
    lines.append("Questions are generated from source documents before chunking")
    lines.append("(heading-based strategy). Each markdown heading (`##`, `###`)")
    lines.append("becomes a query, the section content becomes the ground truth.")
    lines.append("Fallback: extractive sentences from indexed chunks.")
    lines.append("")
    lines.append("### Relevance")
    lines.append("")
    lines.append("A retrieved chunk is relevant if:")
    lines.append("")
    lines.append("    word_overlap(ground_truth, chunk) >= 0.3")
    lines.append("")
    lines.append("word_overlap = |words(GT) ∩ words(chunk)| / |words(GT)|")
    lines.append("")
    lines.append("### Metrics")
    lines.append("")
    lines.append("| Metric | Definition |")
    lines.append("|--------|-----------|")
    lines.append("| **hit** | 1.0 if at least one retrieved chunk is relevant, else 0.0 |")
    lines.append("| **mrr** | 1/(rank of first relevant chunk). 1.0 = first, 0.5 = second |")
    lines.append("| **ndcg@5** | Normalized Discounted Cumulative Gain. DCG = Σ rel_i / log₂(i+1). NDCG = DCG / ideal DCG |")
    lines.append("| **recall@5** | (relevant in top-5) / (total relevant). 1.0 = all found |")
    lines.append("| **word_overlap** | Best word overlap across retrieved chunks |")
    lines.append("| **avg** | Arithmetic mean of all metrics |")
    lines.append("")

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path


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
    report_path: str | None = None,
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
    phases = ["Indexing", "Questions", "Optimization"]
    reporter = ProgressReporter(
        collection="optimize",
        models=list(embedders.keys()),
        total_configs=total_configs,
        level=output_level,
        phases=phases,
    )
    reporter.print_header()

    effective_docs_dir = docs_dir or source_dir
    db_dir_path = Path(db_dir)
    db_dir_path.mkdir(parents=True, exist_ok=True)

    first_emb_name = next(iter(embedders))
    first_emb = embedders[first_emb_name]

    reporter.begin_phase("Indexing")
    reporter.print_section("Question generation")
    t0 = time.time()
    first_db = _optimize_ingest(
        db_dir_path, manifest_path, effective_docs_dir, first_emb,
        chunk_sizes[0], chunk_overlaps[0],
    )
    reporter.print_step("Initial indexing", elapsed=time.time() - t0)

    reporter.begin_phase("Questions")
    t0 = time.time()
    if effective_docs_dir:
        questions = generate_questions_from_sources(effective_docs_dir, num_questions)
    if not effective_docs_dir or not questions:
        questions = generate_questions_from_db(first_db, num_questions)
    reporter.print_step(f"Generated {len(questions)} questions", elapsed=time.time() - t0)
    reporter.print_questions(questions)

    best_score = -1.0
    best_config = {}
    all_results = []
    config_num = 0

    reporter.begin_phase("Optimization")
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
                        "details": result.get("details", []),
                    }
                    all_results.append(entry)

                    is_best = avg > best_score
                    if is_best:
                        best_score = avg
                        best_config = entry

                    scores_str = " ".join(f"{k}={v:.3f}" for k, v in sorted(scores.items()))
                    reporter.print_milestone(
                        config_num=config_num,
                        detail=model_name,
                        msg=f"[{config_num}/{total_configs}] {model_name} "
                        f"chunk={cs}/{co} top_k={tk}: avg={round(avg, 4)} ({scores_str})"
                    )

    for emb in embedders.values():
        emb.unload()

    reporter.print_results_table(all_results)
    elapsed = time.time() - reporter._start
    reporter.print_summary(configs_tested=total_configs, elapsed=elapsed)

    if report_path:
        generate_eval_report_md(questions, all_results, best_config, elapsed, report_path)
        reporter.print_step(f"Report: {report_path}")

    return {"best": best_config, "all": all_results}
