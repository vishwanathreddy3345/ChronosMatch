import asyncio
from pathlib import Path
import random

import pytest

from chronosmatch.pipeline.week1 import Week1Pipeline
from chronosmatch.models.order import Side


@pytest.fixture
def tmp_mmap_path(tmp_path: Path) -> Path:
    return tmp_path / "week1_mmap.dat"


def test_week1_pipeline_basic(tmp_mmap_path: Path):
    # Deterministic parameters
    seed = 12345
    count = 5
    rate = 1000.0  # high rate for fast test
    pipeline = Week1Pipeline(
        buffer_path=tmp_mmap_path,
        buffer_capacity=10,
        count=count,
        rate=rate,
        seed=seed,
    )
    # Run the pipeline
    orders = asyncio.run(pipeline.run())
    # Verify number of orders
    assert len(orders) == count
    # Verify order IDs are sequential starting at 1
    assert [o.order_id for o in orders] == list(range(1, count + 1))
    # Verify side sequence matches seeded randomness (default buy_ratio=0.5)
    rng = random.Random(seed)
    expected_sides = []
    for _ in range(count):
        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        expected_sides.append(side)
    assert [o.side for o in orders] == expected_sides
    # Ensure temporary mmap file has been removed after pipeline close
    assert not tmp_mmap_path.exists()


def test_week1_throughput_measurement(tmp_path: Path):
    from chronosmatch.pipeline.week1 import measure_throughput

    result = measure_throughput(count=20, rate=5000.0, buffer_capacity=5, seed=42)
    assert isinstance(result, dict)
    for key in [
        "order_count",
        "elapsed",
        "orders_per_sec",
        "python_version",
        "platform",
    ]:
        assert key in result
    assert result["order_count"] == 20
    assert result["elapsed"] > 0
