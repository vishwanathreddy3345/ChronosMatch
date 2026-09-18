# ChronosMatch Performance Benchmarking

## Overview

ChronosMatch includes an end-to-end performance benchmarking layer designed
to measure the throughput and processing latency of the market data and matching
pipeline.

The benchmark exercises the complete architecture:
1. **AsyncMarketSimulator**: Synthetic order generation.
2. **Order Serialization**: Fixed 29-byte binary serialization via `struct`.
3. **RingBuffer (mmap)**: Zero-copy inter-process communication storage.
4. **Order Deserialization**: Binary decoding into `Order` instances.
5. **MatchingEngine**: Order validation and dispatch.
6. **LimitOrderBook**: Price-time priority book management (bids and asks).

## Metrics Measured

- **Orders Processed**: Total count of orders successfully produced, transported,
  deserialized, and ingested into the order book queues.
- **Elapsed Time**: Total wall-clock time for the run, measured using
  high-resolution nanosecond timestamps (`time.perf_counter_ns()`).
- **Throughput (orders/sec)**: Rate of order processing:
  $$\text{Throughput} = \frac{\text{Orders}}{\text{Elapsed Seconds}}$$
- **Average Latency (ns/order)**: Mean amortized duration to process a single order
  across the full pipeline:
  $$\text{Latency} = \frac{\text{Elapsed Nanoseconds}}{\text{Orders}}$$

## Machine Dependency

All benchmark results are inherently machine- and environment-dependent.
Key factors include:
- **Operating System & Scheduler**: OS clock resolution and context switching
  latencies vary across operating systems (e.g., Windows timer quanta vs Linux).
- **CPU Characteristics**: Core frequency, IPC capabilities, and cache hierarchy
  (L1/L2/L3 cache sizes) impact memory-mapped buffer access.
- **Memory Subsystem**: Memory bandwidth and page fault handling for mmap files.
- **Background Load**: Concurrent processes and system activity during execution.

## Running the Benchmarks

### Default Benchmark Run (10,000 orders)

```bash
python benchmarks/benchmark_pipeline.py
```

Or via module execution:

```bash
python -m benchmarks.benchmark_python
```

### Custom Workload Sizes

Run with a specific order count:

```bash
python benchmarks/benchmark_pipeline.py --count 1000
python benchmarks/benchmark_pipeline.py --count 10000
python benchmarks/benchmark_pipeline.py --count 100000
```

### Multiple Workload Sizes

Run several workloads sequentially:

```bash
python benchmarks/benchmark_pipeline.py --workloads 1000 10000
```

### Additional Parameters

- `--rate <float>`: Target generation rate in orders/sec (defaults to
  unthrottled maximum throughput).
- `--buffer-capacity <int>`: Ring buffer capacity in order slots (defaults
  to auto-scaled capacity).
- `--seed <int>`: Random seed for reproducible generation (default: 42).

## Example Output Format

> [!NOTE]
> The following output illustrates the report structure only and does not
> represent fixed benchmark values. Actual numbers will vary by machine.

```text
ChronosMatch Benchmark
-----------------------
Orders:          <order_count>
Elapsed:         <elapsed_ms> ms
Throughput:      <orders_per_sec> orders/sec
Avg latency:     <avg_latency_ns> ns/order
```
