"""End-to-end performance benchmarking for ChronosMatch.

Exercises the complete market data and matching pipeline:
AsyncMarketSimulator -> Order serialization -> RingBuffer (mmap) ->
Deserialization -> MatchingEngine -> LimitOrderBook.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
import sys
import tempfile
import time
from typing import Optional, Sequence

from chronosmatch.engine.matching import MatchingEngine
from chronosmatch.pipeline.week1 import Week1Pipeline


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Holds timing and throughput results from a pipeline benchmark run."""

    order_count: int
    elapsed_ns: int
    elapsed_ms: float
    orders_per_sec: float
    avg_latency_ns: float
    best_bid: Optional[float]
    best_ask: Optional[float]
    spread: Optional[float]


def run_pipeline_benchmark(
    *,
    count: int = 10_000,
    rate: Optional[float] = None,
    buffer_capacity: Optional[int] = None,
    seed: Optional[int] = 42,
    buffer_path: Optional[Path] = None,
) -> BenchmarkResult:
    """Execute an end-to-end pipeline benchmark using real components.

    Args:
        count: Number of orders to generate and process through the book.
        rate: Target order generation rate (orders/sec). Defaults to
            unthrottled generation (float("inf")) for maximum throughput.
        buffer_capacity: Ring buffer capacity. Defaults to scaled capacity.
        seed: Random seed for deterministic order stream generation.
        buffer_path: Optional custom path for the mmap buffer file.

    Returns:
        A :class:`BenchmarkResult` with timing, throughput and latency metrics.

    Raises:
        ValueError: If parameters are non-positive or invalid.
    """
    if count <= 0:
        raise ValueError("count must be a positive integer")
    if rate is not None and rate <= 0:
        raise ValueError("rate must be positive")
    if buffer_capacity is not None and buffer_capacity <= 0:
        raise ValueError("buffer_capacity must be a positive integer")

    sim_rate = float("inf") if rate is None else float(rate)
    capacity = (
        buffer_capacity if buffer_capacity is not None else min(max(count, 16), 65536)
    )

    is_temp = buffer_path is None
    if buffer_path is None:
        temp_dir = tempfile.gettempdir()
        tmp_file = Path(temp_dir) / f"chronosmatch_bench_{time.time_ns()}.dat"
    else:
        tmp_file = buffer_path

    if tmp_file.exists():
        try:
            tmp_file.unlink()
        except OSError:
            pass

    engine = MatchingEngine()
    pipeline = Week1Pipeline(
        buffer_path=tmp_file,
        buffer_capacity=capacity,
        count=count,
        rate=sim_rate,
        seed=seed,
        matching_engine=engine,
    )

    try:
        start_ns = time.perf_counter_ns()
        orders = asyncio.run(pipeline.run())
        end_ns = time.perf_counter_ns()
    finally:
        pipeline.close()
        if is_temp and tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass

    elapsed_ns = max(end_ns - start_ns, 1)
    elapsed_ms = elapsed_ns / 1_000_000.0
    elapsed_sec = elapsed_ns / 1_000_000_000.0
    processed_count = len(orders)
    orders_per_sec = processed_count / elapsed_sec if elapsed_sec > 0 else float("inf")
    avg_latency_ns = elapsed_ns / processed_count if processed_count > 0 else 0.0

    return BenchmarkResult(
        order_count=processed_count,
        elapsed_ns=elapsed_ns,
        elapsed_ms=elapsed_ms,
        orders_per_sec=orders_per_sec,
        avg_latency_ns=avg_latency_ns,
        best_bid=engine.best_bid,
        best_ask=engine.best_ask,
        spread=engine.spread,
    )


def format_benchmark_result(result: BenchmarkResult) -> str:
    """Format a BenchmarkResult for terminal output."""
    lines = [
        "ChronosMatch Benchmark",
        "-----------------------",
        f"Orders:          {result.order_count}",
        f"Elapsed:         {result.elapsed_ms:.2f} ms",
        f"Throughput:      {result.orders_per_sec:,.2f} orders/sec",
        f"Avg latency:     {result.avg_latency_ns:,.1f} ns/order",
    ]
    return "\n".join(lines)


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments for the benchmark runner."""
    parser = argparse.ArgumentParser(
        description="ChronosMatch End-to-End Pipeline Performance Benchmark"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10_000,
        help="Number of orders to process (default: 10000)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Target simulator rate in orders/sec (default: unthrottled)",
    )
    parser.add_argument(
        "--buffer-capacity",
        type=int,
        default=None,
        help="Ring buffer capacity (default: auto-scaled)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible order stream (default: 42)",
    )
    parser.add_argument(
        "--workloads",
        type=int,
        nargs="+",
        default=None,
        help="Run multiple workload sizes (e.g. --workloads 1000 10000)",
    )
    return parser.parse_args(args)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for running benchmarks."""
    args = parse_args(argv)

    if args.workloads:
        for count in args.workloads:
            print(f"\nRunning workload size: {count:,} orders...")
            result = run_pipeline_benchmark(
                count=count,
                rate=args.rate,
                buffer_capacity=args.buffer_capacity,
                seed=args.seed,
            )
            print(format_benchmark_result(result))
    else:
        result = run_pipeline_benchmark(
            count=args.count,
            rate=args.rate,
            buffer_capacity=args.buffer_capacity,
            seed=args.seed,
        )
        print(format_benchmark_result(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
