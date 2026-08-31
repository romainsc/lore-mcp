"""Tests for E10.15: RAGAS explicit only, fail fast."""

from unittest.mock import patch
import pytest


RAGAS_METRICS = ["faithfulness", "context_recall", "answer_correctness"]
NON_RAGAS_METRICS = ["score_spread", "source_diversity", "hit", "mrr"]


class TestRagasValidation:
    def test_ragas_requested_but_not_installed(self):
        """Requesting RAGAS metrics without ragas installed → error."""
        from lore_mcp.eval import validate_metrics_prerequisites
        with pytest.raises(ImportError, match="ragas"):
            with patch.dict("sys.modules", {"ragas": None}):
                validate_metrics_prerequisites(
                    metrics=["faithfulness"],
                    judge_url="http://localhost:11434/v1",
                    judge_model="granite-8b",
                )

    def test_ragas_requested_without_judge(self):
        """Requesting RAGAS metrics without judge LLM → error."""
        from lore_mcp.eval import validate_metrics_prerequisites
        with pytest.raises(ValueError, match="judge"):
            validate_metrics_prerequisites(
                metrics=["faithfulness"],
                judge_url="",
                judge_model="",
            )

    def test_non_ragas_metrics_no_validation(self):
        """Non-RAGAS metrics don't require judge or ragas."""
        from lore_mcp.eval import validate_metrics_prerequisites
        validate_metrics_prerequisites(
            metrics=["score_spread", "source_diversity", "mrr"],
            judge_url="",
            judge_model="",
        )

    def test_identify_ragas_metrics(self):
        """RAGAS metrics are correctly identified."""
        from lore_mcp.eval import RAGAS_METRIC_NAMES
        for m in RAGAS_METRICS:
            assert m in RAGAS_METRIC_NAMES
        for m in NON_RAGAS_METRICS:
            assert m not in RAGAS_METRIC_NAMES
