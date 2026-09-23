"""Benchmark comparing pure-Python LimitOrderBook vs CythonLimitOrderBook."""

from __future__ import annotations

import argparse
import random
import sys
import time
from typing import Optional, Sequence

from chronosmatch.engine import CythonLimitOrderBook, LimitOrderBook
from chronosmatch.models.order import Order, Side


def generate_orders(count: int, seed: int = 42) -> list[Order]:
    """Generate a deterministic stream of orders."""
    rng = random.Random(seed)
    orders: list[Order] = []
    sides = [Side.BUY, Side.SELL]
    for i in range(1, count + 1):
        side = rng.choice(sides)
        price = round(rng.uniform(90.0, 110.0), 2)
        qty = rng.randint(1, 100)
        orders.append(
            Order(order_id=i, side=side, price=price, quantity=qty, timestamp=i)
        )
    return orders


def run_benchmark(count: int = 10_000, seed: int = 42) -> int:
    """Benchmark LimitOrderBook vs CythonLimitOrderBook."""
    if CythonLimitOrderBook is None:
        print("Error: CythonLimitOrderBook is not available.")
        return 1

    orders = generate_orders(count, seed)

    # Benchmark Pure-Python LimitOrderBook
    py_book = LimitOrderBook()
    start_py = time.perf_counter_ns()
    for o in orders:
        py_book.add_order(o)
    end_py = time.perf_counter_ns()
    py_elapsed_ns = max(end_py - start_py, 1)
    py_elapsed_ms = py_elapsed_ns / 1_000_000.0
    py_ops = (count / (py_elapsed_ns / 1_000_000_000.0)) if py_elapsed_ns > 0 else 0.0
    py_lat = py_elapsed_ns / count if count > 0 else 0.0

    # Benchmark Cython LimitOrderBook
    cy_book = CythonLimitOrderBook()
    start_cy = time.perf_counter_ns()
    for o in orders:
        cy_book.add_order(o)
    end_cy = time.perf_counter_ns()
    cy_elapsed_ns = max(end_cy - start_cy, 1)
    cy_elapsed_ms = cy_elapsed_ns / 1_000_000.0
    cy_ops = (count / (cy_elapsed_ns / 1_000_000_000.0)) if cy_elapsed_ns > 0 else 0.0
    cy_lat = cy_elapsed_ns / count if count > 0 else 0.0

    # Verify order books reach the same state
    assert py_book.best_bid == cy_book.best_bid
    assert py_book.best_ask == cy_book.best_ask
    assert py_book.spread == cy_book.spread

    speedup = py_elapsed_ns / cy_elapsed_ns if cy_elapsed_ns > 0 else 1.0

    print("=" * 60)
    print("ChronosMatch: Python vs Cython LimitOrderBook Benchmark")
    print("=" * 60)
    print(f"Order Count:      {count:,}")
    print("-" * 60)
    print("Python LimitOrderBook:")
    print(f"  Elapsed:        {py_elapsed_ms:.2f} ms ({py_elapsed_ns:,} ns)")
    print(f"  Throughput:     {py_ops:,.2f} orders/sec")
    print(f"  Avg Latency:    {py_lat:,.1f} ns/order")
    print("-" * 60)
    print("Cython LimitOrderBook:")
    print(f"  Elapsed:        {cy_elapsed_ms:.2f} ms ({cy_elapsed_ns:,} ns)")
    print(f"  Throughput:     {cy_ops:,.2f} orders/sec")
    print(f"  Avg Latency:    {cy_lat:,.1f} ns/order")
    print("-" * 60)
    print(f"Relative Speedup: {speedup:.2f}x")
    print("=" * 60)

    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Benchmark Python vs Cython LimitOrderBook performance."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10_000,
        help="Number of orders to insert (default: 10,000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic order stream (default: 42)",
    )
    args = parser.parse_args(argv)
    return run_benchmark(count=args.count, seed=args.seed)


if __name__ == "__main__":
    sys.exit(main())
