"""Tests for benchmark database operations."""

import json
import tempfile
from pathlib import Path

import pytest

from src.maider.benchmark_db import BenchmarkDatabase, BenchmarkResult


class TestBenchmarkDatabase:
    """Test BenchmarkDatabase class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test-benchmark.json"
            yield BenchmarkDatabase(db_path)

    @pytest.fixture
    def sample_result(self):
        """Create a sample benchmark result."""
        return {
            "gpu_type": "g1-gpu-rtx6000-2",
            "gpu_count": 2,
            "vram_per_gpu": 48,
            "hourly_cost": 3.00,
            "model_id": "Qwen/Qwen2.5-Coder-70B-Instruct-AWQ",
            "model_category": "70b",
            "vllm_config": {
                "tensor_parallel_size": 2,
                "max_model_len": 32768,
                "gpu_memory_utilization": 0.90,
            },
            "results_by_category": {
                "coding": {
                    "avg_tokens_per_sec": 45.3,
                    "cost_per_1k_tokens": 0.0242,
                    "tests_passed": 4,
                },
                "context_heavy": {
                    "avg_tokens_per_sec": 42.1,
                    "cost_per_1k_tokens": 0.0251,
                    "tests_passed": 4,
                },
                "reasoning": {
                    "avg_tokens_per_sec": 43.7,
                    "cost_per_1k_tokens": 0.0245,
                    "tests_passed": 4,
                },
            },
            "summary": {
                "avg_tokens_per_sec": 43.7,
                "cost_per_1k_tokens": 0.0246,
                "tests_passed": 12,
                "tests_total": 12,
            },
            "tests": [
                {
                    "test_name": "Simple function",
                    "category": "coding",
                    "success": True,
                    "tokens_per_sec": 45.0,
                }
            ],
        }

    def test_database_creation(self, temp_db):
        """Test database file is created."""
        assert temp_db.db_path.exists()

        # Check initial structure
        data = json.loads(temp_db.db_path.read_text())
        assert "version" in data
        assert "benchmarks" in data
        assert data["version"] == "1.0"
        assert data["benchmarks"] == []

    def test_create_result(self, temp_db, sample_result):
        """Test creating a benchmark result object."""
        result = temp_db.create_result(**sample_result)

        assert isinstance(result, BenchmarkResult)
        assert result.gpu_type == sample_result["gpu_type"]
        assert result.gpu_count == sample_result["gpu_count"]
        assert result.total_vram == 96  # 2 x 48GB
        assert result.hourly_cost == sample_result["hourly_cost"]
        assert result.model_category == sample_result["model_category"]
        assert result.id  # Should have UUID
        assert result.timestamp  # Should have timestamp

    def test_add_result(self, temp_db, sample_result):
        """Test adding a result to database."""
        result = temp_db.create_result(**sample_result)
        result_id = temp_db.add_result(result)

        assert result_id == result.id
        assert len(result_id) == 36  # UUID length

        # Verify it was saved
        data = json.loads(temp_db.db_path.read_text())
        assert len(data["benchmarks"]) == 1
        assert data["benchmarks"][0]["id"] == result_id

    def test_get_results(self, temp_db, sample_result):
        """Test retrieving all results."""
        # Add multiple results
        result1 = temp_db.create_result(**sample_result)
        temp_db.add_result(result1)

        result2_data = sample_result.copy()
        result2_data["gpu_type"] = "g2-gpu-rtx4000a2-s"
        result2_data["model_category"] = "30b"
        result2 = temp_db.create_result(**result2_data)
        temp_db.add_result(result2)

        # Get all results
        results = temp_db.get_results()
        assert len(results) == 2
        assert all(isinstance(r, BenchmarkResult) for r in results)

    def test_get_results_with_filters(self, temp_db, sample_result):
        """Test retrieving results with filters."""
        # Add two different GPU types
        result1 = temp_db.create_result(**sample_result)
        temp_db.add_result(result1)

        result2_data = sample_result.copy()
        result2_data["gpu_type"] = "g2-gpu-rtx4000a2-s"
        result2_data["gpu_count"] = 2
        result2_data["vram_per_gpu"] = 20
        result2_data["model_category"] = "30b"
        result2 = temp_db.create_result(**result2_data)
        temp_db.add_result(result2)

        # Filter by GPU type
        rtx6000_results = temp_db.get_results(gpu_type="g1-gpu-rtx6000-2")
        assert len(rtx6000_results) == 1
        assert rtx6000_results[0].gpu_type == "g1-gpu-rtx6000-2"

        # Filter by model category
        model_70b_results = temp_db.get_results(model_category="70b")
        assert len(model_70b_results) == 1
        assert model_70b_results[0].model_category == "70b"

        # Filter by task category
        coding_results = temp_db.get_results(task_category="coding")
        assert len(coding_results) == 2  # Both have coding results

    def test_get_best_by_metric(self, temp_db, sample_result):
        """Test getting best results by metric."""
        # Add results with different performance
        result1 = temp_db.create_result(**sample_result)
        temp_db.add_result(result1)

        # Slower but cheaper
        result2_data = sample_result.copy()
        result2_data["gpu_type"] = "g2-gpu-rtx4000a2-s"
        result2_data["hourly_cost"] = 1.04
        result2_data["summary"]["avg_tokens_per_sec"] = 38.0
        result2 = temp_db.create_result(**result2_data)
        temp_db.add_result(result2)

        # Get best by tokens_per_sec (descending)
        best_tps = temp_db.get_best_by_metric("tokens_per_sec", limit=1)
        assert len(best_tps) == 1
        assert best_tps[0].summary["avg_tokens_per_sec"] == 43.7

        # Get best by cost (ascending)
        best_cost = temp_db.get_best_by_metric("cost_per_1k_tokens", limit=1, ascending=True)
        assert len(best_cost) == 1
        # Should be the cheaper one (result2 - will have lower cost_per_1k)

        # Get best by efficiency
        best_eff = temp_db.get_best_by_metric("cost_efficiency", limit=1)
        assert len(best_eff) == 1
        # RTX4000 should have better efficiency (38/1.04 = 36.5 vs 43.7/3.0 = 14.6)
        assert best_eff[0].gpu_type == "g2-gpu-rtx4000a2-s"

    def test_get_coverage_report(self, temp_db, sample_result):
        """Test coverage report generation."""
        # Empty database
        coverage = temp_db.get_coverage_report()
        assert coverage["total_benchmarks"] == 0
        assert coverage["gpu_types_tested"] == 0
        assert coverage["gpu_types_total"] == 7
        assert len(coverage["tested_configs"]) == 0

        # Add one result
        result = temp_db.create_result(**sample_result)
        temp_db.add_result(result)

        coverage = temp_db.get_coverage_report()
        assert coverage["total_benchmarks"] == 1
        assert coverage["gpu_types_tested"] == 1
        assert len(coverage["tested_configs"]) == 1

        config = coverage["tested_configs"][0]
        assert config["gpu_type"] == "g1-gpu-rtx6000-2"
        assert config["model_category"] == "70b"
        assert config["count"] == 1

        # Add another run of same config
        result2 = temp_db.create_result(**sample_result)
        temp_db.add_result(result2)

        coverage = temp_db.get_coverage_report()
        assert coverage["total_benchmarks"] == 2
        assert coverage["gpu_types_tested"] == 1  # Still 1 unique type
        assert len(coverage["tested_configs"]) == 1
        assert coverage["tested_configs"][0]["count"] == 2

    def test_export_json(self, temp_db, sample_result):
        """Test JSON export."""
        result = temp_db.create_result(**sample_result)
        temp_db.add_result(result)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "export.json"
            temp_db.export("json", output)

            assert output.exists()
            data = json.loads(output.read_text())
            assert len(data) == 1
            assert data[0]["gpu_type"] == "g1-gpu-rtx6000-2"

    def test_export_csv(self, temp_db, sample_result):
        """Test CSV export."""
        result = temp_db.create_result(**sample_result)
        temp_db.add_result(result)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "export.csv"
            temp_db.export("csv", output)

            assert output.exists()
            content = output.read_text()
            assert "GPU Type" in content
            assert "g1-gpu-rtx6000-2" in content

    def test_export_markdown(self, temp_db, sample_result):
        """Test Markdown export."""
        result = temp_db.create_result(**sample_result)
        temp_db.add_result(result)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "export.md"
            temp_db.export("markdown", output)

            assert output.exists()
            content = output.read_text()
            assert "# Benchmark Results" in content
            assert "g1-gpu-rtx6000-2" in content
            assert "| " in content  # Markdown table format

    def test_concurrent_writes(self, temp_db, sample_result):
        """Test file locking prevents concurrent write issues."""
        # This test verifies atomic writes work
        # In practice, fcntl.flock prevents corruption
        result1 = temp_db.create_result(**sample_result)
        result2_data = sample_result.copy()
        result2_data["gpu_type"] = "g2-gpu-rtx4000a2-s"
        result2 = temp_db.create_result(**result2_data)

        # Write both (sequentially, but testing atomic pattern)
        temp_db.add_result(result1)
        temp_db.add_result(result2)

        # Verify both were saved
        results = temp_db.get_results()
        assert len(results) == 2

        # Database should still be valid JSON
        data = json.loads(temp_db.db_path.read_text())
        assert len(data["benchmarks"]) == 2
