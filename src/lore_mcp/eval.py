"""RAG evaluation: testset generation, retrieval scoring. See docs/architecture.md."""

import json
import logging
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lore_mcp.store import open_db, search, list_sources, get_all_sources

logger = logging.getLogger(__name__)


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
) -> dict:
    """Evaluate retrieval quality on a set of questions.

    For each question, embeds the query, searches the index,
    and scores the retrieved contexts against ground truth.
    """
    db = open_db(db_path)
    details = []

    for q in questions:
        query_emb = embedder.embed(q["question"])
        results = search(db, query_emb, top_k=top_k)
        retrieved_contexts = [r["content"] for r in results]

        scores = _score_retrieval(
            question=q["question"],
            retrieved=retrieved_contexts,
            ground_truth=q.get("ground_truth", ""),
        )

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
        "num_questions": len(questions),
        "top_k": top_k,
        "scores": avg_scores,
        "details": details,
    }


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
    logger.info("Generating %d questions from %s", config.num_questions, db_path)
    questions = generate_questions_from_db(db_path, config.num_questions)

    logger.info("Evaluating retrieval (top_k=%d)", config.top_k)
    results = evaluate_retrieval(db_path, embedder, questions, top_k=config.top_k)

    if output_path:
        generate_eval_report(results, output_path)
        logger.info("Report written to %s", output_path)

    return results
