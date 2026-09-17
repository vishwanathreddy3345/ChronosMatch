# Day 9: Matching Engine & Order Book Integration

## Overview

Day 9 integrates the pure-Python `LimitOrderBook` (implemented on Day 8) into
the Week 1 market-data pipeline. Deserialized `Order` records emitted by the
async market simulator and transported via the mmap-backed ring buffer are
ingested into the limit order book in real time.

## Architecture & Data Flow

```
AsyncMarketSimulator
       │
       ▼ (Order serialization)
  RingBuffer (mmap IPC)
       │
       ▼ (Order deserialization)
  Week1Pipeline / Consumer
       │
       ▼ process_order()
  MatchingEngine
       │
       ▼ add_order()
  LimitOrderBook (Bids / Asks with Price-Time Priority)
```

## Key Components

### `MatchingEngine` (`chronosmatch.engine.matching`)

The `MatchingEngine` wraps a `LimitOrderBook` and provides:
- `process_order(order: Order)`: Validates and inserts orders into the book,
  updating bid/ask queues and the processed order counter.
- `consume_one(ring_buffer: RingBuffer)`: Reads a single order from the ring
  buffer and submits it to the book.
- `consume_from_ring_buffer(ring_buffer, count, ...)`: Async coroutine that
  continuously consumes orders from the ring buffer into the book.
- `run_pipeline(buffer_path, ...)`: Executes the complete end-to-end pipeline
  with market data feeding directly into the book.
- `best_bid` / `best_ask` / `spread` / `depth()`: Read-only accessors mirroring
  the underlying order book state.

### `Week1Pipeline` Integration (`chronosmatch.pipeline.week1`)

`Week1Pipeline` accepts an optional `matching_engine: MatchingEngine` parameter.
When supplied, the pipeline consumer submits each deserialized order to
`matching_engine.process_order(order)` as it arrives from the ring buffer,
while maintaining full backwards compatibility when omitted.

## Price-Time Priority Invariants

- **Bids (BUY)**: Highest price has top priority.
- **Asks (SELL)**: Lowest price has top priority.
- **Equal Prices**: First-In, First-Out (FIFO) based on arrival sequence.
- **Trade Execution**: Full matching and execution logic is deferred to Day 10.
