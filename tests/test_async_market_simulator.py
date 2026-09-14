import asyncio
from pathlib import Path
import pytest
import random

from chronosmatch.simulator import AsyncMarketSimulator
from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.models.order import Side


def test_simulator_invalid_configuration():
    # count < 0
    with pytest.raises(ValueError):
        AsyncMarketSimulator(count=-1)
    # rate <= 0
    with pytest.raises(ValueError):
        AsyncMarketSimulator(rate=0)
    # empty symbols list
    with pytest.raises(ValueError):
        AsyncMarketSimulator(symbols=[])
    # invalid price range
    with pytest.raises(ValueError):
        AsyncMarketSimulator(price_range=(100.0, 10.0))
    # invalid quantity range
    with pytest.raises(ValueError):
        AsyncMarketSimulator(quantity_range=(0, 10))
    # buy_ratio out of bounds
    with pytest.raises(ValueError):
        AsyncMarketSimulator(buy_ratio=-0.1)
    with pytest.raises(ValueError):
        AsyncMarketSimulator(buy_ratio=1.1)
    # buffer capacity <= 0
    with pytest.raises(ValueError):
        AsyncMarketSimulator(buffer_capacity=0)


def test_simulator_deterministic_generation(tmp_path: Path):
    # Deterministic generation using seed
    seed = 12345
    sim = AsyncMarketSimulator(
        count=5,
        rate=1000.0,  # high rate, sleep will be negligible
        symbols=["AAPL", "GOOG"],
        price_range=(10.0, 20.0),
        quantity_range=(1, 5),
        buy_ratio=0.6,
        buffer_path=tmp_path / "sim_mmap.dat",
        buffer_capacity=10,
        seed=seed,
    )
    # Run async simulator
    asyncio.run(sim.run())
    # Consume from ring buffer
    buffer = RingBuffer(path=tmp_path / "sim_mmap.dat", capacity=10)
    orders = []
    while not buffer.is_empty():
        o = buffer.pop()
        orders.append(o)
    buffer.close()
    sim.close()
    assert len(orders) == 5
    # Verify order IDs are sequential starting at 1
    assert [o.order_id for o in orders] == list(range(1, 6))
    # Verify sides follow seeded randomness (should be reproducible)
    # Using the same seed we can predict the side sequence manually
    rng = random.Random(seed)
    expected_sides = []
    for _ in range(5):
        side = Side.BUY if rng.random() < 0.6 else Side.SELL
        expected_sides.append(side)
    assert [o.side for o in orders] == expected_sides


def test_simulator_integration(tmp_path: Path):
    # Small count, moderate buffer, ensure no deadlock
    sim = AsyncMarketSimulator(
        count=3,
        rate=10.0,
        buffer_path=tmp_path / "int_mmap.dat",
        buffer_capacity=2,  # intentionally small to exercise back‑pressure
        seed=42,
    )

    # Run simulator concurrently with consumer that drains the buffer
    async def run_and_consume():
        consumer_task = asyncio.create_task(_consume(tmp_path / "int_mmap.dat"))
        await sim.run()
        # Wait a moment for consumer to finish processing remaining items
        await asyncio.sleep(0.1)
        consumer_task.cancel()

    async def _consume(path: Path):
        buf = RingBuffer(path=path, capacity=2)
        while True:
            if not buf.is_empty():
                _ = buf.pop()
            await asyncio.sleep(0.001)

    # Execute the combined coroutine
    asyncio.run(run_and_consume())
    sim.close()
