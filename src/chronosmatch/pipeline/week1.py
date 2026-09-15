import asyncio
import time
from pathlib import Path
from typing import List, Optional

from ..simulator.async_market import AsyncMarketSimulator
from ..ipc.ring_buffer import RingBuffer
from ..models.order import Order


class Week1Pipeline:
    """Integrates the async market simulator with the mmap ring buffer and a consumer.

    The pipeline runs the simulator to generate ``Order`` objects, pushes them into a
    :class:`~chronosmatch.ipc.ring_buffer.RingBuffer`, and concurrently consumes the
    serialized records, deserialising them back into :class:`~chronosmatch.models.order.Order`
    instances.

    The integration is deliberately lightweight – the consumer is a simple ``async``
    coroutine that repeatedly calls :meth:`RingBuffer.pop`.  ``RingBuffer.pop`` is a
    blocking call that acquires an internal lock, but the coroutine yields control
    between attempts using ``await asyncio.sleep`` so the event loop remains responsive.

    Parameters are forwarded to the underlying :class:`AsyncMarketSimulator`.  The
    same ``buffer_path`` and ``buffer_capacity`` must be supplied to both the simulator
    and the consumer so they operate on the same mmap file.
    """

    def __init__(self, *, buffer_path: Path, buffer_capacity: int = 4, **sim_kwargs):
        """Create a new pipeline.

        Args:
            buffer_path: Path to the mmap file used for the ring buffer.
            buffer_capacity: Capacity of the ring buffer (number of orders).
            **sim_kwargs: Keyword arguments passed directly to
                :class:`AsyncMarketSimulator` (e.g., ``count``, ``rate``, ``seed``).
        """
        self._buffer_path = buffer_path
        self._buffer_capacity = buffer_capacity
        # Initialise simulator with the same buffer parameters.
        self._sim = AsyncMarketSimulator(
            buffer_path=buffer_path,
            buffer_capacity=buffer_capacity,
            **sim_kwargs,
        )
        # Consumer will use its own RingBuffer instance pointing at the same file.
        self._ring = RingBuffer(path=buffer_path, capacity=buffer_capacity)

    async def _consume(self, expected_count: int) -> List[Order]:
        """Consume ``expected_count`` orders from the ring buffer.

        The coroutine repeatedly attempts to ``pop`` from the ring buffer.  If the
        buffer is empty it sleeps briefly (1 ms) to avoid busy‑waiting.
        """
        orders: List[Order] = []
        while len(orders) < expected_count:
            order = self._ring.pop()
            if order is not None:
                orders.append(order)
                continue
            # Empty – give producer a chance to fill the buffer.
            await asyncio.sleep(0.001)
        return orders

    async def run(self) -> List[Order]:
        """Execute the full pipeline and return the consumed orders.

        Returns:
            A list of ``Order`` objects that were produced by the simulator and
            successfully consumed from the ring buffer.
        """
        # Run simulator and consumer concurrently.
        producer_task = asyncio.create_task(self._sim.run())
        consumer_task = asyncio.create_task(self._consume(self._sim._count))
        # Wait for both to finish.
        consumed_orders = await consumer_task
        await producer_task
        # Cleanup resources.
        self._sim.close()
        self._ring.close()
        # Remove the mmap file to avoid leftover temporary files.
        if self._buffer_path.exists():
            try:
                self._buffer_path.unlink()
            except Exception:
                pass
        return consumed_orders

    def close(self) -> None:
        """Explicitly close underlying resources (useful if the pipeline is aborted)."""
        self._sim.close()
        self._ring.close()


def measure_throughput(
    *,
    count: int = 10_000,
    rate: float = 10_000.0,
    buffer_capacity: int = 4,
    seed: Optional[int] = None,
) -> dict:
    """Run the Week1Pipeline and measure throughput.

    Returns a dictionary with ``order_count``, ``elapsed``, ``orders_per_sec``, ``python_version`` and ``platform``.
    """
    import platform
    import sys
    from pathlib import Path
    import asyncio

    tmp_path = Path.cwd() / "tmp_week1_mmap.dat"
    if tmp_path.exists():
        tmp_path.unlink()
    pipeline = Week1Pipeline(
        buffer_path=tmp_path,
        buffer_capacity=buffer_capacity,
        count=count,
        rate=rate,
        seed=seed,
    )
    start = time.perf_counter()
    orders = asyncio.run(pipeline.run())
    elapsed = time.perf_counter() - start
    pipeline.close()
    if tmp_path.exists():
        tmp_path.unlink()
    return {
        "order_count": len(orders),
        "elapsed": elapsed,
        "orders_per_sec": len(orders) / elapsed if elapsed else float("inf"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }
