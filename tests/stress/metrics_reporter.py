"""Metrics reporter — reads stress test results and reports every N prompts.

Usage:
    python tests/stress/metrics_reporter.py [--interval 5000]

Reads /tmp/bitmod-stress-results.jsonl, aggregates by category and cache layer,
reports to stdout every `interval` prompts.
"""

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

RESULTS_LOG = Path("/tmp/bitmod-stress-results.jsonl")
STATUS_FILE = Path("/tmp/bitmod-stress-status.json")
STOP_SIGNAL = Path("/tmp/bitmod-stress-stop")
METRICS_LOG = Path("/tmp/bitmod-stress-metrics.jsonl")


def read_results(path: Path, offset: int = 0) -> list[dict]:
    """Read results from JSONL, starting at line offset."""
    results = []
    if not path.exists():
        return results
    with open(path) as f:
        for i, line in enumerate(f):
            if i < offset:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return results


def compute_metrics(results: list[dict]) -> dict:
    """Compute aggregate metrics from results."""
    total = len(results)
    if total == 0:
        return {"total": 0}

    successes = sum(1 for r in results if r.get("success"))
    errors = total - successes

    # By category
    cat_counts = Counter(r["category"] for r in results)
    cat_success = Counter(r["category"] for r in results if r.get("success"))
    cat_errors = Counter(r["category"] for r in results if not r.get("success"))

    # Cache hit analysis (only successful)
    successful = [r for r in results if r.get("success")]
    cache_hits = sum(1 for r in successful if r.get("cache_hit"))

    # Hit layer distribution
    layer_counts = Counter()
    for r in successful:
        layers = r.get("hit_layers", [])
        if layers:
            for layer in layers:
                layer_counts[layer] += 1
        else:
            layer_counts["none (full LLM)"] += 1

    # Latency stats
    latencies = [r["elapsed_ms"] for r in results if "elapsed_ms" in r]
    latencies.sort()

    latency_stats = {}
    if latencies:
        latency_stats = {
            "min_ms": round(latencies[0], 1),
            "p50_ms": round(latencies[len(latencies) // 2], 1),
            "p95_ms": round(latencies[int(len(latencies) * 0.95)], 1),
            "p99_ms": round(latencies[int(len(latencies) * 0.99)], 1),
            "max_ms": round(latencies[-1], 1),
            "avg_ms": round(sum(latencies) / len(latencies), 1),
        }

    # Per-category latency
    cat_latencies = defaultdict(list)
    for r in results:
        if "elapsed_ms" in r:
            cat_latencies[r["category"]].append(r["elapsed_ms"])

    cat_latency_avg = {
        cat: round(sum(lats) / len(lats), 1)
        for cat, lats in cat_latencies.items()
    }

    # Error types
    error_types = Counter()
    for r in results:
        if not r.get("success") and "error" in r:
            err = r["error"][:80]
            error_types[err] += 1

    return {
        "total": total,
        "successes": successes,
        "errors": errors,
        "success_rate": round(successes / total * 100, 1),
        "cache_hits": cache_hits,
        "cache_hit_rate": round(cache_hits / max(successes, 1) * 100, 1),
        "by_category": dict(cat_counts),
        "category_success": dict(cat_success),
        "category_errors": dict(cat_errors),
        "layer_distribution": dict(layer_counts),
        "latency": latency_stats,
        "category_avg_latency_ms": cat_latency_avg,
        "top_errors": dict(error_types.most_common(5)),
    }


def format_report(metrics: dict, checkpoint: int) -> str:
    """Format metrics into a readable report."""
    lines = [
        f"\n{'='*70}",
        f"  STRESS TEST REPORT — Checkpoint {checkpoint:,}",
        f"{'='*70}",
        f"  Total: {metrics['total']:,}  |  OK: {metrics['successes']:,}  |  "
        f"Errors: {metrics['errors']:,}  |  Success: {metrics.get('success_rate', 0)}%",
        f"  Cache Hits: {metrics['cache_hits']:,}  |  "
        f"Hit Rate: {metrics.get('cache_hit_rate', 0)}%",
    ]

    if metrics.get("latency"):
        lat = metrics["latency"]
        lines.append(
            f"  Latency: avg={lat['avg_ms']}ms  p50={lat['p50_ms']}ms  "
            f"p95={lat['p95_ms']}ms  p99={lat['p99_ms']}ms  max={lat['max_ms']}ms"
        )

    lines.append(f"\n  Cache Layer Distribution:")
    for layer, count in sorted(metrics.get("layer_distribution", {}).items(), key=lambda x: -x[1]):
        pct = count / max(metrics["successes"], 1) * 100
        bar = "█" * int(pct / 2)
        lines.append(f"    {layer:<25} {count:>6}  ({pct:5.1f}%)  {bar}")

    lines.append(f"\n  By Category:")
    for cat in sorted(metrics.get("by_category", {}).keys()):
        total = metrics["by_category"][cat]
        ok = metrics.get("category_success", {}).get(cat, 0)
        err = metrics.get("category_errors", {}).get(cat, 0)
        avg_lat = metrics.get("category_avg_latency_ms", {}).get(cat, 0)
        lines.append(f"    {cat:<20} {total:>6} sent  |  {ok:>6} ok  |  {err:>4} err  |  avg {avg_lat}ms")

    if metrics.get("top_errors"):
        lines.append(f"\n  Top Errors:")
        for err, count in metrics["top_errors"].items():
            lines.append(f"    [{count}x] {err}")

    lines.append(f"{'='*70}\n")
    return "\n".join(lines)


def main(interval: int = 5000):
    print(f"Metrics reporter started. Reporting every {interval} prompts.")
    last_reported = 0

    while True:
        if STOP_SIGNAL.exists():
            # Final report
            results = read_results(RESULTS_LOG)
            if results:
                metrics = compute_metrics(results)
                report = format_report(metrics, len(results))
                print(report)
                # Save final metrics
                METRICS_LOG.write_text(json.dumps(metrics, indent=2))
            print("Stop signal received. Final report above.")
            break

        results = read_results(RESULTS_LOG)
        current = len(results)

        # Report at each interval checkpoint
        next_checkpoint = ((last_reported // interval) + 1) * interval
        if current >= next_checkpoint:
            metrics = compute_metrics(results)
            report = format_report(metrics, next_checkpoint)
            print(report)

            # Append to metrics log
            with open(METRICS_LOG, "a") as f:
                f.write(json.dumps({"checkpoint": next_checkpoint, **metrics}) + "\n")

            last_reported = next_checkpoint

        time.sleep(5)  # Poll every 5 seconds


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=5000)
    args = parser.parse_args()
    main(args.interval)
