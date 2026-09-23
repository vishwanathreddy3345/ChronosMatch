# cython_lob.pyx – Cython optimized LimitOrderBook

# distutils: language = c
# cython: language_level=3

import bisect
from ..models.order import Order, Side

cdef class CythonLimitOrderBook:
    """Cython implementation of LimitOrderBook with static typing.
    Mirrors the pure‑Python implementation while using Cython for speed.
    """

    cdef dict _bids          # price -> list[Order]
    cdef dict _asks
    cdef list _bid_prices    # sorted ascending, best bid is last element
    cdef list _ask_prices    # sorted ascending, best ask is first element

    def __cinit__(self):
        # Initialise Python containers – fast attribute access from Cython.
        self._bids = {}
        self._asks = {}
        self._bid_prices = []
        self._ask_prices = []

    cpdef void _insert_price(self, double price, object side):
        """Insert ``price`` into the appropriate sorted price list if missing."""
        if side is Side.BUY:
            if price not in self._bid_prices:
                bisect.insort_left(self._bid_prices, price)
        else:  # SELL
            if price not in self._ask_prices:
                bisect.insort_left(self._ask_prices, price)

    cpdef void _remove_price_if_empty(self, double price, object side):
        """Remove ``price`` from the price list when its order list becomes empty."""
        cdef list orders
        if side is Side.BUY:
            orders = self._bids.get(price)
            if not orders:
                self._bids.pop(price, None)
                self._bid_prices.remove(price)
        else:
            orders = self._asks.get(price)
            if not orders:
                self._asks.pop(price, None)
                self._ask_prices.remove(price)

    cpdef void add_order(self, order):
        """Add an ``Order`` instance to the book, preserving price‑time priority.
        Typed locals avoid repeated attribute look‑ups.
        """
        cdef object side = order.side
        cdef double price = order.price
        cdef dict book
        cdef list pt_list
        if side is Side.BUY:
            book = self._bids
            pt_list = self._bid_prices
        else:
            book = self._asks
            pt_list = self._ask_prices
        if price not in book:
            book[price] = []
            bisect.insort_left(pt_list, price)
        (<list>book[price]).append(order)

    @property
    def best_bid(self):
        if self._bid_prices:
            return self._bid_prices[-1]
        return None

    @property
    def best_ask(self):
        if self._ask_prices:
            return self._ask_prices[0]
        return None

    @property
    def spread(self):
        cdef object b = self.best_bid
        cdef object a = self.best_ask
        if b is None or a is None:
            return None
        return a - b

    cpdef dict depth(self, side = None):
        """Return a snapshot mapping price -> tuple(Orders) for the requested side.
        The snapshot is a shallow copy; order objects are not duplicated.
        """
        cdef dict result = {}
        cdef double price
        if side is Side.BUY:
            for price in sorted(self._bids.keys(), reverse=True):
                result[price] = tuple(self._bids[price])
            return result
        elif side is Side.SELL:
            for price in sorted(self._asks.keys()):
                result[price] = tuple(self._asks[price])
            return result
        else:
            for price, orders in self._bids.items():
                result[price] = tuple(orders)
            for price, orders in self._asks.items():
                result[price] = tuple(orders)
            return result

    cpdef void remove_order(self, int order_id):
        """Remove an order by its identifier from both sides if present."""
        cdef list orders
        cdef double price
        cdef int idx
        for price, orders in list(self._bids.items()):
            for idx, o in enumerate(orders):
                if o.order_id == order_id:
                    del orders[idx]
                    if not orders:
                        self._remove_price_if_empty(price, Side.BUY)
                    return
        for price, orders in list(self._asks.items()):
            for idx, o in enumerate(orders):
                if o.order_id == order_id:
                    del orders[idx]
                    if not orders:
                        self._remove_price_if_empty(price, Side.SELL)
                    return
        raise KeyError(f"order_id {order_id} not found in order book")

    def __repr__(self):
        return f"CythonLimitOrderBook(bids={len(self._bids)} price levels, asks={len(self._asks)} price levels)"
