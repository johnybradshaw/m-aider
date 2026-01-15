"""Benchmark command for testing VM performance."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import click
import requests
from rich.console import Console
from rich.table import Table

from ..session import SessionManager
from ..benchmark_db import BenchmarkDatabase
from ..benchmark_models import get_model_category, get_quantization_type
from ..providers.linode import GPU_TYPES

console = Console()

# Test prompts of varying complexity, organized by category
TEST_PROMPTS = [
    # Coding tasks (4 prompts)
    {
        "name": "Simple function",
        "category": "coding",
        "prompt": "Write a Python function that checks if a number is prime.",
        "expected_tokens": 100,
    },
    {
        "name": "Code review",
        "category": "coding",
        "prompt": "Review this code and suggest improvements:\n\ndef process_data(data):\n    result = []\n    for i in range(len(data)):\n        if data[i] > 0:\n            result.append(data[i] * 2)\n    return result",
        "expected_tokens": 200,
    },
    {
        "name": "Algorithm explanation",
        "category": "coding",
        "prompt": "Explain how the quicksort algorithm works and provide a Python implementation with comments.",
        "expected_tokens": 400,
    },
    {
        "name": "Complex refactoring",
        "category": "coding",
        "prompt": "Refactor this legacy code to use modern Python patterns, type hints, and better error handling:\n\nclass DataProcessor:\n    def __init__(self):\n        self.data = []\n    \n    def add(self, item):\n        self.data.append(item)\n    \n    def process(self):\n        results = []\n        for d in self.data:\n            try:\n                results.append(d * 2)\n            except:\n                pass\n        return results",
        "expected_tokens": 500,
    },
    # Context-heavy tasks (4 prompts)
    {
        "name": "Multi-file code analysis",
        "category": "context_heavy",
        "prompt": """Analyze this multi-file Python project and identify potential issues:

# File: models.py
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
        self.posts = []

# File: views.py
from models import User

def create_user(request):
    user = User(request.name, request.email)
    user.save()
    return user

# File: database.py
users = []

def save_user(user):
    users.append(user)

What architectural problems do you see? How would you refactor this to be more maintainable?""",
        "expected_tokens": 800,
    },
    {
        "name": "Refactor with context",
        "category": "context_heavy",
        "prompt": """Given this large codebase context, refactor the payment processing module:

Current implementation has:
- 5 different payment providers (Stripe, PayPal, Square, Venmo, Bitcoin)
- Each provider has duplicate validation code
- Error handling is inconsistent
- Logging is scattered throughout
- No retry logic for failed payments
- Tests are tightly coupled to implementation

Propose a clean architecture that:
1. Uses dependency injection
2. Centralizes validation
3. Implements consistent error handling
4. Adds retry logic with exponential backoff
5. Makes testing easier

Provide the refactored code with detailed comments.""",
        "expected_tokens": 1000,
    },
    {
        "name": "Debug trace analysis",
        "category": "context_heavy",
        "prompt": """Analyze this stack trace and explain the root cause:

Traceback (most recent call last):
  File "app.py", line 145, in process_request
    result = handler.handle(request)
  File "handlers.py", line 67, in handle
    data = self.parse_json(request.body)
  File "handlers.py", line 89, in parse_json
    return json.loads(body.decode('utf-8'))
  File "/usr/lib/python3.9/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
  File "/usr/lib/python3.9/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
  File "/usr/lib/python3.9/json/decoder.py", line 355, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

What's the likely root cause? How would you fix it?""",
        "expected_tokens": 600,
    },
    {
        "name": "Architecture explanation",
        "category": "context_heavy",
        "prompt": """Explain the architecture of a production-ready microservices system for an e-commerce platform:

Requirements:
- Handle 100K+ concurrent users
- Support multiple payment providers
- Real-time inventory management
- Order processing and fulfillment
- User authentication and authorization
- Product catalog with search
- Recommendation engine
- Analytics and reporting

Describe:
1. Service boundaries and responsibilities
2. Communication patterns (sync vs async)
3. Data storage strategies
4. Scalability considerations
5. Reliability and fault tolerance
6. Monitoring and observability""",
        "expected_tokens": 800,
    },
    # Reasoning tasks (4 prompts)
    {
        "name": "Problem decomposition",
        "category": "reasoning",
        "prompt": """Break down this complex problem into smaller, manageable sub-problems:

Problem: Build a real-time collaborative code editor (like Google Docs but for code)

Consider:
- Conflict resolution when multiple users edit
- Syntax highlighting that updates in real-time
- Cursor position tracking for all users
- Undo/redo that works across users
- Performance with large files
- Network latency handling
- Offline support with sync when reconnected

What are the key technical challenges and how would you approach each one?""",
        "expected_tokens": 300,
    },
    {
        "name": "Design trade-offs analysis",
        "category": "reasoning",
        "prompt": """Analyze the trade-offs between these database architectures for a social media platform:

Option A: Single PostgreSQL database with read replicas
Option B: Sharded PostgreSQL across multiple servers
Option C: NoSQL (MongoDB/Cassandra) with eventual consistency
Option D: Hybrid approach (PostgreSQL for users, Cassandra for posts)

Compare them on:
- Scalability (reads and writes)
- Consistency guarantees
- Operational complexity
- Cost
- Query flexibility
- Development speed

Which would you choose and why?""",
        "expected_tokens": 400,
    },
    {
        "name": "Algorithmic optimization reasoning",
        "category": "reasoning",
        "prompt": """You need to find the k-th largest element in an unsorted array of n integers.

Analyze these approaches:
1. Sort the array: O(n log n) time, O(1) space
2. Use a min-heap of size k: O(n log k) time, O(k) space
3. Quickselect algorithm: O(n) average, O(n²) worst case, O(1) space
4. Use counting sort: O(n + max_value) time, O(max_value) space

For each approach, explain:
- When it's the best choice
- What are its weaknesses
- How would you optimize it further
- What if k is very small (k=1) or very large (k=n/2)?

Recommend the best approach for a production system.""",
        "expected_tokens": 500,
    },
    {
        "name": "System design",
        "category": "reasoning",
        "prompt": """Design a URL shortener service (like bit.ly) that handles 1 billion URLs and 10 billion redirects per day.

Consider:
1. How do you generate short codes? (hash vs counter vs random)
2. How do you prevent collisions?
3. How do you store billions of mappings efficiently?
4. How do you handle 100K+ redirects per second?
5. How do you make it highly available?
6. How do you prevent abuse (spam, malicious URLs)?
7. Should you support custom short URLs?
8. How do you track analytics (click counts, geo location)?

Provide a high-level architecture with justifications for your choices.""",
        "expected_tokens": 600,
    },
]


def run_single_prompt(
    api_base: str, prompt: str, model: str, timeout: int = 120
) -> Optional[Dict[str, Any]]:
    """Run a single prompt against the vLLM API.

    Args:
        api_base: API base URL
        prompt: Prompt to send
        model: Model name
        timeout: Request timeout in seconds

    Returns:
        Dictionary with response data or None if failed
    """
    url = f"{api_base}/completions"

    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": 1000,
        "temperature": 0.7,
        "stream": False,
    }

    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        elapsed_time = time.time() - start_time

        data = response.json()

        # Extract metrics
        completion = data.get("choices", [{}])[0].get("text", "")
        tokens_generated = len(completion.split())  # Rough estimate
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", tokens_generated)
        total_tokens = prompt_tokens + completion_tokens

        tokens_per_sec = completion_tokens / elapsed_time if elapsed_time > 0 else 0

        return {
            "success": True,
            "elapsed_time": elapsed_time,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "tokens_per_sec": tokens_per_sec,
            "completion": completion[:200],  # First 200 chars
        }

    except requests.exceptions.Timeout:
        console.print(f"[yellow]⚠ Request timeout after {timeout}s[/yellow]")
        return None
    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ API request failed: {e}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]✗ Unexpected error: {e}[/red]")
        return None


def calculate_cost_per_1k_tokens(tokens_per_sec: float, hourly_cost: float) -> float:
    """Calculate cost per 1K tokens.

    Args:
        tokens_per_sec: Token generation rate
        hourly_cost: VM hourly cost in USD

    Returns:
        Cost per 1K tokens in USD
    """
    if tokens_per_sec <= 0:
        return 0.0

    # Tokens per hour = tokens_per_sec * 3600
    tokens_per_hour = tokens_per_sec * 3600

    # Cost per token = hourly_cost / tokens_per_hour
    # Cost per 1K tokens = (hourly_cost / tokens_per_hour) * 1000
    cost_per_1k = (hourly_cost / tokens_per_hour) * 1000

    return cost_per_1k


@click.command(name="benchmark")
@click.option(
    "--session",
    "-s",
    default=None,
    help="Session name (uses current session if not specified)",
)
@click.option(
    "--output",
    "-o",
    default=".benchmark-results.json",
    help="Output file for results (default: .benchmark-results.json)",
)
@click.option(
    "--category",
    "-c",
    type=click.Choice(["all", "coding", "context_heavy", "reasoning"], case_sensitive=False),
    default="all",
    help="Test category to run (default: all)",
)
@click.option(
    "--save-to-db/--no-db",
    default=True,
    help="Save results to centralized benchmark database (default: True)",
)
def cmd(session: Optional[str], output: str, category: str, save_to_db: bool):
    """Run performance benchmark on current or specified VM.

    Tests the VM with prompts of varying complexity across three categories:
    - Coding: function writing, code review, refactoring
    - Context-heavy: large context analysis, architecture design
    - Reasoning: problem decomposition, trade-off analysis

    Measures:
    - Tokens per second (throughput)
    - Total generation time
    - Cost per 1K tokens

    Results are saved to a JSON file and optionally to the centralized database.
    """
    session_mgr = SessionManager()
    current_session = _get_session(session_mgr, session)
    _print_session_header(current_session)

    env_file = session_mgr.cache_dir / current_session.name / "aider-env"
    api_base, model_name = _load_api_settings(env_file)
    selected_tests = _select_tests(category)

    console.print(f"[bold]Running benchmark tests ({category})...[/bold]\n")
    results = _run_benchmark_tests(api_base, model_name, selected_tests)
    successful_results = [r for r in results if r.get("success", False)]

    if not successful_results:
        console.print("[red]✗ All tests failed[/red]")
        raise click.Abort()

    summary, results_by_category = _aggregate_results(
        successful_results,
        selected_tests,
        current_session.hourly_cost,
    )
    _print_summary(
        summary,
        current_session.hourly_cost,
        len(successful_results),
        len(selected_tests),
        results_by_category,
        category,
    )

    output_data = _build_output_data(
        current_session,
        category,
        results_by_category,
        summary,
        results,
    )
    output_path = _write_results(output, output_data)
    console.print(f"\n[green]✓ Results saved to: {output_path}[/green]")

    if save_to_db:
        _save_results_to_db(current_session, results_by_category, output_data, results)


def _get_session(session_mgr: SessionManager, session_name: Optional[str]):
    if session_name:
        current_session = session_mgr.get_session(session_name)
        if not current_session:
            console.print(f"[red]✗ Session '{session_name}' not found[/red]")
            raise click.Abort()
        return current_session

    current_session = session_mgr.get_current_session()
    if not current_session:
        console.print("[red]✗ No current session set[/red]")
        console.print("\nUse: maider use <session-name>")
        raise click.Abort()
    return current_session


def _print_session_header(current_session):
    console.print(f"\n[bold cyan]Benchmarking session: {current_session.name}[/bold cyan]\n")
    console.print(f"  Model: {current_session.model_id}")
    console.print(f"  Type: {current_session.type}")
    console.print(f"  Cost: ${current_session.hourly_cost}/hour\n")


def _load_api_settings(env_file: Path) -> tuple[str, str]:
    if not env_file.exists():
        console.print(f"[red]✗ Environment file not found: {env_file}[/red]")
        raise click.Abort()

    api_base = None
    model_name = None
    for line in env_file.read_text().splitlines():
        if line.startswith("export OPENAI_API_BASE="):
            api_base = line.split("=", 1)[1].strip('"').strip("'")
        elif line.startswith("export AIDER_MODEL="):
            model_name = line.split("=", 1)[1].strip('"').strip("'").replace("openai/", "")

    if not api_base or not model_name:
        console.print("[red]✗ Could not determine API settings[/red]")
        raise click.Abort()

    return api_base, model_name


def _select_tests(category: str):
    if category.lower() == "all":
        selected_tests = TEST_PROMPTS
    else:
        selected_tests = [t for t in TEST_PROMPTS if t["category"] == category.lower()]

    if not selected_tests:
        console.print(f"[red]✗ No tests found for category: {category}[/red]")
        raise click.Abort()

    return selected_tests


def _run_benchmark_tests(
    api_base: str, model_name: str, selected_tests: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for i, test in enumerate(selected_tests, 1):
        console.print(
            f"[cyan]Test {i}/{len(selected_tests)}: {test['name']} ({test['category']})[/cyan]"
        )

        result = run_single_prompt(api_base, test["prompt"], model_name)

        if result:
            console.print(
                f"  ✓ {result['completion_tokens']} tokens in {result['elapsed_time']:.2f}s"
            )
            console.print(f"  ➜ {result['tokens_per_sec']:.2f} tokens/sec\n")
            results.append(
                {
                    "test_name": test["name"],
                    "category": test["category"],
                    "prompt": test["prompt"],
                    "expected_tokens": test["expected_tokens"],
                    **result,
                }
            )
        else:
            console.print("  ✗ Test failed\n")
            results.append(
                {
                    "test_name": test["name"],
                    "category": test["category"],
                    "prompt": test["prompt"],
                    "success": False,
                }
            )

    return results


def _aggregate_results(
    successful_results: List[Dict[str, Any]],
    selected_tests: List[Dict[str, Any]],
    hourly_cost: float,
) -> tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    avg_tokens_per_sec = sum(r["tokens_per_sec"] for r in successful_results) / len(
        successful_results
    )
    total_time = sum(r["elapsed_time"] for r in successful_results)
    total_tokens = sum(r["completion_tokens"] for r in successful_results)
    cost_per_1k = calculate_cost_per_1k_tokens(avg_tokens_per_sec, hourly_cost)

    results_by_category = _build_results_by_category(successful_results, hourly_cost)

    summary = {
        "avg_tokens_per_sec": avg_tokens_per_sec,
        "total_time": total_time,
        "total_tokens": total_tokens,
        "cost_per_1k_tokens": cost_per_1k,
        "tests_passed": len(successful_results),
        "tests_total": len(selected_tests),
    }

    return summary, results_by_category


def _build_results_by_category(
    successful_results: List[Dict[str, Any]], hourly_cost: float
) -> Dict[str, Dict[str, Any]]:
    results_by_category: Dict[str, Dict[str, Any]] = {}
    for cat in ["coding", "context_heavy", "reasoning"]:
        cat_results = [r for r in successful_results if r.get("category") == cat]
        if not cat_results:
            continue
        cat_avg_tps = sum(r["tokens_per_sec"] for r in cat_results) / len(cat_results)
        results_by_category[cat] = {
            "avg_tokens_per_sec": cat_avg_tps,
            "total_time": sum(r["elapsed_time"] for r in cat_results),
            "total_tokens": sum(r["completion_tokens"] for r in cat_results),
            "cost_per_1k_tokens": calculate_cost_per_1k_tokens(cat_avg_tps, hourly_cost),
            "tests_passed": len(cat_results),
        }
    return results_by_category


def _print_summary(
    summary: Dict[str, Any],
    hourly_cost: float,
    successful_count: int,
    total_count: int,
    results_by_category: Dict[str, Dict[str, Any]],
    category: str,
) -> None:
    console.print("\n[bold]Benchmark Results[/bold]\n")

    table = Table(show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Average throughput", f"{summary['avg_tokens_per_sec']:.2f} tokens/sec")
    table.add_row("Total generation time", f"{summary['total_time']:.2f} seconds")
    table.add_row("Total tokens generated", f"{summary['total_tokens']}")
    table.add_row("Hourly cost", f"${hourly_cost:.2f}/hour")
    table.add_row("Cost per 1K tokens", f"${summary['cost_per_1k_tokens']:.4f}")
    table.add_row("Tests passed", f"{successful_count}/{total_count}")

    console.print(table)

    if category.lower() == "all" and results_by_category:
        console.print("\n[bold]Results by Category:[/bold]\n")
        for cat, cat_data in results_by_category.items():
            cat_display = cat.replace("_", " ").title()
            console.print(
                f"  [cyan]{cat_display}:[/cyan] {cat_data['avg_tokens_per_sec']:.2f} tokens/sec "
                f"(${cat_data['cost_per_1k_tokens']:.4f}/1K tokens)"
            )


def _build_output_data(
    current_session,
    category: str,
    results_by_category: Dict[str, Dict[str, Any]],
    summary: Dict[str, Any],
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(),
        "session": current_session.name,
        "model": current_session.model_id,
        "vm_type": current_session.type,
        "hourly_cost": current_session.hourly_cost,
        "category_filter": category,
        "results_by_category": results_by_category,
        "summary": summary,
        "tests": results,
    }


def _write_results(output: str, output_data: Dict[str, Any]) -> Path:
    output_path = Path(output)
    output_path.write_text(json.dumps(output_data, indent=2))
    return output_path


def _save_results_to_db(
    current_session,
    results_by_category: Dict[str, Dict[str, Any]],
    output_data: Dict[str, Any],
    results: List[Dict[str, Any]],
) -> None:
    try:
        db = BenchmarkDatabase()

        gpu_info = GPU_TYPES.get(current_session.type, {})
        gpu_count = gpu_info.get("gpus", 1)
        vram_per_gpu = gpu_info.get("vram_per_gpu", 0)

        vllm_config = {
            "tensor_parallel_size": gpu_count,
            "max_model_len": 32768,
            "gpu_memory_utilization": 0.90,
        }

        benchmark_result = db.create_result(
            gpu_type=current_session.type,
            gpu_count=gpu_count,
            vram_per_gpu=vram_per_gpu,
            hourly_cost=current_session.hourly_cost,
            model_id=current_session.model_id,
            model_category=get_model_category(current_session.model_id),
            vllm_config=vllm_config,
            results_by_category=results_by_category,
            summary=output_data["summary"],
            tests=results,
        )

        result_id = db.add_result(benchmark_result)

        console.print(f"[green]✓ Results saved to benchmark database (ID: {result_id[:8]})[/green]")

    except Exception as e:
        console.print(f"[yellow]⚠ Failed to save to database: {e}[/yellow]")
        console.print("[dim]Results are still saved to JSON file[/dim]")
