"""Recommendation engine for GPU/model configuration selection."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any

from .benchmark_db import BenchmarkDatabase, BenchmarkResult


class TaskType(Enum):
    """Types of tasks for recommendation."""

    CODING = "coding"
    CONTEXT_HEAVY = "context_heavy"
    REASONING = "reasoning"
    MIXED = "mixed"


class BudgetConstraint(Enum):
    """Budget constraints for recommendations."""

    UNDER_1 = "under_1"  # Under $1/hour
    ONE_TO_THREE = "1_to_3"  # $1-3/hour
    OVER_THREE = "over_3"  # Over $3/hour
    NO_CONSTRAINT = "no_constraint"  # No budget limit


class ModelSizePreference(Enum):
    """Model size preferences."""

    SMALLEST_VIABLE = "smallest_viable"  # Best value
    BALANCED = "balanced"  # Good performance/cost
    LARGEST_AVAILABLE = "largest_available"  # Maximum performance


@dataclass
class Recommendation:
    """A GPU/model configuration recommendation."""

    gpu_type: str
    gpu_count: int
    total_vram: int
    model_id: str
    model_category: str
    avg_tokens_per_sec: float
    cost_per_1k_tokens: float
    hourly_cost: float
    cost_efficiency: float
    confidence_level: str  # "High", "Medium", "Low"
    confidence_color: str  # Rich color name
    num_benchmark_runs: int
    task_category: str  # Which task category this recommendation is based on
    notes: List[str]  # Additional notes or warnings


class RecommendationEngine:
    """Engine for generating GPU/model recommendations."""

    def __init__(self, db: BenchmarkDatabase):
        """Initialize recommendation engine.

        Args:
            db: BenchmarkDatabase instance
        """
        self.db = db

    def recommend(
        self,
        task_type: TaskType,
        budget_constraint: BudgetConstraint,
        model_size_pref: ModelSizePreference,
        limit: int = 3,
    ) -> List[Recommendation]:
        """Generate ranked recommendations.

        Args:
            task_type: Type of task (coding, context_heavy, reasoning, mixed)
            budget_constraint: Budget constraint
            model_size_pref: Model size preference
            limit: Maximum number of recommendations to return

        Returns:
            List of Recommendation objects, ranked by suitability
        """
        # Get appropriate task category
        if task_type == TaskType.MIXED:
            task_category = None  # Consider all categories
        else:
            task_category = task_type.value

        # Get all results for this task category
        results = self.db.get_results(task_category=task_category)

        if not results:
            return []

        # Apply budget filter
        results = self._filter_by_budget(results, budget_constraint)

        if not results:
            return []

        # Group by config (gpu_type + model_category)
        config_groups = self._group_by_config(results)

        # Generate recommendations from each config group
        recommendations = []
        for config_key, config_results in config_groups.items():
            rec = self._create_recommendation(config_results, task_category or "mixed")
            if rec:
                recommendations.append(rec)

        # Rank recommendations based on preferences
        recommendations = self._rank_recommendations(recommendations, model_size_pref)

        return recommendations[:limit]

    def _filter_by_budget(
        self, results: List[BenchmarkResult], budget: BudgetConstraint
    ) -> List[BenchmarkResult]:
        """Filter results by budget constraint."""
        if budget == BudgetConstraint.NO_CONSTRAINT:
            return results

        def matches_budget(cost: float) -> bool:
            if budget == BudgetConstraint.UNDER_1:
                return cost < 1.0
            if budget == BudgetConstraint.ONE_TO_THREE:
                return 1.0 <= cost <= 3.0
            if budget == BudgetConstraint.OVER_THREE:
                return cost > 3.0
            return True

        filtered = []
        for result in results:
            if matches_budget(result.hourly_cost):
                filtered.append(result)

        return filtered

    def _group_by_config(self, results: List[BenchmarkResult]) -> Dict[str, List[BenchmarkResult]]:
        """Group results by GPU type and model category."""
        groups: Dict[str, List[BenchmarkResult]] = {}

        for result in results:
            key = f"{result.gpu_type}|{result.model_category}"
            if key not in groups:
                groups[key] = []
            groups[key].append(result)

        return groups

    def _create_recommendation(
        self, results: List[BenchmarkResult], task_category: str
    ) -> Optional[Recommendation]:
        """Create recommendation from a group of results for the same config."""
        if not results:
            return None

        # Use the most recent result as the primary source
        primary = results[-1]  # Assuming results are ordered by timestamp

        # Calculate average metrics across all runs
        avg_tps = sum(r.summary.get("avg_tokens_per_sec", 0) for r in results) / len(results)
        avg_cost_1k = sum(r.summary.get("cost_per_1k_tokens", 0) for r in results) / len(results)

        # Calculate cost efficiency
        cost_efficiency = self.calculate_cost_efficiency(avg_tps, primary.hourly_cost)

        # Calculate confidence
        num_runs = len(results)
        confidence_level, confidence_color = self.calculate_confidence(num_runs)

        # Generate notes
        notes = []
        if num_runs == 1:
            notes.append("⚠ Single benchmark - results may vary")
        elif num_runs == 2:
            notes.append("Based on limited data (2 runs)")

        if task_category == "mixed":
            notes.append("Averaged across all task categories")

        return Recommendation(
            gpu_type=primary.gpu_type,
            gpu_count=primary.gpu_count,
            total_vram=primary.total_vram,
            model_id=primary.model_id,
            model_category=primary.model_category,
            avg_tokens_per_sec=avg_tps,
            cost_per_1k_tokens=avg_cost_1k,
            hourly_cost=primary.hourly_cost,
            cost_efficiency=cost_efficiency,
            confidence_level=confidence_level,
            confidence_color=confidence_color,
            num_benchmark_runs=num_runs,
            task_category=task_category,
            notes=notes,
        )

    def _rank_recommendations(
        self,
        recommendations: List[Recommendation],
        model_size_pref: ModelSizePreference,
    ) -> List[Recommendation]:
        """Rank recommendations based on preferences."""

        def rank_key(rec: Recommendation) -> tuple:
            """Generate sort key for recommendation."""
            # Priority factors:
            # 1. Confidence (high confidence = lower number = higher priority)
            confidence_priority = {"High": 0, "Medium": 1, "Low": 2, "None": 3}

            # 2. Model size preference
            vram_priority = rec.total_vram
            if model_size_pref == ModelSizePreference.SMALLEST_VIABLE:
                vram_priority = -vram_priority  # Smaller is better
            elif model_size_pref == ModelSizePreference.LARGEST_AVAILABLE:
                vram_priority = rec.total_vram  # Larger is better
            else:  # BALANCED
                # Prefer mid-range (around 48-96GB)
                vram_priority = abs(72 - rec.total_vram)

            # 3. Cost efficiency (higher is better)
            # Negate so higher efficiency gets lower sort value
            efficiency_priority = -rec.cost_efficiency

            # 4. Performance (tokens/sec, higher is better)
            performance_priority = -rec.avg_tokens_per_sec

            return (
                confidence_priority[rec.confidence_level],
                efficiency_priority,
                vram_priority,
                performance_priority,
            )

        recommendations.sort(key=rank_key)
        return recommendations

    @staticmethod
    def calculate_cost_efficiency(tokens_per_sec: float, hourly_cost: float) -> float:
        """Calculate cost efficiency score.

        Args:
            tokens_per_sec: Token generation rate
            hourly_cost: Hourly cost in USD

        Returns:
            Cost efficiency (tokens/sec per dollar/hour)
        """
        if hourly_cost <= 0:
            return 0.0

        return tokens_per_sec / hourly_cost

    @staticmethod
    def calculate_confidence(num_runs: int) -> tuple[str, str]:
        """Calculate confidence level and color.

        Args:
            num_runs: Number of benchmark runs for this config

        Returns:
            Tuple of (confidence_level, color) for Rich formatting
        """
        if num_runs >= 3:
            return ("High", "green")
        elif num_runs == 2:
            return ("Medium", "yellow")
        elif num_runs == 1:
            return ("Low", "red")
        else:
            return ("None", "dim")
