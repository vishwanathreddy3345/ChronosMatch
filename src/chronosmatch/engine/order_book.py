"""Limit Order Book (LOB) implementation for ChronosMatch.

Provides a pure‑Python data structure that maintains price‑time priority for
BUY (bid) and SELL (ask) orders.  This is the foundation for the matching
engine that will be added on Day 9.

The implementation is deliberately lightweight and uses only built‑in types:
- ``dict`` mapping price -> ``list`` of :class:`~chronosmatch.models.order.Order`
  objects (FIFO order within the same price level).
- Two sorted ``list`` objects keep the price levels in priority order.

The public API mirrors typical order‑book operations:
* ``add_order(order)`` – insert a new order.
* ``best_bid`` / ``best_ask`` – current best prices.
* ``spread`` – ``best_ask - best_bid`` or ``None`` if one side is empty.
* ``depth(side=None)`` – snapshot of the book state.
* ``remove_order(order_id)`` – cancel an order (optional; raises ``KeyError``
  if not found).
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from ..models.order import Order, Side


@dataclass(slots=True)
class _PriceLevel:
    """Helper container for a price level.

    Stores the price and a FIFO list of :class:`Order` objects at that price.
    """

    price: float
    orders: List[Order]

    def __len__(self) -> int:
        return len(self.orders)


class LimitOrderBook:
    """Pure‑Python limit order book.

    The book maintains separate structures for BUY (bid) and SELL (ask) sides.
    Price‑time priority is enforced:

    * BUY: higher price has higher priority.
    * SELL: lower price has higher priority.
    * Within the same price level, orders are served FIFO (earlier insertion
      first, based on the ``timestamp`` that the :class:`Order` carries).
    """

    def __init__(self) -> None:
        # price -> list[Order]
        self._bids: Dict[float, List[Order]] = {}
        self._asks: Dict[float, List[Order]] = {}
        # Sorted price lists for fast best‑price lookup.
        self._bid_prices: List[float] = []  # descending order
        self._ask_prices: List[float] = []  # ascending order

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _insert_price(self, price: float, side: Side) -> None:
        """Insert *price* into the sorted price list for *side* if missing."""
        if side is Side.BUY:
            if price not in self._bid_prices:
                bisect.insort_left(self._bid_prices, price)
        else:  # SELL
            if price not in self._ask_prices:
                bisect.insort_left(self._ask_prices, price)

    def _remove_price_if_empty(self, price: float, side: Side) -> None:
        """Remove *price* from the price list when its order list becomes empty."""
        if side is Side.BUY:
            if not self._bids.get(price):
                self._bids.pop(price, None)
                self._bid_prices.remove(price)
        else:
            if not self._asks.get(price):
                self._asks.pop(price, None)
                self._ask_prices.remove(price)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def add_order(self, order: Order) -> None:
        """Validate and insert *order* into the appropriate side of the book.

        Raises:
            TypeError: If *order* is not an instance of :class:`Order`.
            ValueError: If the order side is unknown.
        """
        if not isinstance(order, Order):
            raise TypeError("order must be an Order instance")

        if order.side is Side.BUY:
            book = self._bids
        elif order.side is Side.SELL:
            book = self._asks
        else:
            raise ValueError(f"Unsupported side: {order.side}")

        price = order.price
        if price not in book:
            book[price] = []
            self._insert_price(price, order.side)
        # Append preserves FIFO within the price level.
        book[price].append(order)

    # ------------------------------------------------------------------
    # Accessors for best prices and spread
    # ------------------------------------------------------------------
    @property
    def best_bid(self) -> Optional[float]:
        """Highest bid price or ``None`` if no buy orders exist."""
        return self._bid_prices[-1] if self._bid_prices else None

    @property
    def best_ask(self) -> Optional[float]:
        """Lowest ask price or ``None`` if no sell orders exist."""
        return self._ask_prices[0] if self._ask_prices else None

    @property
    def spread(self) -> Optional[float]:
        """Price spread (best ask – best bid) or ``None`` when either side empty."""
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------
    def depth(self, side: Optional[Side] = None) -> Mapping[float, Tuple[Order, ...]]:
        """Return a *read‑only* snapshot of the order book.

        The returned mapping uses price as the key and a tuple of orders (FIFO
        order) as the value.  The snapshot is a copy; mutating it will not affect
        the live book.
        """
        if side is Side.BUY:
            # BUY side: descending price order (best bid first)
            prices = sorted(self._bids.keys(), reverse=True)
            return {price: tuple(self._bids[price]) for price in prices}
        elif side is Side.SELL:
            # SELL side: ascending price order (best ask first)
            prices = sorted(self._asks.keys())
            return {price: tuple(self._asks[price]) for price in prices}
        else:
            # Combine both sides for a full view (order not guaranteed).
            combined: Dict[float, Tuple[Order, ...]] = {}
            for d in (self._bids, self._asks):
                for price, orders in d.items():
                    combined[price] = tuple(orders)
            return combined

    # ------------------------------------------------------------------
    # Order cancellation (optional)
    # ------------------------------------------------------------------
    # noqa: C901
    def remove_order(self, order_id: int) -> None:
        """Cancel an order by *order_id*.

        Searches both sides for the given identifier, removes the order and
        cleans up empty price levels via ``_remove_price_if_empty``.
        """
        # BUY side
        for price, orders in list(self._bids.items()):
            for idx, o in enumerate(orders):
                if o.order_id == order_id:
                    del orders[idx]
                    if not orders:
                        self._remove_price_if_empty(price, Side.BUY)
                    return
        # SELL side
        for price, orders in list(self._asks.items()):
            for idx, o in enumerate(orders):
                if o.order_id == order_id:
                    del orders[idx]
                    if not orders:
                        self._remove_price_if_empty(price, Side.SELL)
                    return
        raise KeyError(f"order_id {order_id} not found in order book")

    # ------------------------------------------------------------------
    # Utility methods (not part of the public API but handy for tests)
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"LimitOrderBook(bids={len(self._bids)} price levels, "
            f"asks={len(self._asks)} price levels)"
        )
