"""Matching engine integration for ChronosMatch Day 9.

Integrates the pure-Python :class:`~chronosmatch.engine.order_book.LimitOrderBook`
into the Week 1 market data flow (ring buffer and async simulator).
Orders produced by the simulator or popped from the ring buffer are submitted
to the order book, maintaining price-time priority across BUY (bid) and
SELL (ask) sides. Full trade execution and matching logic will be introduced
in Day 10.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, List, Mapping, Optional, Tuple

from ..models.order import Order, Side
from .order_book import LimitOrderBook

if TYPE_CHECKING:
    from ..ipc.ring_buffer import RingBuffer


class MatchingEngine:
    """Consumes orders from market-data flows and maintains limit order book state.

    Attributes:
        book: The underlying :class:`LimitOrderBook` managing order queues.
    """

    def __init__(self, book: Optional[LimitOrderBook] = None) -> None:
        """Initialise the matching engine with an optional pre-existing book."""
        self.book: LimitOrderBook = book if book is not None else LimitOrderBook()
        self._processed_count: int = 0

    @property
    def processed_count(self) -> int:
        """Number of orders successfully submitted to the order book."""
        return self._processed_count

    @property
    def best_bid(self) -> Optional[float]:
        """Current highest bid price or ``None`` if no buy orders exist."""
        return self.book.best_bid

    @property
    def best_ask(self) -> Optional[float]:
        """Current lowest ask price or ``None`` if no sell orders exist."""
        return self.book.best_ask

    @property
    def spread(self) -> Optional[float]:
        """Difference between best ask and best bid, or ``None`` if either is absent."""
        return self.book.spread

    def depth(self, side: Optional[Side] = None) -> Mapping[float, Tuple[Order, ...]]:
        """Return a read-only depth snapshot of the underlying order book."""
        return self.book.depth(side=side)

    def process_order(self, order: Order) -> None:
        """Validate and insert *order* into the underlying order book.

        Preserves price-time priority:
        - BUY: highest price first, FIFO at equal price.
        - SELL: lowest price first, FIFO at equal price.

        Raises:
            TypeError: If *order* is not an instance of :class:`Order`.
            ValueError: If the order has an invalid side.
        """
        self.book.add_order(order)
        self._processed_count += 1

    def consume_one(self, ring_buffer: RingBuffer) -> Optional[Order]:
        """Pop a single order from *ring_buffer* and submit to the order book.

        Returns:
            The consumed :class:`Order` if available, or ``None`` if the
            buffer was empty.
        """
        order = ring_buffer.pop()
        if order is not None:
            self.process_order(order)
            return order
        return None

    async def consume_from_ring_buffer(
        self,
        ring_buffer: RingBuffer,
        expected_count: int,
        poll_interval: float = 0.001,
    ) -> List[Order]:
        """Asynchronously consume *expected_count* orders from *ring_buffer*.

        Each consumed order is inserted into the order book. Yields control
        to the event loop between polls when the buffer is empty.

        Returns:
            List of consumed :class:`Order` objects in arrival order.
        """
        orders: List[Order] = []
        while len(orders) < expected_count:
            order = ring_buffer.pop()
            if order is not None:
                self.process_order(order)
                orders.append(order)
                continue
            await asyncio.sleep(poll_interval)
        return orders

    async def run_pipeline(
        self,
        *,
        buffer_path: Path,
        buffer_capacity: int = 4,
        **sim_kwargs,
    ) -> List[Order]:
        """Execute a market-data pipeline integrated with this matching engine.

        Creates and executes a :class:`~chronosmatch.pipeline.week1.Week1Pipeline`
        with this engine registered to ingest orders as they are deserialized.

        Returns:
            List of consumed :class:`Order` objects.
        """
        from ..pipeline.week1 import Week1Pipeline

        pipeline = Week1Pipeline(
            buffer_path=buffer_path,
            buffer_capacity=buffer_capacity,
            matching_engine=self,
            **sim_kwargs,
        )
        return await pipeline.run()
