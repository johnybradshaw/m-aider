"""Benchmark database for storing and querying performance results."""

import csv
import fcntl
import json
import shutil
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class BenchmarkResult:
    """Represents a single benchmark result."""

    id: str
    timestamp: str
    gpu_type: str
    gpu_count: int
    vram_per_gpu: int
    total_vram: int
    hourly_cost: float
    model_id: str
    model_category: str
    vllm_config: Dict[str, Any]
    results_by_category: Dict[str, Dict[str, Any]]
    summary: Dict[str, Any]
    tests: List[Dict[str, Any]]


class BenchmarkDatabase:
    """Manages benchmark results database."""

    DB_VERSION = "1.0"

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize benchmark database.

        Args:
            db_path: Path to database file (default: ~/.cache/linode-vms/benchmark-database.json)
        """
        if db_path is None:
            cache_dir = Path.home() / ".cache" / "linode-vms"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = cache_dir / "benchmark-database.json"

        self.db_path = db_path
        self._ensure_database()

    def _ensure_database(self):
        """Ensure database file exists with proper structure."""
        if not self.db_path.exists():
            self._write_database({"version": self.DB_VERSION, "benchmarks": []})

    def _read_database(self) -> Dict[str, Any]:
        """Read database with file locking.

        Returns:
            Dictionary containing database data
        """
        with open(self.db_path, "r") as f:
            # Acquire shared lock for reading
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        # Handle migration if needed
        if "version" not in data:
            data["version"] = "1.0"

        return data

    def _write_database(self, data: Dict[str, Any]):
        """Write database with atomic write and file locking.

        Args:
            data: Database data to write
        """
        # Write to temporary file first (atomic write pattern)
        temp_path = self.db_path.with_suffix(".tmp")

        with open(temp_path, "w") as f:
            # Acquire exclusive lock for writing
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        # Atomic rename
        shutil.move(str(temp_path), str(self.db_path))

    def add_result(self, result: BenchmarkResult) -> str:
        """Add new benchmark result to database.

        Args:
            result: BenchmarkResult to add

        Returns:
            ID of the added result
        """
        data = self._read_database()

        # Convert result to dict
        result_dict = asdict(result)

        # Append to benchmarks list
        data["benchmarks"].append(result_dict)

        # Write back
        self._write_database(data)

        return result.id

    def get_results(
        self,
        gpu_type: Optional[str] = None,
        model_category: Optional[str] = None,
        task_category: Optional[str] = None,
    ) -> List[BenchmarkResult]:
        """Query results with filters.

        Args:
            gpu_type: Filter by GPU type (e.g., "g1-gpu-rtx6000-2")
            model_category: Filter by model category (e.g., "70b", "30b")
            task_category: Filter by task category (e.g., "coding", "context_heavy")

        Returns:
            List of BenchmarkResult objects matching filters
        """
        data = self._read_database()
        results = []

        for benchmark in data.get("benchmarks", []):
            # Apply filters
            if gpu_type and benchmark.get("gpu_type") != gpu_type:
                continue

            if model_category and benchmark.get("model_category") != model_category:
                continue

            if task_category:
                # Check if task_category exists in results_by_category
                results_by_cat = benchmark.get("results_by_category", {})
                if task_category not in results_by_cat:
                    continue

            # Convert to BenchmarkResult object
            try:
                result = BenchmarkResult(**benchmark)
                results.append(result)
            except (TypeError, KeyError):
                # Skip malformed results
                continue

        return results

    def get_best_by_metric(
        self,
        metric: str,
        task_category: Optional[str] = None,
        limit: int = 10,
        ascending: bool = False,
    ) -> List[BenchmarkResult]:
        """Get top results sorted by metric.

        Args:
            metric: Metric to sort by ("tokens_per_sec", "cost_per_1k_tokens", "cost_efficiency")
            task_category: Filter by task category
            limit: Maximum number of results to return
            ascending: Sort ascending (for cost metrics) or descending (for performance metrics)

        Returns:
            List of BenchmarkResult objects sorted by metric
        """
        results = self.get_results(task_category=task_category)

        # Define sort key based on metric
        def sort_key(result: BenchmarkResult) -> float:
            summary = result.summary

            if metric == "tokens_per_sec":
                return summary.get("avg_tokens_per_sec", 0)
            elif metric == "cost_per_1k_tokens":
                return summary.get("cost_per_1k_tokens", float("inf"))
            elif metric == "cost_efficiency":
                # Cost efficiency = tokens_per_sec / hourly_cost
                tps = summary.get("avg_tokens_per_sec", 0)
                cost = result.hourly_cost
                return tps / cost if cost > 0 else 0
            else:
                return 0

        # Sort results
        sorted_results = sorted(results, key=sort_key, reverse=not ascending)

        return sorted_results[:limit]

    def get_coverage_report(self) -> Dict[str, Any]:
        """Generate coverage report showing which configs have been tested.

        Returns:
            Dictionary with coverage information:
            {
                "tested_configs": [{"gpu_type": str, "model_category": str, "count": int, "last_run": str}],
                "total_benchmarks": int,
                "gpu_types_tested": int,
                "gpu_types_total": int,
            }
        """
        results = self.get_results()

        # Count benchmarks by GPU type and model category
        config_counts: Dict[str, Dict[str, Any]] = {}

        for result in results:
            key = f"{result.gpu_type}|{result.model_category}"

            if key not in config_counts:
                config_counts[key] = {
                    "gpu_type": result.gpu_type,
                    "model_category": result.model_category,
                    "count": 0,
                    "last_run": result.timestamp,
                }

            config_counts[key]["count"] += 1

            # Update last_run if this is more recent
            if result.timestamp > config_counts[key]["last_run"]:
                config_counts[key]["last_run"] = result.timestamp

        # Convert to list
        tested_configs = list(config_counts.values())

        # Sort by last_run (most recent first)
        tested_configs.sort(key=lambda x: x["last_run"], reverse=True)

        # Get unique GPU types
        gpu_types_tested = len({config["gpu_type"] for config in tested_configs})

        # Total GPU types available (from linode provider)
        gpu_types_total = (
            7  # RTX4000x1, RTX4000x2, RTX4000x4, RTX6000x1, RTX6000x2, RTX6000x3, RTX6000x4
        )

        return {
            "tested_configs": tested_configs,
            "total_benchmarks": len(results),
            "gpu_types_tested": gpu_types_tested,
            "gpu_types_total": gpu_types_total,
        }

    def get_results_by_config(
        self, gpu_type: str, model_category: Optional[str] = None
    ) -> List[BenchmarkResult]:
        """Get all benchmark results for a specific GPU type and optional model category.

        Args:
            gpu_type: GPU type to query
            model_category: Optional model category filter

        Returns:
            List of BenchmarkResult objects
        """
        return self.get_results(gpu_type=gpu_type, model_category=model_category)

    def export(self, format: str, output_path: Path):
        """Export database to file.

        Args:
            format: Export format ("json", "csv", "markdown")
            output_path: Path to write output file
        """
        results = self.get_results()

        if format == "json":
            self._export_json(results, output_path)
        elif format == "csv":
            self._export_csv(results, output_path)
        elif format == "markdown":
            self._export_markdown(results, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_json(self, results: List[BenchmarkResult], output_path: Path):
        """Export to JSON format."""
        data = [asdict(result) for result in results]
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def _export_csv(self, results: List[BenchmarkResult], output_path: Path):
        """Export to CSV format."""
        if not results:
            # Write empty CSV with headers
            with open(output_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "ID",
                        "Timestamp",
                        "GPU Type",
                        "GPU Count",
                        "Total VRAM (GB)",
                        "Model",
                        "Model Category",
                        "Avg Tokens/Sec",
                        "Cost per 1K Tokens",
                        "Hourly Cost",
                        "Tests Passed",
                        "Tests Total",
                    ]
                )
            return

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(
                [
                    "ID",
                    "Timestamp",
                    "GPU Type",
                    "GPU Count",
                    "Total VRAM (GB)",
                    "Model",
                    "Model Category",
                    "Avg Tokens/Sec",
                    "Cost per 1K Tokens",
                    "Hourly Cost",
                    "Tests Passed",
                    "Tests Total",
                ]
            )

            # Write rows
            for result in results:
                summary = result.summary
                writer.writerow(
                    [
                        result.id,
                        result.timestamp,
                        result.gpu_type,
                        result.gpu_count,
                        result.total_vram,
                        result.model_id,
                        result.model_category,
                        f"{summary.get('avg_tokens_per_sec', 0):.2f}",
                        f"${summary.get('cost_per_1k_tokens', 0):.4f}",
                        f"${result.hourly_cost:.2f}",
                        summary.get("tests_passed", 0),
                        summary.get("tests_total", 0),
                    ]
                )

    def _export_markdown(self, results: List[BenchmarkResult], output_path: Path):
        """Export to Markdown table format."""
        lines = [
            "# Benchmark Results",
            "",
            "| GPU Type | GPUs | VRAM | Model | Tokens/Sec | Cost/1K | Hourly Cost | Tests |",
            "|----------|------|------|-------|------------|---------|-------------|-------|",
        ]

        for result in results:
            summary = result.summary
            # Truncate model name if too long
            model_name = result.model_id.split("/")[-1]
            if len(model_name) > 30:
                model_name = model_name[:27] + "..."

            lines.append(
                f"| {result.gpu_type} | {result.gpu_count}x | {result.total_vram}GB | "
                f"{model_name} | {summary.get('avg_tokens_per_sec', 0):.1f} | "
                f"${summary.get('cost_per_1k_tokens', 0):.4f} | ${result.hourly_cost:.2f} | "
                f"{summary.get('tests_passed', 0)}/{summary.get('tests_total', 0)} |"
            )

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

    def create_result(
        self,
        gpu_type: str,
        gpu_count: int,
        vram_per_gpu: int,
        hourly_cost: float,
        model_id: str,
        model_category: str,
        vllm_config: Dict[str, Any],
        results_by_category: Dict[str, Dict[str, Any]],
        summary: Dict[str, Any],
        tests: List[Dict[str, Any]],
    ) -> BenchmarkResult:
        """Create a new BenchmarkResult object with generated ID and timestamp.

        Args:
            gpu_type: GPU type identifier
            gpu_count: Number of GPUs
            vram_per_gpu: VRAM per GPU in GB
            hourly_cost: Hourly cost in USD
            model_id: HuggingFace model ID
            model_category: Model category (e.g., "70b", "30b")
            vllm_config: vLLM configuration dict
            results_by_category: Results organized by task category
            summary: Summary metrics
            tests: List of individual test results

        Returns:
            BenchmarkResult object ready to be added to database
        """
        return BenchmarkResult(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            vram_per_gpu=vram_per_gpu,
            total_vram=gpu_count * vram_per_gpu,
            hourly_cost=hourly_cost,
            model_id=model_id,
            model_category=model_category,
            vllm_config=vllm_config,
            results_by_category=results_by_category,
            summary=summary,
            tests=tests,
        )
