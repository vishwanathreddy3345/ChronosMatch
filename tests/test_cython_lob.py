"""Tests verifying parity between LimitOrderBook and CythonLimitOrderBook.

Validates that CythonLimitOrderBook matches the pure-Python LimitOrderBook in:
- Empty book initialization
- BUY and SELL order insertion and price-time priority
- Multiple price levels and best bid / ask / spread calculation
- FIFO order maintenance within identical price levels
- Order removal (partial, final in level, best price update, nonexistent ID)
- Depth snapshot consistency across all side options
- Invalid order handling (TypeError on non-Order instances)
- Multi-step deterministic operation sequences
- Dependency injection and flag-based compatibility with MatchingEngine
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import random
import time
from typing import List

import pytest

from chronosmatch.engine.cython_lob import CythonLimitOrderBook  # type: ignore[import-not-found]
from chronosmatch.engine.matching import MatchingEngine
from chronosmatch.engine.order_book import LimitOrderBook
from chronosmatch.models.order import Order, Side
from chronosmatch.pipeline.week1 import Week1Pipeline


def make_order(
    order_id: int,
    side: Side,
    price: float,
    quantity: int = 1,
    timestamp: int = 0,
) -> Order:
    """Helper to construct an Order instance."""
    return Order(
        order_id=order_id,
        side=side,
        price=price,
        quantity=quantity,
        timestamp=timestamp,
    )


def test_cython_lob_empty_book_parity():
    """Verify empty book state matches between Python and Cython implementations."""
    py_book = LimitOrderBook()
    cy_book = CythonLimitOrderBook()

    assert cy_book.best_bid is None
    assert cy_book.best_ask is None
    assert cy_book.spread is None
    assert cy_book.depth() == {}
    assert cy_book.depth(Side.BUY) == {}
    assert cy_book.depth(Side.SELL) == {}

    assert py_book.best_bid == cy_book.best_bid
    assert py_book.best_ask == cy_book.best_ask
    assert py_book.spread == cy_book.spread
    assert py_book.depth() == cy_book.depth()


def test_cython_lob_single_buy_order():
    """Verify single BUY order state matches Python LimitOrderBook."""
    py_book = LimitOrderBook()
    cy_book = CythonLimitOrderBook()
    order = make_order(1, Side.BUY, price=100.0, quantity=10, timestamp=1)

    py_book.add_order(order)
    cy_book.add_order(order)

    assert cy_book.best_bid == 100.0
    assert cy_book.best_ask is None
    assert cy_book.spread is None
    assert cy_book.depth(Side.BUY) == {100.0: (order,)}
    assert cy_book.depth(Side.SELL) == {}

    assert py_book.best_bid == cy_book.best_bid
    assert py_book.best_ask == cy_book.best_ask
    assert py_book.spread == cy_book.spread
    assert py_book.depth(Side.BUY) == cy_book.depth(Side.BUY)
    assert py_book.depth() == cy_book.depth()


def test_cython_lob_single_sell_order():
    """Verify single SELL order state matches Python LimitOrderBook."""
    py_book = LimitOrderBook()
    cy_book = CythonLimitOrderBook()
    order = make_order(2, Side.SELL, price=105.5, quantity=5, timestamp=2)

    py_book.add_order(order)
    cy_book.add_order(order)

    assert cy_book.best_ask == 105.5
    assert cy_book.best_bid is None
    assert cy_book.spread is None
    assert cy_book.depth(Side.SELL) == {105.5: (order,)}
    assert cy_book.depth(Side.BUY) == {}

    assert py_book.best_bid == cy_book.best_bid
    assert py_book.best_ask == cy_book.best_ask
    assert py_book.spread == cy_book.spread
    assert py_book.depth(Side.SELL) == cy_book.depth(Side.SELL)
    assert py_book.depth() == cy_book.depth()


def test_cython_lob_multiple_price_levels():
    """Verify multiple price levels, sorting, and spread match Python LOB."""
    py_book = LimitOrderBook()
    cy_book = CythonLimitOrderBook()

    # BUY orders: highest price should be best_bid
    b1 = make_order(1, Side.BUY, price=99.0)
    b2 = make_order(2, Side.BUY, price=101.0)
    b3 = make_order(3, Side.BUY, price=100.0)

    # SELL orders: lowest price should be best_ask
    s1 = make_order(4, Side.SELL, price=108.0)
    s2 = make_order(5, Side.SELL, price=105.0)
    s3 = make_order(6, Side.SELL, price=106.5)

    for o in (b1, b2, b3, s1, s2, s3):
        py_book.add_order(o)
        cy_book.add_order(o)

    assert cy_book.best_bid == 101.0
    assert cy_book.best_ask == 105.0
    assert cy_book.spread == pytest.approx(4.0)

    # BUY depth must be sorted descending by price (highest first)
    assert list(cy_book.depth(Side.BUY).keys()) == [101.0, 100.0, 99.0]
    # SELL depth must be sorted ascending by price (lowest first)
    assert list(cy_book.depth(Side.SELL).keys()) == [105.0, 106.5, 108.0]

    assert py_book.best_bid == cy_book.best_bid
    assert py_book.best_ask == cy_book.best_ask
    assert py_book.spread == cy_book.spread
    assert py_book.depth(Side.BUY) == cy_book.depth(Side.BUY)
    assert py_book.depth(Side.SELL) == cy_book.depth(Side.SELL)
    assert py_book.depth() == cy_book.depth()


def test_cython_lob_fifo_ordering_at_same_price():
    """Verify FIFO ordering at identical price level is strictly preserved."""
    py_book = LimitOrderBook()
    cy_book = CythonLimitOrderBook()

    # Three BUY orders at same price with increasing timestamps
    b1 = make_order(10, Side.BUY, price=100.0, timestamp=100)
    b2 = make_order(20, Side.BUY, price=100.0, timestamp=200)
    b3 = make_order(30, Side.BUY, price=100.0, timestamp=300)

    for o in (b1, b2, b3):
        py_book.add_order(o)
        cy_book.add_order(o)

    assert cy_book.depth(Side.BUY)[100.0] == (b1, b2, b3)
    assert [o.order_id for o in cy_book.depth(Side.BUY)[100.0]] == [10, 20, 30]

    # Two SELL orders at same price
    s1 = make_order(40, Side.SELL, price=105.0, timestamp=150)
    s2 = make_order(50, Side.SELL, price=105.0, timestamp=250)

    for o in (s1, s2):
        py_book.add_order(o)
        cy_book.add_order(o)

    assert cy_book.depth(Side.SELL)[105.0] == (s1, s2)
    assert [o.order_id for o in cy_book.depth(Side.SELL)[105.0]] == [40, 50]

    assert py_book.depth() == cy_book.depth()


def test_cython_lob_order_removal_parity():
    """Verify order cancellation, empty level removal, and KeyError parity."""
    py_book = LimitOrderBook()
    cy_book = CythonLimitOrderBook()

    o1 = make_order(1, Side.BUY, price=100.0)
    o2 = make_order(2, Side.BUY, price=100.0)
    o3 = make_order(3, Side.BUY, price=102.0)
    o4 = make_order(4, Side.SELL, price=105.0)

    for o in (o1, o2, o3, o4):
        py_book.add_order(o)
        cy_book.add_order(o)

    assert cy_book.best_bid == 102.0

    # Remove best bid (o3) -> best bid should fall to 100.0, level 102.0 removed
    py_book.remove_order(3)
    cy_book.remove_order(3)

    assert cy_book.best_bid == 100.0
    assert 102.0 not in cy_book.depth(Side.BUY)
    assert py_book.best_bid == cy_book.best_bid
    assert py_book.depth() == cy_book.depth()

    # Remove o1 (first of two at price 100.0) -> o2 remains
    py_book.remove_order(1)
    cy_book.remove_order(1)

    assert cy_book.depth(Side.BUY)[100.0] == (o2,)
    assert py_book.depth() == cy_book.depth()

    # Remove o2 (final order at 100.0) -> level 100.0 removed, best_bid becomes None
    py_book.remove_order(2)
    cy_book.remove_order(2)

    assert cy_book.best_bid is None
    assert cy_book.best_ask == 105.0
    assert cy_book.spread is None
    assert py_book.best_bid == cy_book.best_bid
    assert py_book.depth() == cy_book.depth()

    # Attempting to remove nonexistent order must raise KeyError in both
    with pytest.raises(KeyError):
        py_book.remove_order(999)
    with pytest.raises(KeyError):
        cy_book.remove_order(999)


def test_cython_lob_invalid_orders():
    """Verify TypeError is raised when invalid objects are passed to add_order."""
    cy_book = CythonLimitOrderBook()

    with pytest.raises(TypeError, match="must be an Order instance"):
        cy_book.add_order(None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be an Order instance"):
        cy_book.add_order("invalid_string")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be an Order instance"):
        cy_book.add_order(12345)  # type: ignore[arg-type]


def test_cython_lob_deterministic_sequence_parity():
    """Apply a deterministic sequence of mixed adds and removals to both books.

    Verifies identical state at every step: best_bid, best_ask, spread, and depth.
    """
    py_book = LimitOrderBook()
    cy_book = CythonLimitOrderBook()

    rng = random.Random(42)
    active_order_ids: List[int] = []

    prices = [98.0, 99.0, 99.5, 100.0, 100.5, 101.0, 102.0]
    next_order_id = 1

    for step in range(200):
        # 75% chance to add an order, 25% chance to remove (if any active)
        if rng.random() < 0.75 or not active_order_ids:
            oid = next_order_id
            next_order_id += 1
            side = Side.BUY if rng.random() < 0.5 else Side.SELL
            price = rng.choice(prices)
            qty = rng.randint(1, 50)
            order = make_order(oid, side, price=price, quantity=qty, timestamp=step)

            py_book.add_order(order)
            cy_book.add_order(order)
            active_order_ids.append(oid)
        else:
            # Remove a random existing order
            remove_idx = rng.randint(0, len(active_order_ids) - 1)
            oid = active_order_ids.pop(remove_idx)
            py_book.remove_order(oid)
            cy_book.remove_order(oid)

        # Check invariant parity at every step
        assert py_book.best_bid == cy_book.best_bid
        assert py_book.best_ask == cy_book.best_ask
        assert py_book.spread == cy_book.spread

        py_depth = py_book.depth()
        cy_depth = cy_book.depth()
        assert set(py_depth.keys()) == set(cy_depth.keys())
        for p in py_depth:
            assert [o.order_id for o in py_depth[p]] == [
                o.order_id for o in cy_depth[p]
            ]


def test_matching_engine_with_cython_book_injection():
    """Verify MatchingEngine works when injected with CythonLimitOrderBook."""
    cy_book = CythonLimitOrderBook()
    engine = MatchingEngine(book=cy_book)

    assert engine.book is cy_book
    assert engine.processed_count == 0
    assert engine.best_bid is None
    assert engine.best_ask is None
    assert engine.spread is None

    o1 = make_order(1, Side.BUY, price=100.0, quantity=10)
    o2 = make_order(2, Side.SELL, price=102.0, quantity=5)

    engine.process_order(o1)
    engine.process_order(o2)

    assert engine.processed_count == 2
    assert engine.best_bid == 100.0
    assert engine.best_ask == 102.0
    assert engine.spread == pytest.approx(2.0)
    assert 100.0 in engine.depth(Side.BUY)
    assert 102.0 in engine.depth(Side.SELL)


def test_matching_engine_use_cython_flag():
    """Verify MatchingEngine initializes CythonLimitOrderBook via use_cython=True."""
    engine = MatchingEngine(use_cython=True)
    assert isinstance(engine.book, CythonLimitOrderBook)

    # Combining explicit book and use_cython=True must raise ValueError
    match_msg = "Cannot specify both book and use_cython=True"
    with pytest.raises(ValueError, match=match_msg):
        MatchingEngine(book=LimitOrderBook(), use_cython=True)


def test_matching_engine_cython_pipeline_integration(tmp_path: Path):
    """Verify end-to-end Week1Pipeline runs seamlessly with a Cython-backed engine."""
    buf_file = tmp_path / "cython_pipeline.dat"
    engine = MatchingEngine(use_cython=True)
    count = 10

    pipeline = Week1Pipeline(
        buffer_path=buf_file,
        buffer_capacity=10,
        count=count,
        rate=2000.0,
        seed=42,
        matching_engine=engine,
    )

    orders = asyncio.run(pipeline.run())
    assert len(orders) == count
    assert engine.processed_count == count
    assert pipeline.matching_engine is engine

    # Ensure engine order book state reflects the processed orders
    buy_orders = [o for o in orders if o.side == Side.BUY]
    sell_orders = [o for o in orders if o.side == Side.SELL]

    if buy_orders:
        expected_best_bid = max(o.price for o in buy_orders)
        assert engine.best_bid == expected_best_bid

    if sell_orders:
        expected_best_ask = min(o.price for o in sell_orders)
        assert engine.best_ask == expected_best_ask


def test_cython_lob_performance_no_assertion():
    """Report execution timing for both implementations without assertion.

    Keeps performance measurement strictly informational, per Day 14 guidelines.
    """
    orders = [
        Order(
            order_id=i,
            side=random.choice([Side.BUY, Side.SELL]),
            price=random.uniform(90, 110),
            quantity=1,
            timestamp=i,
        )
        for i in range(2000)
    ]

    def run(book):
        for o in orders:
            book.add_order(o)

    # Python implementation timing
    start = time.perf_counter_ns()
    run(LimitOrderBook())
    py_ns = time.perf_counter_ns() - start

    # Cython implementation timing
    start = time.perf_counter_ns()
    run(CythonLimitOrderBook())
    cy_ns = time.perf_counter_ns() - start

    print(f"\n[Day 14 Informational Timing] Python LOB: {py_ns:,} ns")
    print(f"[Day 14 Informational Timing] Cython LOB: {cy_ns:,} ns")
