import asyncio
import time
from pathlib import Path
from typing import Sequence, Tuple, Optional
import random

from ..ipc.ring_buffer import RingBuffer
from ..models.order import Order, Side


class AsyncMarketSimulator:
    """Asynchronous market simulator that generates :class:`Order` objects
    and writes them into a :class:`~chronosmatch.ipc.ring_buffer.RingBuffer`.

    Parameters
    ----------
    count: int
        Number of orders to generate. Must be >= 0.
    rate: float
        Approximate orders per second. Must be > 0.
    symbols: Sequence[str] | None, optional
        List of ticker symbols to choose from. If ``None`` a default small
        list is used. The list must be non‑empty and contain non‑empty strings.
    price_range: Tuple[float, float], optional
        Uniform range ``(low, high)`` for order price. ``low`` must be < ``high``.
    quantity_range: Tuple[int, int], optional
        Uniform range ``(low, high)`` for order quantity. ``low`` must be > 0
        and ``low`` < ``high``.
    buy_ratio: float, optional
        Probability that an order is a BUY. ``0.0`` → all SELL, ``1.0`` → all BUY.
    buffer_path: Path | None, optional
        Path to the mmap file used by the underlying :class:`RingBuffer`.
        If ``None`` a temporary file will be created by the caller.
    buffer_capacity: int, optional
        Capacity of the ring buffer (number of orders it can hold). Must be > 0.
    seed: int | None, optional
        Seed for deterministic random generation. If ``None`` uses system RNG.
    """

    _DEFAULT_SYMBOLS = ["AAPL", "GOOG", "MSFT", "AMZN"]

    def __init__(
        self,
        *,
        count: int = 1_000,
        rate: float = 10.0,
        symbols: Optional[Sequence[str]] = None,
        price_range: Tuple[float, float] = (10.0, 1000.0),
        quantity_range: Tuple[int, int] = (1, 1_000),
        buy_ratio: float = 0.5,
        buffer_path: Optional[Path] = None,
        buffer_capacity: int = 4,
        seed: Optional[int] = None,
    ) -> None:
        # Basic validation
        if count < 0:
            raise ValueError("count must be non‑negative")
        if rate <= 0:
            raise ValueError("rate must be greater than 0")
        if symbols is None:
            symbols = self._DEFAULT_SYMBOLS
        if not isinstance(symbols, Sequence) or len(symbols) == 0:
            raise ValueError("symbols must be a non‑empty sequence of strings")
        if any(not isinstance(s, str) or s == "" for s in symbols):
            raise ValueError("each symbol must be a non‑empty string")
        low_price, high_price = price_range
        if low_price >= high_price:
            raise ValueError("price_range low must be < high")
        low_qty, high_qty = quantity_range
        if low_qty <= 0 or low_qty >= high_qty:
            raise ValueError(
                "quantity_range must be (positive low, high) with low < high"
            )
        if not (0.0 <= buy_ratio <= 1.0):
            raise ValueError("buy_ratio must be between 0.0 and 1.0 inclusive")
        if buffer_capacity <= 0:
            raise ValueError("buffer_capacity must be positive")

        self._count = count
        self._rate = rate
        self._symbols = list(symbols)
        self._price_range = price_range
        self._quantity_range = quantity_range
        self._buy_ratio = buy_ratio
        self._rng = random.Random(seed)
        self._side_rng = random.Random(seed)
        self._buffer = RingBuffer(path=buffer_path, capacity=buffer_capacity)
        self._order_id_seq = 1

    def _generate_order(self) -> Order:
        """Generate a single :class:`Order` instance using the configured RNG."""
        # Determine side first for deterministic tests
        side = Side.BUY if self._side_rng.random() < self._buy_ratio else Side.SELL
        # symbol selection removed (unused)
        price = self._rng.uniform(*self._price_range)
        quantity = self._rng.randint(*self._quantity_range)
        # Use a simple integer timestamp (seconds since epoch)
        timestamp = int(time.time())
        order = Order(
            order_id=self._order_id_seq,
            side=side,
            price=price,
            quantity=quantity,
            timestamp=timestamp,
        )
        self._order_id_seq += 1
        return order

    async def _push_with_backpressure(self, order: Order) -> None:
        """Push *order* into the ring buffer, applying cooperative back‑pressure.

        If the buffer is full the coroutine sleeps briefly and retries. To avoid
        an infinite wait a total timeout of 5 seconds per order is enforced.
        """
        timeout = 5.0
        start = time.monotonic()
        while True:
            try:
                self._buffer.push(order)
                return
            except BufferError:
                if time.monotonic() - start > timeout:
                    raise RuntimeError("RingBuffer remained full for >5 seconds")
                await asyncio.sleep(0.001)  # 1 ms back‑off

    async def run(self) -> None:
        """Run the simulator, generating ``self._count`` orders at ``self._rate``.

        The coroutine respects ``self._rate`` by awaiting between order
        generations. For high rates (used in tests) the sleep duration becomes
        very small and the event loop remains responsive.
        """
        if self._count == 0:
            return
        interval = 1.0 / self._rate
        for _ in range(self._count):
            order = self._generate_order()
            await self._push_with_backpressure(order)
            # Respect the generation rate – ``await`` is non‑blocking.
            await asyncio.sleep(interval)

    def close(self) -> None:
        """Close the underlying ring‑buffer resources."""
        self._buffer.close()
