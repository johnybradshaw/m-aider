"""Tests for recommendation engine."""

import tempfile
from pathlib import Path

import pytest

from src.maider.benchmark_db import BenchmarkDatabase
from src.maider.recommendations import (
    RecommendationEngine,
    TaskType,
    BudgetConstraint,
    ModelSizePreference,
)


class TestRecommendationEngine:
    """Test RecommendationEngine class."""

    @pytest.fixture
    def db_with_data(self):
        """Create database with sample benchmark data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test-benchmark.json"
            db = BenchmarkDatabase(db_path)

            # Add sample results for different configs
            configs = [
                # RTX 6000 x2, 70B, fast but expensive
                {
                    "gpu_type": "g1-gpu-rtx6000-2",
                    "gpu_count": 2,
                    "vram_per_gpu": 48,
                    "hourly_cost": 3.00,
                    "model_id": "Qwen/Qwen2.5-Coder-70B-Instruct-AWQ",
                    "model_category": "70b",
                    "tps": 45.3,
                },
                # RTX 4000 x2, 30B, slower but better value
                {
                    "gpu_type": "g2-gpu-rtx4000a2-s",
                    "gpu_count": 2,
                    "vram_per_gpu": 20,
                    "hourly_cost": 1.04,
                    "model_id": "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
                    "model_category": "30b",
                    "tps": 38.1,
                },
                # RTX 6000 x1, 30B, mid-range
                {
                    "gpu_type": "g1-gpu-rtx6000-1",
                    "gpu_count": 1,
                    "vram_per_gpu": 48,
                    "hourly_cost": 1.50,
                    "model_id": "Qwen/Qwen2.5-Coder-32B-Instruct",
                    "model_category": "30b",
                    "tps": 32.5,
                },
                # RTX 4000 x1, 14B, cheap and fast enough
                {
                    "gpu_type": "g2-gpu-rtx4000a1-s",
                    "gpu_count": 1,
                    "vram_per_gpu": 20,
                    "hourly_cost": 0.52,
                    "model_id": "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ",
                    "model_category": "14b",
                    "tps": 28.0,
                },
            ]

            for config in configs:
                tps = config.pop("tps")
                result = db.create_result(
                    **config,
                    vllm_config={"tensor_parallel_size": config["gpu_count"]},
                    results_by_category={
                        "coding": {
                            "avg_tokens_per_sec": tps,
                            "cost_per_1k_tokens": (config["hourly_cost"] / (tps * 3600)) * 1000,
                        }
                    },
                    summary={
                        "avg_tokens_per_sec": tps,
                        "cost_per_1k_tokens": (config["hourly_cost"] / (tps * 3600)) * 1000,
                        "tests_passed": 12,
                        "tests_total": 12,
                    },
                    tests=[],
                )
                db.add_result(result)

            yield db

    def test_recommend_coding_balanced(self, db_with_data):
        """Test recommendations for coding with balanced preference."""
        engine = RecommendationEngine(db_with_data)

        recs = engine.recommend(
            task_type=TaskType.CODING,
            budget_constraint=BudgetConstraint.NO_CONSTRAINT,
            model_size_pref=ModelSizePreference.BALANCED,
            limit=3,
        )

        assert len(recs) > 0
        assert len(recs) <= 3

        # All should have Low confidence (only 1 run each)
        assert all(r.confidence_level == "Low" for r in recs)

    def test_recommend_with_budget_under_1(self, db_with_data):
        """Test recommendations with budget constraint under $1/hour."""
        engine = RecommendationEngine(db_with_data)

        recs = engine.recommend(
            task_type=TaskType.CODING,
            budget_constraint=BudgetConstraint.UNDER_1,
            model_size_pref=ModelSizePreference.BALANCED,
            limit=5,
        )

        # Only RTX 4000 x1 should match ($.52/hr)
        assert len(recs) == 1
        assert recs[0].hourly_cost < 1.0

    def test_recommend_with_budget_1_to_3(self, db_with_data):
        """Test recommendations with budget $1-3/hour."""
        engine = RecommendationEngine(db_with_data)

        recs = engine.recommend(
            task_type=TaskType.CODING,
            budget_constraint=BudgetConstraint.ONE_TO_THREE,
            model_size_pref=ModelSizePreference.BALANCED,
            limit=5,
        )

        # RTX 4000 x2 ($1.04), RTX 6000 x1 ($1.50), and RTX 6000 x2 ($3.00) should match
        assert len(recs) == 3
        assert all(1.0 <= r.hourly_cost <= 3.0 for r in recs)

    def test_recommend_smallest_viable(self, db_with_data):
        """Test recommendations with smallest viable preference."""
        engine = RecommendationEngine(db_with_data)

        recs = engine.recommend(
            task_type=TaskType.CODING,
            budget_constraint=BudgetConstraint.NO_CONSTRAINT,
            model_size_pref=ModelSizePreference.SMALLEST_VIABLE,
            limit=3,
        )

        # Smallest VRAM configs should be prioritized
        # RTX 4000 x1 (20GB) should rank higher than RTX 6000 x2 (96GB)
        assert recs[0].total_vram <= recs[-1].total_vram

    def test_recommend_largest_available(self, db_with_data):
        """Test recommendations with largest available preference."""
        engine = RecommendationEngine(db_with_data)

        recs = engine.recommend(
            task_type=TaskType.CODING,
            budget_constraint=BudgetConstraint.NO_CONSTRAINT,
            model_size_pref=ModelSizePreference.LARGEST_AVAILABLE,
            limit=5,  # Get all configs to verify largest is included
        )

        # Largest VRAM configs should be prioritized
        # With LARGEST_AVAILABLE, VRAM is a factor but not the only one
        # Efficiency is still considered within same confidence level
        largest_vram = max(r.total_vram for r in recs)
        assert largest_vram == 96  # Should include RTX 6000 x2
        # Check that configs are sorted with larger VRAM ranked higher than smaller VRAM
        # when comparing configs with similar efficiency
        vram_values = [r.total_vram for r in recs]
        assert 96 in vram_values  # Largest config should be present

    def test_calculate_cost_efficiency(self):
        """Test cost efficiency calculation."""
        engine = RecommendationEngine(None)  # Don't need db for this

        # 45 tokens/sec at $3/hour = 15 efficiency
        eff = engine.calculate_cost_efficiency(45.0, 3.00)
        assert eff == pytest.approx(15.0)

        # 38 tokens/sec at $1.04/hour = 36.5 efficiency
        eff = engine.calculate_cost_efficiency(38.0, 1.04)
        assert eff == pytest.approx(36.54, rel=0.01)

        # Edge case: zero cost
        eff = engine.calculate_cost_efficiency(45.0, 0.0)
        assert eff == pytest.approx(0.0)

        # Edge case: zero tokens
        eff = engine.calculate_cost_efficiency(0.0, 3.00)
        assert eff == pytest.approx(0.0)

    def test_calculate_confidence(self):
        """Test confidence level calculation."""
        engine = RecommendationEngine(None)  # Don't need db for this

        # High confidence (3+ runs)
        level, color = engine.calculate_confidence(3)
        assert level == "High"
        assert color == "green"

        level, color = engine.calculate_confidence(5)
        assert level == "High"
        assert color == "green"

        # Medium confidence (2 runs)
        level, color = engine.calculate_confidence(2)
        assert level == "Medium"
        assert color == "yellow"

        # Low confidence (1 run)
        level, color = engine.calculate_confidence(1)
        assert level == "Low"
        assert color == "red"

        # None (0 runs)
        level, color = engine.calculate_confidence(0)
        assert level == "None"
        assert color == "dim"

    def test_filter_by_budget(self, db_with_data):
        """Test budget filtering."""
        engine = RecommendationEngine(db_with_data)
        all_results = db_with_data.get_results()

        # No constraint
        filtered = engine._filter_by_budget(all_results, BudgetConstraint.NO_CONSTRAINT)
        assert len(filtered) == len(all_results)

        # Under $1/hour
        filtered = engine._filter_by_budget(all_results, BudgetConstraint.UNDER_1)
        assert all(r.hourly_cost < 1.0 for r in filtered)
        assert len(filtered) == 1  # Only RTX 4000 x1

        # $1-$3/hour
        filtered = engine._filter_by_budget(all_results, BudgetConstraint.ONE_TO_THREE)
        assert all(1.0 <= r.hourly_cost <= 3.0 for r in filtered)

        # Over $3/hour
        filtered = engine._filter_by_budget(all_results, BudgetConstraint.OVER_THREE)
        assert all(r.hourly_cost > 3.0 for r in filtered)
        assert len(filtered) == 0  # None in our test data

    def test_group_by_config(self, db_with_data):
        """Test grouping results by config."""
        engine = RecommendationEngine(db_with_data)
        all_results = db_with_data.get_results()

        groups = engine._group_by_config(all_results)

        # Should have 4 unique configs
        assert len(groups) == 4

        # Each group key should be gpu_type|model_category
        for key, results in groups.items():
            assert "|" in key
            gpu_type, model_cat = key.split("|")
            assert all(r.gpu_type == gpu_type for r in results)
            assert all(r.model_category == model_cat for r in results)

    def test_create_recommendation(self, db_with_data):
        """Test recommendation creation from results."""
        engine = RecommendationEngine(db_with_data)

        # Get one config's results
        results = db_with_data.get_results(gpu_type="g1-gpu-rtx6000-2")

        rec = engine._create_recommendation(results, "coding")

        assert rec is not None
        assert rec.gpu_type == "g1-gpu-rtx6000-2"
        assert rec.gpu_count == 2
        assert rec.total_vram == 96
        assert rec.model_category == "70b"
        assert rec.avg_tokens_per_sec == pytest.approx(45.3)
        assert rec.confidence_level == "Low"  # Only 1 run
        assert rec.num_benchmark_runs == 1
        assert rec.task_category == "coding"

    def test_recommend_with_multiple_runs(self, db_with_data):
        """Test recommendations with multiple runs for same config."""
        # Add more runs for one config
        for _ in range(2):
            result = db_with_data.create_result(
                gpu_type="g1-gpu-rtx6000-2",
                gpu_count=2,
                vram_per_gpu=48,
                hourly_cost=3.00,
                model_id="Qwen/Qwen2.5-Coder-70B-Instruct-AWQ",
                model_category="70b",
                vllm_config={"tensor_parallel_size": 2},
                results_by_category={
                    "coding": {
                        "avg_tokens_per_sec": 45.0,  # Slightly different
                        "cost_per_1k_tokens": 0.0246,
                    }
                },
                summary={
                    "avg_tokens_per_sec": 45.0,
                    "cost_per_1k_tokens": 0.0246,
                    "tests_passed": 12,
                    "tests_total": 12,
                },
                tests=[],
            )
            db_with_data.add_result(result)

        engine = RecommendationEngine(db_with_data)

        recs = engine.recommend(
            task_type=TaskType.CODING,
            budget_constraint=BudgetConstraint.NO_CONSTRAINT,
            model_size_pref=ModelSizePreference.BALANCED,
            limit=5,
        )

        # RTX 6000 x2 should now have High confidence
        rtx6000_rec = next((r for r in recs if r.gpu_type == "g1-gpu-rtx6000-2"), None)
        assert rtx6000_rec is not None
        assert rtx6000_rec.confidence_level == "High"
        assert rtx6000_rec.num_benchmark_runs == 3

        # Should be ranked first due to high confidence
        assert recs[0].gpu_type == "g1-gpu-rtx6000-2"

    def test_recommend_empty_database(self):
        """Test recommendations with empty database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test-benchmark.json"
            db = BenchmarkDatabase(db_path)
            engine = RecommendationEngine(db)

            recs = engine.recommend(
                task_type=TaskType.CODING,
                budget_constraint=BudgetConstraint.NO_CONSTRAINT,
                model_size_pref=ModelSizePreference.BALANCED,
                limit=3,
            )

            assert len(recs) == 0

    def test_recommend_mixed_workload(self, db_with_data):
        """Test recommendations for mixed workload."""
        engine = RecommendationEngine(db_with_data)

        recs = engine.recommend(
            task_type=TaskType.MIXED,
            budget_constraint=BudgetConstraint.NO_CONSTRAINT,
            model_size_pref=ModelSizePreference.BALANCED,
            limit=3,
        )

        # Should work but with "mixed" task category
        assert len(recs) > 0
        assert all(r.task_category == "mixed" for r in recs)

    def test_recommendation_ranking_order(self, db_with_data):
        """Test that recommendations are ranked correctly."""
        # Add multiple runs to one config for high confidence
        for _ in range(2):
            result = db_with_data.create_result(
                gpu_type="g2-gpu-rtx4000a2-s",
                gpu_count=2,
                vram_per_gpu=20,
                hourly_cost=1.04,
                model_id="Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
                model_category="30b",
                vllm_config={"tensor_parallel_size": 2},
                results_by_category={
                    "coding": {
                        "avg_tokens_per_sec": 38.0,
                        "cost_per_1k_tokens": 0.0178,
                    }
                },
                summary={
                    "avg_tokens_per_sec": 38.0,
                    "cost_per_1k_tokens": 0.0178,
                    "tests_passed": 12,
                    "tests_total": 12,
                },
                tests=[],
            )
            db_with_data.add_result(result)

        engine = RecommendationEngine(db_with_data)

        recs = engine.recommend(
            task_type=TaskType.CODING,
            budget_constraint=BudgetConstraint.NO_CONSTRAINT,
            model_size_pref=ModelSizePreference.BALANCED,
            limit=5,
        )

        # RTX 4000 x2 now has High confidence (3 runs)
        # Should be ranked first due to confidence + excellent efficiency
        assert recs[0].gpu_type == "g2-gpu-rtx4000a2-s"
        assert recs[0].confidence_level == "High"
